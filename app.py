from flask import Flask, session, request, render_template
import click
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import logging
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

from flask_session import Session

_server_session = Session()
_session_interface = None

from extensions import db, limiter, migrate
from models import (
    GameConfig, User, Pig, BalanceTransaction, GrainMarket, Trophy,
    CerealItem, TrainingItem, SchoolLessonItem, HangmanWordItem, PigAvatar,
    PokerTable, PokerPlayer, PokerHandHistory,
)
from data import PIG_ORIGINS, CEREALS, TRAININGS, SCHOOL_LESSONS, COCHON_PENDU_WORDS
from helpers import init_default_config, ensure_next_race, get_first_injured_pig
from services.finance_service import record_balance_transaction
from services.auth_log_service import purge_old_auth_events, log_site_action
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
        # Augmenter le timeout pour SQLite pour eviter les erreurs "database is locked"
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'connect_args': {'timeout': 30} # Attend jusqu'a 30 secondes
        }
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 60,
            'pool_recycle': 300,
        }
    app.config['SCHEDULER_ENABLED'] = os.environ.get('DERBY_DISABLE_SCHEDULER', '0') != '1'
    app.config['PIG_VITALS_COMMIT_INTERVAL_SECONDS'] = int(
        os.environ.get('PIG_VITALS_COMMIT_INTERVAL_SECONDS', '60')
    )
    app.config['AUTH_LOG_RETENTION_DAYS'] = int(os.environ.get('AUTH_LOG_RETENTION_DAYS', '180'))

    db.init_app(app)
    migrate.init_app(app, db)
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
    from flask import jsonify as _jsonify

    def _render_error_template(template_name, status_code):
        try:
            return render_template(template_name), status_code
        except Exception:
            logger.exception("Erreur pendant le rendu de %s", template_name)
            return (
                f"Erreur {status_code}. "
                "Le serveur rencontre un probleme temporaire.",
                status_code,
                {'Content-Type': 'text/plain; charset=utf-8'},
            )

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith('/api/'):
            return _jsonify({'error': 'Trop de requetes, ralentis un peu !'}), 429
        return _render_error_template('429.html', 429)

    @app.errorhandler(404)
    def not_found_error(e):
        return _render_error_template('404.html', 404)

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return _render_error_template('500.html', 500)

    # ── Logging structure ───────────────────────────────────────────────
    @app.after_request
    def log_request(response):
        ignored_prefixes = (
            '/static',
            '/health',
            '/admin/auth-logs',  # Eviter l'auto-bruit de la page de consultation.
            '/api/notifications/poll',
        )
        if request.path.startswith(ignored_prefixes) or request.path.startswith('/chat'):
            return response
        logger.info(
            "%s %s %s — user=%s",
            request.method, request.path, response.status_code,
            session.get('user_id', '-'),
        )
        try:
            log_site_action(
                user_id=session.get('user_id'),
                method=request.method,
                path=request.path,
                status_code=response.status_code,
            )
        except Exception:
            logger.exception("Impossible d'ecrire le log d'action pour %s %s", request.method, request.path)
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
            if inspect(db.engine).has_table('game_config'):
                init_default_config()
            else:
                logger.info("Table game_config absente: init_default_config différé après migrations.")
        except Exception as e:
            logger.exception("Erreur critique lors de l'initialisation DB: %s", e)
            raise

    if should_autostart_scheduler(app):
        start_scheduler(app)

    register_cli_commands(app)

    return app


def run_seeders(with_admin=True):
    """Regroupe tous les seeds applicatifs pour une exécution explicite."""
    if with_admin:
        ensure_admin_user()
    seed_users()
    ensure_balance_transaction_snapshots()
    ensure_next_race()
    _init_grain_market()
    seed_game_data()


def register_cli_commands(app):
    @app.cli.command('seed-db')
    @click.option('--with-admin/--without-admin', default=True, show_default=True)
    def seed_db_command(with_admin):
        """Peuple les données initiales de l'application."""
        run_seeders(with_admin=with_admin)
        click.echo('✅ Seed termine.')

    @app.cli.command('purge-auth-logs')
    @click.option('--days', default=None, type=int, help='Override retention days for this run.')
    def purge_auth_logs_command(days):
        """Supprime les événements d'authentification anciens."""
        retention_days = int(days or app.config.get('AUTH_LOG_RETENTION_DAYS', 180))
        deleted_count = purge_old_auth_events(retention_days)
        click.echo(f'🧹 Auth logs purgés: {deleted_count} (rétention: {retention_days} jours)')


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
    """Peuple les tables CerealItem, TrainingItem, SchoolLessonItem, HangmanWordItem depuis data.py
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

    if not HangmanWordItem.query.first():
        for i, word in enumerate(COCHON_PENDU_WORDS):
            db.session.add(HangmanWordItem(word=word, sort_order=i))
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
