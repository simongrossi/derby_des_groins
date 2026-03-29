from flask import Flask, session, request
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

from flask_session import Session

_server_session = Session()
_session_interface = None

from extensions import db, limiter
from models import (
    GameConfig, User, Pig, BalanceTransaction, GrainMarket, Trophy,
    CerealItem, TrainingItem, SchoolLessonItem, PigAvatar,
    PokerTable, PokerPlayer, PokerHandHistory,
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

    # ── Securite ────────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 'dev-only-secret-change-me-in-production'
    )
    if not app.debug and app.config['SECRET_KEY'].startswith('dev-only'):
        logger.warning("SECRET_KEY non definie ! Utilisez une cle secrete en production.")

    # SESSION_COOKIE_SECURE ne doit être True QUE si le site est servi en HTTPS.
    # En HTTP (ex : localhost Docker), il doit être False sinon le navigateur
    # refuse d'envoyer le cookie → session perdue après chaque redirect.
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SECURE_COOKIES', 'false').lower() == 'true'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['TEMPLATES_AUTO_RELOAD'] = os.environ.get('FLASK_ENV') != 'production'

    # ── Base de donnees ─────────────────────────────────────────────────
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///derby.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Sessions serveur (Flask-Session + SQLAlchemy) ────────────────────
    app.config['SESSION_TYPE'] = 'sqlalchemy'
    app.config['SESSION_SQLALCHEMY'] = db
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_KEY_PREFIX'] = 'derby:'
    app.config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    if 'sqlite' in db_url:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 60,
            'pool_recycle': 300,
        }
    app.config['SCHEDULER_ENABLED'] = os.environ.get('DERBY_DISABLE_SCHEDULER', '0') != '1'

    db.init_app(app)
    limiter.init_app(app)
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

    global _session_interface
    if _session_interface is None:
        _server_session.init_app(app)
        _session_interface = app.session_interface
    else:
        app.session_interface = _session_interface

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    for bp in all_blueprints:
        app.register_blueprint(bp)

    # ── Rate limiting : page 429 personnalisee ───────────────────────────
    from flask import jsonify as _jsonify, render_template as _rt
    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith('/api/'):
            return _jsonify({'error': 'Trop de requetes, ralentis un peu !'}), 429
        return _rt('429.html'), 429

    @app.errorhandler(404)
    def not_found_error(e):
        return _rt('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return _rt('500.html'), 500

    # ── Logging structure ───────────────────────────────────────────────
    @app.after_request
    def log_request(response):
        if request.path.startswith('/static') or request.path == '/health':
            return response
        logger.info(
            "%s %s %s — user=%s",
            request.method, request.path, response.status_code,
            session.get('user_id', '-'),
        )
        return response

    @app.context_processor
    def inject_injured_pig_nav():
        injured_pig_nav_id = None
        if 'user_id' in session:
            # Cache en session pour eviter une requete DB a chaque page.
            # Invalide via session.pop('_injured_cache') quand une blessure change.
            cached = session.get('_injured_pig_id')
            cache_ts = session.get('_injured_cache_ts', 0)
            import time
            now = time.time()
            if cached is not None and (now - cache_ts) < 30:
                injured_pig_nav_id = cached if cached != 0 else None
            else:
                injured_pig = get_first_injured_pig(session.get('user_id'))
                injured_pig_nav_id = injured_pig.id if injured_pig else None
                session['_injured_pig_id'] = injured_pig_nav_id or 0
                session['_injured_cache_ts'] = now
        return {'injured_pig_nav_id': injured_pig_nav_id}

    with app.app_context():
        try:
            db.create_all()
            migrate_db()
            init_default_config()
        except Exception as e:
            logger.exception("Erreur critique lors de l'initialisation DB: %s", e)
            raise
        # Admin user commité en premier, de façon indépendante
        ensure_admin_user()
        try:
            seed_users()
            ensure_balance_transaction_snapshots()
            ensure_next_race()
            _init_grain_market()
            seed_game_data()
        except Exception as e:
            logger.exception("Erreur lors du seed (non bloquant pour admin): %s", e)

    if should_autostart_scheduler(app):
        start_scheduler(app)

    return app


def migrate_db():
    migrations = [
        ('participant', 'pig_id', 'INTEGER'),
        ('participant', 'owner_name', 'VARCHAR(80)'),
        ('pig', 'is_alive', 'BOOLEAN DEFAULT TRUE'),
        ('pig', 'death_date', 'DATETIME'),
        ('pig', 'death_cause', 'VARCHAR(30)'),
        ('pig', 'charcuterie_type', 'VARCHAR(50)'),
        ('pig', 'charcuterie_emoji', 'VARCHAR(10)'),
        ('pig', 'epitaph', 'VARCHAR(200)'),
        ('pig', 'challenge_mort_wager', 'FLOAT DEFAULT 0'),
        ('pig', 'max_races', 'INTEGER DEFAULT 80'),
        ('pig', 'rarity', "VARCHAR(20) DEFAULT 'commun'"),
        ('pig', 'origin_country', "VARCHAR(30) DEFAULT 'France'"),
        ('pig', 'origin_flag', "VARCHAR(10) DEFAULT '🇫🇷'"),
        ('pig', 'last_school_at', 'DATETIME'),
        ('pig', 'last_fed_at', 'DATETIME'),
        ('pig', 'last_interaction_at', 'DATETIME'),
        ('pig', 'comeback_bonus_ready', 'BOOLEAN DEFAULT FALSE'),
        ('pig', 'school_sessions_completed', 'INTEGER DEFAULT 0'),
        ('pig', 'weight_kg', 'FLOAT DEFAULT 112.0'),
        ('pig', 'freshness', 'FLOAT DEFAULT 100.0'),
        ('pig', 'ever_bad_state', 'BOOLEAN DEFAULT FALSE'),
        ('pig', 'is_injured', 'BOOLEAN DEFAULT FALSE'),
        ('pig', 'injury_risk', 'FLOAT DEFAULT 10.0'),
        ('pig', 'vet_deadline', 'DATETIME'),
        ('pig', 'lineage_name', 'VARCHAR(80)'),
        ('pig', 'generation', 'INTEGER DEFAULT 1'),
        ('pig', 'lineage_boost', 'FLOAT DEFAULT 0'),
        ('pig', 'sire_id', 'INTEGER'),
        ('pig', 'dam_id', 'INTEGER'),
        ('pig', 'retired_into_heritage', 'BOOLEAN DEFAULT FALSE'),
        ('user', 'email', 'VARCHAR(200)'),
        ('user', 'is_admin', 'BOOLEAN DEFAULT FALSE'),
        ('user', 'last_relief_at', 'DATETIME'),
        ('user', 'barn_heritage_bonus', 'FLOAT DEFAULT 0'),
        ('user', 'snack_shares_today', 'INTEGER DEFAULT 0'),
        ('user', 'snack_share_reset_at', 'DATETIME'),
        ('participant', 'strategy', 'INTEGER DEFAULT 50'),
        ('race', 'replay_json', 'TEXT'),
        ('course_plan', 'strategy', 'INTEGER DEFAULT 50'),
        ('course_plan', 'strategy_profile', 'TEXT DEFAULT \'{"phase_1": 35, "phase_2": 50, "phase_3": 80}\''),
        ('auction', 'seller_id', 'INTEGER'),
        ('auction', 'source_pig_id', 'INTEGER'),
        ('auction', 'pig_weight', 'FLOAT DEFAULT 112.0'),
        ('auction', 'pig_origin', 'VARCHAR(30)'),
        ('auction', 'pig_origin_flag', 'VARCHAR(10)'),
        ('auction', 'pig_avatar_url', 'VARCHAR(500)'),
        ('participant', 'avatar_url', 'VARCHAR(500)'),
        ('bet', 'bet_type', "VARCHAR(20) DEFAULT 'win'"),
        ('bet', 'selection_order', 'VARCHAR(240)'),
        ('user', 'last_daily_reward_at', 'DATETIME'),
        ('user', 'last_truffe_at', 'DATETIME'),
        ('user', 'truffes_balance', 'FLOAT DEFAULT 0.0'),
        ('trophy', 'pig_name', 'VARCHAR(80)'),
        ('trophy', 'trophy_key', 'VARCHAR(50)'),
        ('trophy', 'date_earned', 'DATETIME'),
        ('race', 'preview_segments_json', 'TEXT'),
        ('pig', 'avatar_id', 'INTEGER'),
        ('user', 'last_agenda_at', 'TIMESTAMP'),
        ('user', 'agenda_plays_today', "INTEGER DEFAULT 0 NOT NULL"),
    ]
    table_migrations = [
        'ALTER TABLE game_config ALTER COLUMN value TYPE TEXT',
    ]
    index_migrations = [
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_trophy_user_code ON trophy(user_id, code)',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_bet_user_race ON bet(user_id, race_id)',
        'CREATE INDEX IF NOT EXISTS ix_auction_status_ends_at ON auction(status, ends_at)',
        'CREATE INDEX IF NOT EXISTS ix_race_status_scheduled_at ON race(status, scheduled_at)',
        'CREATE INDEX IF NOT EXISTS ix_pig_vet_deadline ON pig(is_injured, is_alive, vet_deadline)',
        # Index supplementaires pour la performance
        'CREATE INDEX IF NOT EXISTS ix_pig_user_alive ON pig(user_id, is_alive)',
        'CREATE INDEX IF NOT EXISTS ix_bet_user_status ON bet(user_id, status)',
        'CREATE INDEX IF NOT EXISTS ix_user_username ON "user"(username)',
        'CREATE INDEX IF NOT EXISTS ix_participant_race_pig ON participant(race_id, pig_id)',
        'CREATE INDEX IF NOT EXISTS ix_balance_tx_user ON balance_transaction(user_id)',
        'CREATE INDEX IF NOT EXISTS ix_course_plan_user_sched ON course_plan(user_id, scheduled_at)',
        'CREATE INDEX IF NOT EXISTS ix_poker_player_table ON poker_player(table_id)',
        'CREATE INDEX IF NOT EXISTS ix_poker_player_user ON poker_player(user_id)',
        'CREATE INDEX IF NOT EXISTS ix_poker_hand_table ON poker_hand_history(table_id)',
    ]
    with db.engine.connect() as conn:
        for statement in table_migrations:
            try:
                conn.execute(db.text(statement))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning("Migration table echouee: %s — %s", statement[:80], e)
        for table, col, col_type in migrations:
            tbl = f'"{table}"'
            try:
                conn.execute(db.text(f"SELECT {col} FROM {tbl} LIMIT 1"))
                conn.rollback()
            except Exception:
                conn.rollback()
                try:
                    conn.execute(db.text(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.warning("Migration colonne echouee: %s.%s — %s", table, col, e)
        for statement in index_migrations:
            try:
                conn.execute(db.text(statement))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning("Migration index echouee: %s — %s", statement[:80], e)
        try:
            if db.engine.dialect.name == 'sqlite':
                conn.execute(db.text("""
                    UPDATE course_plan
                    SET strategy_profile = json_object(
                        'phase_1', COALESCE(strategy, 50),
                        'phase_2', COALESCE(strategy, 50),
                        'phase_3', COALESCE(strategy, 50)
                    )
                    WHERE strategy_profile IS NULL OR strategy_profile = ''
                """))
            else:
                conn.execute(db.text("""
                    UPDATE course_plan
                    SET strategy_profile = json_build_object(
                        'phase_1', COALESCE(strategy, 50),
                        'phase_2', COALESCE(strategy, 50),
                        'phase_3', COALESCE(strategy, 50)
                    )::text
                    WHERE strategy_profile IS NULL OR strategy_profile = ''
                """))
            conn.execute(db.text("""
                UPDATE trophy
                SET trophy_key = COALESCE(trophy_key, code),
                    date_earned = COALESCE(date_earned, earned_at)
            """))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.warning("Migration donnees echouee: %s", e)


def ensure_admin_user():
    """Garantit que le compte admin existe avec les bons credentials.
    Committé de façon indépendante pour ne pas être affecté par les autres seeds."""
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
            logger.info("[SEED] Compte 'admin' créé avec succès (admin/admin)")
        else:
            admin.is_admin = True
            db.session.commit()
            logger.info("[SEED] Compte 'admin' existant vérifié (is_admin=True)")
    except Exception as e:
        db.session.rollback()
        logger.error("[SEED] ERREUR CRITIQUE - impossible de créer le compte admin: %s", e)


def seed_users():
    default_users = [
        {'username': 'Emerson',    'pig_name': 'Groin de Tonnerre',  'emoji': '🐗', 'origin': 'Brésil'},
        {'username': 'Pascal',     'pig_name': 'Le Baron du Lard',   'emoji': '🐷', 'origin': 'France'},
        {'username': 'Simon',      'pig_name': 'Saucisse Turbo',     'emoji': '🌭', 'origin': 'Allemagne'},
        {'username': 'Edwin',      'pig_name': 'Porcinator',         'emoji': '🐽', 'origin': 'Angleterre'},
        {'username': 'Julien',     'pig_name': 'Flash McGroin',      'emoji': '🐖', 'origin': 'Japon'},
        {'username': 'Christophe', 'pig_name': 'Père Cochon',        'emoji': '🏆', 'origin': 'France', 'admin': True},
        # admin est géré séparément par ensure_admin_user()
        {'username': 'admin', 'pig_name': 'Grand Admin', 'emoji': '👑', 'origin': 'France', 'admin': True, 'password': os.environ.get('ADMIN_PASSWORD', 'admin')},
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
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=port,
    )
