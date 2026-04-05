from flask import Flask, session, request, render_template
import os
import logging
from sqlalchemy import inspect, event

logger = logging.getLogger(__name__)

from flask_session import Session

_server_session = Session()
_session_interface = None

from cli import register_cli_commands
from config.app_config import get_config_class
from extensions import db, limiter, migrate
from helpers.config import init_default_config
from helpers.veterinary import get_first_injured_pig
from services.auth_log_service import log_site_action
from routes import all_blueprints
from scheduler import start_scheduler, should_autostart_scheduler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app(config_name=None):
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
    config_class = get_config_class(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)

    # ── Securite ────────────────────────────────────────────────────────
    if not app.debug and app.config['SECRET_KEY'].startswith('dev-only'):
        logger.warning("SECRET_KEY non definie ! Utilisez une cle secrete en production.")

    # ── Sessions serveur (Flask-Session + SQLAlchemy) ────────────────────
    app.config['SESSION_SQLALCHEMY'] = db
    db_url = app.config['SQLALCHEMY_DATABASE_URI']

    db.init_app(app)
    if 'sqlite' in db_url:
        with app.app_context():
            @event.listens_for(db.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    migrate.init_app(app, db)
    limiter.init_app(app)
    global _session_interface
    if _session_interface is None:
        _server_session.init_app(app)
        _session_interface = app.session_interface
    else:
        app.session_interface = _session_interface

    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

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
            '/api/race/live-state',
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


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=port,
    )
