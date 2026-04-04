import json
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from exceptions import InsufficientFundsError, ValidationError
from extensions import db
from helpers import set_config
from models import User
from services.finance_service import credit_user, debit_user

ADMIN_RESET_PASSWORD_MIN_LENGTH = 4
MAGIC_LINK_EXPIRY_HOURS = 24


def toggle_admin_status(actor, target):
    if target.id == actor.id:
        raise ValidationError("Tu ne peux pas modifier tes propres droits admin.")

    target.is_admin = not target.is_admin
    db.session.commit()
    state = 'promu administrateur' if target.is_admin else 'retire des administrateurs'
    return f"{target.username} a ete {state}."


def reset_user_password(target, new_password):
    new_password = (new_password or '').strip()
    if len(new_password) < ADMIN_RESET_PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"Mot de passe trop court (min {ADMIN_RESET_PASSWORD_MIN_LENGTH} caracteres)."
        )

    target.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return f"🔑 Mot de passe de {target.username} mis a jour."


def create_user_magic_link_token(target):
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=MAGIC_LINK_EXPIRY_HOURS)
    set_config(
        f'magic_token_{target.id}',
        json.dumps({
            'token': token,
            'expires': expires.isoformat(),
            'user_id': target.id,
        }),
    )
    return {
        'target': target,
        'token': token,
        'expires': expires,
    }


def adjust_user_balance_by_admin(actor, target, amount, reason):
    if amount is None or amount == 0:
        raise ValidationError("Montant invalide.")

    reason = (reason or 'Ajustement admin').strip() or 'Ajustement admin'

    if amount > 0:
        credit_user(
            target,
            amount,
            reason_code='admin_adjust',
            reason_label=reason,
            reference_type='user',
            reference_id=actor.id,
            commit=False,
        )
        db.session.commit()
        return f"💰 +{amount:.0f} 🪙 credites a {target.username}."

    try:
        debit_user(
            target,
            abs(amount),
            reason_code='admin_adjust',
            reason_label=reason,
            reference_type='user',
            reference_id=actor.id,
            commit=False,
        )
    except InsufficientFundsError:
        raise InsufficientFundsError(
            f"{target.username} n'a pas assez de BitGroins pour ce debit."
        ) from None

    db.session.commit()
    return f"💸 {amount:.0f} 🪙 debites de {target.username}."
