from urllib.parse import urlparse

from werkzeug.security import check_password_hash, generate_password_hash

from config.game_rules import AUTH_RULES
from content.pigs_catalog import PIG_ORIGINS
from exceptions import UserNotFoundError, ValidationError
from extensions import db
from models import GameConfig, Pig, User
from services.auth_log_service import log_auth_event
from services.economy_service import get_welcome_bonus_value
from services.finance_service import record_balance_transaction
from services.pig_lineage_service import (
    apply_origin_bonus,
    build_unique_pig_name,
    random_pig_sex,
)
from services.pig_power_service import generate_weight_kg_for_profile


def register_user(username, password):
    username = (username or '').strip()
    password = (password or '').strip()

    if not username or not password:
        raise ValidationError("Remplis tous les champs !")
    if len(username) < AUTH_RULES.minimum_username_length:
        raise ValidationError(
            f"Pseudo trop court (min {AUTH_RULES.minimum_username_length} caractères)"
        )
    if User.query.filter_by(username=username).first():
        raise ValidationError("Ce pseudo est déjà pris !")

    welcome_bonus = get_welcome_bonus_value()
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        balance=welcome_bonus,
    )
    db.session.add(user)
    db.session.flush()

    record_balance_transaction(
        user_id=user.id,
        amount=welcome_bonus,
        balance_before=0.0,
        balance_after=welcome_bonus,
        reason_code='welcome_bonus',
        reason_label="Bonus d'inscription",
        details="Capital de depart offert a la creation du compte.",
        reference_type='user',
        reference_id=user.id,
    )

    origin = AUTH_RULES.pick_default_origin(PIG_ORIGINS)
    pig = Pig(
        user_id=user.id,
        name=build_unique_pig_name(f"Cochon de {username}", fallback_prefix='Cochon'),
        emoji='🐷',
        sex=random_pig_sex(),
        origin_country=origin['country'],
        origin_flag=origin['flag'],
    )
    apply_origin_bonus(pig, origin)
    pig.weight_kg = generate_weight_kg_for_profile(pig)
    db.session.add(pig)

    log_auth_event(
        event_type='register',
        is_success=True,
        user_id=user.id,
        username_attempt=username,
    )
    db.session.commit()
    return user


def authenticate_user(username, password):
    username = (username or '').strip()
    password = (password or '').strip()
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        log_auth_event(
            event_type='login',
            is_success=False,
            username_attempt=username,
            details='invalid_credentials',
        )
        db.session.commit()
        raise ValidationError("Identifiants incorrects !")

    log_auth_event(
        event_type='login',
        is_success=True,
        user_id=user.id,
        username_attempt=username,
    )
    db.session.commit()
    return user


def resolve_safe_next_url(next_url):
    candidate = (next_url or '').strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if not parsed.scheme and not parsed.netloc and candidate.startswith('/'):
        return candidate
    return None


def change_user_password(user_or_id, current_password, new_password, confirm_password):
    user = user_or_id if isinstance(user_or_id, User) else User.query.get(user_or_id)
    if not user:
        raise UserNotFoundError("Utilisateur introuvable.")

    current_password = (current_password or '').strip()
    new_password = (new_password or '').strip()
    confirm_password = (confirm_password or '').strip()

    if not current_password or not new_password or not confirm_password:
        raise ValidationError("Remplis tous les champs pour changer ton mot de passe.")
    if not check_password_hash(user.password_hash, current_password):
        raise ValidationError("Ton mot de passe actuel est incorrect.")
    if len(new_password) < AUTH_RULES.minimum_password_length:
        raise ValidationError(
            f"Ton nouveau mot de passe doit faire au moins {AUTH_RULES.minimum_password_length} caractères."
        )
    if current_password == new_password:
        raise ValidationError("Choisis un mot de passe différent de l'actuel.")
    if new_password != confirm_password:
        raise ValidationError("La confirmation du nouveau mot de passe ne correspond pas.")

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return user


def consume_magic_login_token(token):
    configs = GameConfig.query.filter(GameConfig.key.like('magic_token_%')).all()
    for cfg in configs:
        data = AUTH_RULES.parse_magic_token_payload(cfg.value)
        if not data or data.get('token') != token:
            continue

        expires = AUTH_RULES.parse_magic_expiry(data.get('expires'))
        if not expires or AUTH_RULES.is_magic_token_expired(expires):
            log_auth_event(
                event_type='magic_login',
                is_success=False,
                username_attempt=str(data.get('user_id', '')),
                details='expired_token',
            )
            db.session.delete(cfg)
            db.session.commit()
            raise ValidationError("Ce lien magique a expire.")

        user = User.query.get(data.get('user_id'))
        if not user:
            log_auth_event(
                event_type='magic_login',
                is_success=False,
                username_attempt=str(data.get('user_id', '')),
                details='user_not_found',
            )
            db.session.commit()
            raise UserNotFoundError("Utilisateur introuvable.")

        log_auth_event(
            event_type='magic_login',
            is_success=True,
            user_id=user.id,
            username_attempt=user.username,
        )
        db.session.delete(cfg)
        db.session.commit()
        return user

    raise ValidationError("Lien magique invalide ou expire.")
