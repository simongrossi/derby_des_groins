from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from zoneinfo import ZoneInfo
import os

db = SQLAlchemy()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # pas de limite globale par defaut
    storage_uri="memory://",    # en-memoire (suffisant pour single-process Gunicorn)
)

APP_TIMEZONE = ZoneInfo(os.environ.get('DERBY_TIMEZONE', 'Europe/Paris'))
