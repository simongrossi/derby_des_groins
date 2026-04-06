from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

STAT_NAMES = ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral')

# Import sub-modules at the bottom to avoid circular import issues
from routes.admin import dashboard  # noqa
from routes.admin import economy    # noqa
from routes.admin import game_data  # noqa
from routes.admin import entities   # noqa
from routes.admin import operations # noqa
