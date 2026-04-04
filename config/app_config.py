import os
from datetime import timedelta


def _env_flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return int(default)


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-secret-change-me-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///derby.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_TYPE = 'sqlalchemy'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_KEY_PREFIX = 'derby:'
    SESSION_SQLALCHEMY_TABLE = 'flask_sessions'
    SESSION_COOKIE_SECURE = _env_flag('SECURE_COOKIES', False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    TEMPLATES_AUTO_RELOAD = os.environ.get('FLASK_ENV') != 'production'
    SCHEDULER_ENABLED = not _env_flag('DERBY_DISABLE_SCHEDULER', False)
    PIG_VITALS_COMMIT_INTERVAL_SECONDS = _env_int('PIG_VITALS_COMMIT_INTERVAL_SECONDS', 60)
    AUTH_LOG_RETENTION_DAYS = _env_int('AUTH_LOG_RETENTION_DAYS', 180)

    DEBUG = _env_flag('FLASK_DEBUG', False)
    TESTING = False

    @classmethod
    def init_app(cls, app):
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        if 'sqlite' in db_url:
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True,
                'connect_args': {'timeout': 30},
            }
        else:
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True,
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 60,
                'pool_recycle': 300,
            }


class DevelopmentConfig(BaseConfig):
    DEBUG = _env_flag('FLASK_DEBUG', True)


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SCHEDULER_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False


CONFIG_BY_NAME = {
    'default': DevelopmentConfig,
    'development': DevelopmentConfig,
    'dev': DevelopmentConfig,
    'testing': TestingConfig,
    'test': TestingConfig,
    'production': ProductionConfig,
    'prod': ProductionConfig,
}


def get_config_class(config_name=None):
    selected_name = (
        config_name
        or os.environ.get('APP_ENV')
        or os.environ.get('FLASK_ENV')
        or 'default'
    ).lower()
    return CONFIG_BY_NAME.get(selected_name, DevelopmentConfig)
