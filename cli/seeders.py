import logging
import os
from datetime import datetime, timedelta

import click
from werkzeug.security import generate_password_hash

from config.grain_market_defaults import BOURSE_DEFAULT_POS
from content.pigs_catalog import PIG_ORIGINS
from content.seed_game_items import COCHON_PENDU_WORDS, CEREALS, SCHOOL_LESSONS, TRAININGS
from extensions import db
from helpers.race import ensure_next_race
from models import (
    BalanceTransaction,
    CerealItem,
    GrainMarket,
    HangmanWordItem,
    Pig,
    SchoolLessonItem,
    TrainingItem,
    User,
)
from services.auth_log_service import purge_old_auth_events
from services.finance_service import record_balance_transaction
from services.pig_lineage_service import (
    apply_origin_bonus,
    build_unique_pig_name,
    create_preloaded_admin_pigs,
    random_pig_sex,
)
from services.pig_power_service import clamp_pig_weight, generate_weight_kg_for_profile

logger = logging.getLogger(__name__)


def run_seeders(with_admin=True):
    """Regroupe tous les seeds applicatifs pour une execution explicite."""
    if with_admin:
        ensure_admin_user()
    seed_users()
    ensure_balance_transaction_snapshots()
    ensure_next_race()
    init_grain_market()
    seed_game_data()


def register_cli_commands(app):
    @app.cli.command('seed-db')
    @click.option('--with-admin/--without-admin', default=True, show_default=True)
    def seed_db_command(with_admin):
        """Peuple les donnees initiales de l'application."""
        run_seeders(with_admin=with_admin)
        click.echo('✅ Seed termine.')

    @app.cli.command('purge-auth-logs')
    @click.option('--days', default=None, type=int, help='Override retention days for this run.')
    def purge_auth_logs_command(days):
        """Supprime les evenements d'authentification anciens."""
        retention_days = int(days or app.config.get('AUTH_LOG_RETENTION_DAYS', 180))
        deleted_count = purge_old_auth_events(retention_days)
        click.echo(f'🧹 Auth logs purgés: {deleted_count} (rétention: {retention_days} jours)')


def ensure_admin_user():
    """Garantit que le compte admin existe avec les bons credentials."""
    try:
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            admin = User(
                username='admin',
                password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin')),
                balance=100.0,
                is_admin=True,
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("[SEED] Compte 'admin' cree avec succes (admin/admin)")
        else:
            admin.is_admin = True
            db.session.commit()
            logger.info("[SEED] Compte 'admin' existant verifie (is_admin=True)")
    except Exception as exc:
        db.session.rollback()
        logger.error("[SEED] ERREUR CRITIQUE - impossible de creer le compte admin: %s", exc)


def seed_users():
    default_users = [
        {'username': 'Emerson', 'pig_name': 'Groin de Tonnerre', 'emoji': '🐗', 'origin': 'Brésil'},
        {'username': 'Pascal', 'pig_name': 'Le Baron du Lard', 'emoji': '🐷', 'origin': 'France'},
        {'username': 'Simon', 'pig_name': 'Saucisse Turbo', 'emoji': '🌭', 'origin': 'Allemagne'},
        {'username': 'Edwin', 'pig_name': 'Porcinator', 'emoji': '🐽', 'origin': 'Angleterre'},
        {'username': 'Julien', 'pig_name': 'Flash McGroin', 'emoji': '🐖', 'origin': 'Japon'},
        {'username': 'Christophe', 'pig_name': 'Père Cochon', 'emoji': '🏆', 'origin': 'France', 'admin': True},
        {'username': 'admin', 'pig_name': 'Grand Admin', 'emoji': '👑', 'origin': 'France', 'admin': True, 'password': os.environ.get('ADMIN_PASSWORD', 'admin')},
    ]
    for user_data in default_users:
        existing = User.query.filter_by(username=user_data['username']).first()
        if existing:
            existing.password_hash = generate_password_hash(user_data.get('password', 'mdp1234'))
            if user_data.get('admin'):
                existing.is_admin = True
            continue

        origin_data = next(
            (origin for origin in PIG_ORIGINS if origin['country'] == user_data.get('origin', 'France')),
            PIG_ORIGINS[0],
        )
        user = User(
            username=user_data['username'],
            password_hash=generate_password_hash(user_data.get('password', 'mdp1234')),
            balance=100.0,
            is_admin=user_data.get('admin', False),
        )
        db.session.add(user)
        db.session.flush()

        pig = Pig(
            user_id=user.id,
            name=build_unique_pig_name(user_data['pig_name'], fallback_prefix='Cochon'),
            emoji=user_data['emoji'],
            sex=random_pig_sex(),
            origin_country=origin_data['country'],
            origin_flag=origin_data['flag'],
            lineage_name=f"Maison {user_data['username']}",
        )
        apply_origin_bonus(pig, origin_data)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)

    demo_owner = User.query.filter_by(username='Christophe').first()
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        create_preloaded_admin_pigs(admin_user)

    if demo_owner:
        demo_pig = Pig.query.filter_by(user_id=demo_owner.id, name='Patient Zero').first()
        owner_pig_count = Pig.query.filter_by(user_id=demo_owner.id).count()
        if not demo_pig and owner_pig_count < 2:
            origin_data = next((origin for origin in PIG_ORIGINS if origin['country'] == 'Belgique'), PIG_ORIGINS[0])
            demo_pig = Pig(
                user_id=demo_owner.id,
                name='Patient Zero',
                emoji='🩹',
                sex=random_pig_sex(),
                origin_country=origin_data['country'],
                origin_flag=origin_data['flag'],
                energy=62,
                hunger=58,
                happiness=54,
                is_injured=True,
                injury_risk=28.0,
                vet_deadline=datetime.utcnow() + timedelta(hours=12),
                lineage_name=f"Maison {demo_owner.username}",
            )
            apply_origin_bonus(demo_pig, origin_data)
            demo_pig.weight_kg = clamp_pig_weight(118.0)
            db.session.add(demo_pig)

    db.session.commit()


def ensure_balance_transaction_snapshots():
    logged_user_ids = {user_id for (user_id,) in db.session.query(BalanceTransaction.user_id).distinct().all()}
    created = False
    for user in User.query.all():
        if user.id in logged_user_ids:
            continue
        opening_balance = round(float(user.balance or 0.0), 2)
        record_balance_transaction(
            user_id=user.id,
            amount=opening_balance,
            balance_before=0.0,
            balance_after=opening_balance,
            reason_code='snapshot',
            reason_label='Ouverture du journal BitGroin',
            details="Solde observe au moment de l'activation de la tracabilite.",
            reference_type='user',
            reference_id=user.id,
        )
        created = True
    if created:
        db.session.commit()


def seed_game_data():
    """Peuple les tables de donnees de jeu au premier lancement."""
    import json as _json

    if not CerealItem.query.first():
        for index, (key, cereal) in enumerate(CEREALS.items()):
            item = CerealItem(
                key=key,
                name=cereal['name'],
                emoji=cereal['emoji'],
                cost=cereal['cost'],
                description=cereal.get('description', ''),
                hunger_restore=cereal.get('hunger_restore', 0),
                energy_restore=cereal.get('energy_restore', 0),
                weight_delta=cereal.get('weight_delta', 0),
                valeur_fourragere=cereal.get('valeur_fourragere', 100),
                sort_order=index,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', cereal.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()

    if not TrainingItem.query.first():
        for index, (key, training) in enumerate(TRAININGS.items()):
            item = TrainingItem(
                key=key,
                name=training['name'],
                emoji=training['emoji'],
                description=training.get('description', ''),
                energy_cost=training.get('energy_cost', 0),
                hunger_cost=training.get('hunger_cost', 0),
                weight_delta=training.get('weight_delta', 0),
                min_happiness=training.get('min_happiness', 0),
                happiness_bonus=training.get('happiness_bonus', 0),
                sort_order=index,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', training.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()

    if not SchoolLessonItem.query.first():
        for index, (key, lesson) in enumerate(SCHOOL_LESSONS.items()):
            item = SchoolLessonItem(
                key=key,
                name=lesson['name'],
                emoji=lesson['emoji'],
                description=lesson.get('description', ''),
                question=lesson['question'],
                answers_json=_json.dumps(lesson['answers'], ensure_ascii=False),
                xp=lesson.get('xp', 20),
                wrong_xp=lesson.get('wrong_xp', 5),
                energy_cost=lesson.get('energy_cost', 10),
                hunger_cost=lesson.get('hunger_cost', 4),
                min_happiness=lesson.get('min_happiness', 15),
                happiness_bonus=lesson.get('happiness_bonus', 5),
                wrong_happiness_penalty=lesson.get('wrong_happiness_penalty', 5),
                sort_order=index,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', lesson.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()

    if not HangmanWordItem.query.first():
        for index, word in enumerate(COCHON_PENDU_WORDS):
            db.session.add(HangmanWordItem(word=word, sort_order=index))
        db.session.commit()


def init_grain_market():
    """Cree la ligne singleton de la Bourse aux Grains si elle n'existe pas."""
    if not GrainMarket.query.first():
        db.session.add(
            GrainMarket(
                id=1,
                cursor_x=BOURSE_DEFAULT_POS,
                cursor_y=BOURSE_DEFAULT_POS,
            )
        )
        db.session.commit()
