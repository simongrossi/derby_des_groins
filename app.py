from flask import Flask, session
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os

from extensions import db
from models import (
    GameConfig, User, Pig, BalanceTransaction, GrainMarket, Trophy,
    CerealItem, TrainingItem, SchoolLessonItem,
)
from data import PIG_ORIGINS, CEREALS, TRAININGS, SCHOOL_LESSONS
from helpers import init_default_config, ensure_next_race, get_first_injured_pig
from services.finance_service import record_balance_transaction
from services.pig_service import apply_origin_bonus, generate_weight_kg_for_profile, clamp_pig_weight, create_preloaded_admin_pigs, build_unique_pig_name
from routes import all_blueprints
from scheduler import start_scheduler, should_autostart_scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
    app.config['SECRET_KEY'] = 'derby-des-groins-secret-2024'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///derby.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SCHEDULER_ENABLED'] = os.environ.get('DERBY_DISABLE_SCHEDULER', '0') != '1'

    db.init_app(app)

    for bp in all_blueprints:
        app.register_blueprint(bp)

    @app.context_processor
    def inject_injured_pig_nav():
        injured_pig_nav_id = None
        if 'user_id' in session:
            injured_pig = get_first_injured_pig(session.get('user_id'))
            injured_pig_nav_id = injured_pig.id if injured_pig else None
        return {'injured_pig_nav_id': injured_pig_nav_id}

    with app.app_context():
        db.create_all()
        migrate_db()
        init_default_config()
        seed_users()
        ensure_balance_transaction_snapshots()
        ensure_next_race()
        _init_grain_market()
        seed_game_data()

    if should_autostart_scheduler(app):
        start_scheduler(app)

    return app


def migrate_db():
    migrations = [
        ('participant', 'pig_id', 'INTEGER'),
        ('participant', 'owner_name', 'VARCHAR(80)'),
        ('pig', 'is_alive', 'BOOLEAN DEFAULT 1'),
        ('pig', 'death_date', 'DATETIME'),
        ('pig', 'death_cause', 'VARCHAR(30)'),
        ('pig', 'charcuterie_type', 'VARCHAR(50)'),
        ('pig', 'charcuterie_emoji', 'VARCHAR(10)'),
        ('pig', 'epitaph', 'VARCHAR(200)'),
        ('pig', 'challenge_mort_wager', 'FLOAT DEFAULT 0'),
        ('pig', 'max_races', 'INTEGER DEFAULT 80'),
        ('pig', 'rarity', 'VARCHAR(20) DEFAULT "commun"'),
        ('pig', 'origin_country', 'VARCHAR(30) DEFAULT "France"'),
        ('pig', 'origin_flag', 'VARCHAR(10) DEFAULT "🇫🇷"'),
        ('pig', 'last_school_at', 'DATETIME'),
        ('pig', 'last_fed_at', 'DATETIME'),
        ('pig', 'last_interaction_at', 'DATETIME'),
        ('pig', 'comeback_bonus_ready', 'BOOLEAN DEFAULT 0'),
        ('pig', 'school_sessions_completed', 'INTEGER DEFAULT 0'),
        ('pig', 'weight_kg', 'FLOAT DEFAULT 112.0'),
        ('pig', 'freshness', 'FLOAT DEFAULT 100.0'),
        ('pig', 'ever_bad_state', 'BOOLEAN DEFAULT 0'),
        ('pig', 'is_injured', 'BOOLEAN DEFAULT 0'),
        ('pig', 'injury_risk', 'FLOAT DEFAULT 10.0'),
        ('pig', 'vet_deadline', 'DATETIME'),
        ('pig', 'lineage_name', 'VARCHAR(80)'),
        ('pig', 'generation', 'INTEGER DEFAULT 1'),
        ('pig', 'lineage_boost', 'FLOAT DEFAULT 0'),
        ('pig', 'sire_id', 'INTEGER'),
        ('pig', 'dam_id', 'INTEGER'),
        ('pig', 'retired_into_heritage', 'BOOLEAN DEFAULT 0'),
        ('user', 'is_admin', 'BOOLEAN DEFAULT 0'),
        ('user', 'last_relief_at', 'DATETIME'),
        ('user', 'barn_heritage_bonus', 'FLOAT DEFAULT 0'),
        ('user', 'snack_shares_today', 'INTEGER DEFAULT 0'),
        ('user', 'snack_share_reset_at', 'DATETIME'),
        ('participant', 'strategy', 'INTEGER DEFAULT 50'),
        ('race', 'replay_json', 'TEXT'),
        ('course_plan', 'strategy', 'INTEGER DEFAULT 50'),
        ('auction', 'seller_id', 'INTEGER'),
        ('auction', 'source_pig_id', 'INTEGER'),
        ('auction', 'pig_weight', 'FLOAT DEFAULT 112.0'),
        ('auction', 'pig_origin', 'VARCHAR(30)'),
        ('auction', 'pig_origin_flag', 'VARCHAR(10)'),
        ('bet', 'bet_type', 'VARCHAR(20) DEFAULT "win"'),
        ('bet', 'selection_order', 'VARCHAR(240)'),
        ('user', 'last_daily_reward_at', 'DATETIME'),
        ('trophy', 'pig_name', 'VARCHAR(80)'),
    ]
    table_migrations = [
        """CREATE TABLE IF NOT EXISTS trophy (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            code VARCHAR(50) NOT NULL,
            label VARCHAR(80) NOT NULL,
            emoji VARCHAR(10) NOT NULL DEFAULT '🏆',
            description VARCHAR(255) NOT NULL,
            pig_name VARCHAR(80),
            earned_at DATETIME
        )""",
    ]
    index_migrations = [
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_trophy_user_code ON trophy(user_id, code)',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_bet_user_race ON bet(user_id, race_id)',
        'CREATE INDEX IF NOT EXISTS ix_auction_status_ends_at ON auction(status, ends_at)',
        'CREATE INDEX IF NOT EXISTS ix_race_status_scheduled_at ON race(status, scheduled_at)',
        'CREATE INDEX IF NOT EXISTS ix_pig_vet_deadline ON pig(is_injured, is_alive, vet_deadline)',
    ]
    with db.engine.connect() as conn:
        for statement in table_migrations:
            try:
                conn.execute(db.text(statement))
                conn.commit()
            except Exception:
                pass
        for table, col, col_type in migrations:
            try:
                conn.execute(db.text(f"SELECT {col} FROM {table} LIMIT 1"))
            except Exception:
                try:
                    conn.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass
        for statement in index_migrations:
            try:
                conn.execute(db.text(statement))
                conn.commit()
            except Exception:
                pass


def seed_users():
    default_users = [
        {'username': 'Emerson',    'pig_name': 'Groin de Tonnerre',  'emoji': '🐗', 'origin': 'Brésil'},
        {'username': 'Pascal',     'pig_name': 'Le Baron du Lard',   'emoji': '🐷', 'origin': 'France'},
        {'username': 'Simon',      'pig_name': 'Saucisse Turbo',     'emoji': '🌭', 'origin': 'Allemagne'},
        {'username': 'Edwin',      'pig_name': 'Porcinator',         'emoji': '🐽', 'origin': 'Angleterre'},
        {'username': 'Julien',     'pig_name': 'Flash McGroin',      'emoji': '🐖', 'origin': 'Japon'},
        {'username': 'Christophe', 'pig_name': 'Père Cochon',        'emoji': '🏆', 'origin': 'France', 'admin': True},
        {'username': 'admin',       'pig_name': 'Grand Admin',        'emoji': '👑', 'origin': 'France', 'admin': True, 'password': 'admin'},
    ]
    for u in default_users:
        existing = User.query.filter_by(username=u['username']).first()
        if existing:
            existing.password_hash = generate_password_hash(u.get('password', 'mdp1234'))
            if u.get('admin'):
                existing.is_admin = True
        else:
            origin_data = next((o for o in PIG_ORIGINS if o['country'] == u.get('origin', 'France')), PIG_ORIGINS[0])
            user = User(
                username=u['username'],
                password_hash=generate_password_hash(u.get('password', 'mdp1234')),
                balance=100.0,
                is_admin=u.get('admin', False)
            )
            db.session.add(user)
            db.session.flush()
            pig = Pig(
                user_id=user.id, name=build_unique_pig_name(u['pig_name'], fallback_prefix='Cochon'), emoji=u['emoji'],
                origin_country=origin_data['country'], origin_flag=origin_data['flag'],
                lineage_name=f"Maison {u['username']}",
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
            origin_data = next((o for o in PIG_ORIGINS if o['country'] == 'Belgique'), PIG_ORIGINS[0])
            demo_pig = Pig(
                user_id=demo_owner.id,
                name='Patient Zero',
                emoji='🩹',
                origin_country=origin_data['country'],
                origin_flag=origin_data['flag'],
                energy=62,
                hunger=58,
                happiness=54,
                is_injured=True,
                injury_risk=28.0,
                vet_deadline=datetime.utcnow() + timedelta(minutes=30),
                lineage_name=f"Maison {demo_owner.username}",
            )
            apply_origin_bonus(demo_pig, origin_data)
            demo_pig.weight_kg = clamp_pig_weight(118.0)
            db.session.add(demo_pig)
    db.session.commit()


def ensure_balance_transaction_snapshots():
    logged_user_ids = {
        user_id for (user_id,) in db.session.query(BalanceTransaction.user_id).distinct().all()
    }
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
    """Peuple les tables CerealItem, TrainingItem, SchoolLessonItem depuis data.py
    si elles sont vides (premier lancement uniquement)."""
    import json as _json

    if not CerealItem.query.first():
        for i, (key, c) in enumerate(CEREALS.items()):
            item = CerealItem(
                key=key, name=c['name'], emoji=c['emoji'], cost=c['cost'],
                description=c.get('description', ''),
                hunger_restore=c.get('hunger_restore', 0),
                energy_restore=c.get('energy_restore', 0),
                weight_delta=c.get('weight_delta', 0),
                valeur_fourragere=c.get('valeur_fourragere', 100),
                sort_order=i,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', c.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()

    if not TrainingItem.query.first():
        for i, (key, t) in enumerate(TRAININGS.items()):
            item = TrainingItem(
                key=key, name=t['name'], emoji=t['emoji'],
                description=t.get('description', ''),
                energy_cost=t.get('energy_cost', 0),
                hunger_cost=t.get('hunger_cost', 0),
                weight_delta=t.get('weight_delta', 0),
                min_happiness=t.get('min_happiness', 0),
                happiness_bonus=t.get('happiness_bonus', 0),
                sort_order=i,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', t.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()

    if not SchoolLessonItem.query.first():
        for i, (key, l) in enumerate(SCHOOL_LESSONS.items()):
            item = SchoolLessonItem(
                key=key, name=l['name'], emoji=l['emoji'],
                description=l.get('description', ''),
                question=l['question'],
                answers_json=_json.dumps(l['answers'], ensure_ascii=False),
                xp=l.get('xp', 20),
                wrong_xp=l.get('wrong_xp', 5),
                energy_cost=l.get('energy_cost', 10),
                hunger_cost=l.get('hunger_cost', 4),
                min_happiness=l.get('min_happiness', 15),
                happiness_bonus=l.get('happiness_bonus', 5),
                wrong_happiness_penalty=l.get('wrong_happiness_penalty', 5),
                sort_order=i,
            )
            for stat in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
                setattr(item, f'stat_{stat}', l.get('stats', {}).get(stat, 0.0))
            db.session.add(item)
        db.session.commit()


def _init_grain_market():
    """Cree la ligne singleton de la Bourse aux Grains si elle n'existe pas."""
    from data import BOURSE_DEFAULT_POS
    if not GrainMarket.query.first():
        db.session.add(GrainMarket(
            id=1,
            cursor_x=BOURSE_DEFAULT_POS,
            cursor_y=BOURSE_DEFAULT_POS,
        ))
        db.session.commit()


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
