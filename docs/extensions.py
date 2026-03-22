from flask_sqlalchemy import SQLAlchemy
from zoneinfo import ZoneInfo
import os

db = SQLAlchemy()

APP_TIMEZONE = ZoneInfo(os.environ.get('DERBY_TIMEZONE', 'Europe/Paris'))
