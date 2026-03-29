from routes.auth import auth_bp
from routes.main import main_bp
from routes.race import race_bp
from routes.pig import pig_bp
from routes.market import market_bp
from routes.abattoir import abattoir_bp
from routes.admin import admin_bp
from routes.api import api_bp
from routes.bourse import bourse_bp
from routes.blackjack import blackjack_bp
from routes.truffes import truffes_bp
from routes.galerie import galerie_bp
from routes.health import health_bp
from routes.agenda import agenda_bp
from routes.poker import poker_bp

all_blueprints = [
    auth_bp,
    main_bp,
    race_bp,
    pig_bp,
    market_bp,
    abattoir_bp,
    admin_bp,
    api_bp,
    bourse_bp,
    blackjack_bp,
    truffes_bp,
    galerie_bp,
    health_bp,
    agenda_bp,
    poker_bp,
]
