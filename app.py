from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.config['SECRET_KEY'] = 'derby-des-groins-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///derby.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── MODÈLES ────────────────────────────────────────────────────────────────

class GameConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=100.0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bets = db.relationship('Bet', backref='user', lazy=True)

class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False, default='Mon Cochon')
    emoji = db.Column(db.String(10), default='🐷')

    # Compétences (0-100)
    vitesse = db.Column(db.Float, default=10.0)
    endurance = db.Column(db.Float, default=10.0)
    agilite = db.Column(db.Float, default=10.0)
    force = db.Column(db.Float, default=10.0)
    intelligence = db.Column(db.Float, default=10.0)
    moral = db.Column(db.Float, default=10.0)

    # État Tamagotchi (0-100)
    energy = db.Column(db.Float, default=80.0)
    hunger = db.Column(db.Float, default=60.0)
    happiness = db.Column(db.Float, default=70.0)

    # Progression
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    races_won = db.Column(db.Integer, default=0)
    races_entered = db.Column(db.Integer, default=0)

    # Durée de vie & Rareté & Origine
    max_races = db.Column(db.Integer, default=80)
    rarity = db.Column(db.String(20), default='commun')
    origin_country = db.Column(db.String(30), default='France')
    origin_flag = db.Column(db.String(10), default='🇫🇷')

    # Mort & Abattoir
    is_alive = db.Column(db.Boolean, default=True)
    death_date = db.Column(db.DateTime, nullable=True)
    death_cause = db.Column(db.String(30), nullable=True)
    charcuterie_type = db.Column(db.String(50), nullable=True)
    charcuterie_emoji = db.Column(db.String(10), nullable=True)
    epitaph = db.Column(db.String(200), nullable=True)

    # Challenge de la Mort
    challenge_mort_wager = db.Column(db.Float, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('User', backref=db.backref('pigs', lazy=True))

class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    winner_name = db.Column(db.String(80), nullable=True)
    winner_odds = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='upcoming')
    participants = db.relationship('Participant', backref='race', lazy=True)
    bets = db.relationship('Bet', backref='race', lazy=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), default='🐷')
    odds = db.Column(db.Float, nullable=False)
    win_probability = db.Column(db.Float, nullable=False)
    finish_position = db.Column(db.Integer, nullable=True)
    pig_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    owner_name = db.Column(db.String(80), nullable=True)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    pig_name = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    odds_at_bet = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    winnings = db.Column(db.Float, default=0.0)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Cochon en vente
    pig_name = db.Column(db.String(80), nullable=False)
    pig_emoji = db.Column(db.String(10), default='🐷')
    pig_vitesse = db.Column(db.Float, default=10.0)
    pig_endurance = db.Column(db.Float, default=10.0)
    pig_agilite = db.Column(db.Float, default=10.0)
    pig_force = db.Column(db.Float, default=10.0)
    pig_intelligence = db.Column(db.Float, default=10.0)
    pig_moral = db.Column(db.Float, default=10.0)
    pig_rarity = db.Column(db.String(20), default='commun')
    pig_max_races = db.Column(db.Integer, default=80)
    pig_origin = db.Column(db.String(30), default='France')
    pig_origin_flag = db.Column(db.String(10), default='🇫🇷')
    # Enchère
    starting_price = db.Column(db.Float, default=20.0)
    current_bid = db.Column(db.Float, default=0.0)
    bidder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    bidder = db.relationship('User', foreign_keys=[bidder_id], backref='bids_placed')
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    seller = db.relationship('User', foreign_keys=[seller_id])
    source_pig_id = db.Column(db.Integer, nullable=True)  # ID du cochon vendu par un joueur
    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, sold, expired

# ─── DONNÉES ────────────────────────────────────────────────────────────────

PIGS = [
    {"name": "Rillette", "emoji": "🐷"},
    {"name": "Côtelette", "emoji": "🥩"},
    {"name": "Jambonneau", "emoji": "🍖"},
    {"name": "Tirelire", "emoji": "🐽"},
    {"name": "Monsieur Lardon", "emoji": "🥓"},
    {"name": "Bacon Express", "emoji": "🚂"},
    {"name": "Groin d'Or", "emoji": "✨"},
    {"name": "P'tit Boudin", "emoji": "🌭"},
]

PIG_EMOJIS = ['🐷', '🐽', '🐖', '🐗', '🥓', '🍖', '🌭', '🏆']

PIG_ORIGINS = [
    {'country': 'France', 'flag': '🇫🇷', 'specialty': 'Moral', 'bonus_stat': 'moral', 'bonus': 5},
    {'country': 'Espagne', 'flag': '🇪🇸', 'specialty': 'Endurance', 'bonus_stat': 'endurance', 'bonus': 5},
    {'country': 'Italie', 'flag': '🇮🇹', 'specialty': 'Agilité', 'bonus_stat': 'agilite', 'bonus': 5},
    {'country': 'Allemagne', 'flag': '🇩🇪', 'specialty': 'Force', 'bonus_stat': 'force', 'bonus': 5},
    {'country': 'Angleterre', 'flag': '🇬🇧', 'specialty': 'Vitesse', 'bonus_stat': 'vitesse', 'bonus': 5},
    {'country': 'Japon', 'flag': '🇯🇵', 'specialty': 'Intelligence', 'bonus_stat': 'intelligence', 'bonus': 5},
    {'country': 'Brésil', 'flag': '🇧🇷', 'specialty': 'Vitesse', 'bonus_stat': 'vitesse', 'bonus': 4},
    {'country': 'Belgique', 'flag': '🇧🇪', 'specialty': 'Endurance', 'bonus_stat': 'endurance', 'bonus': 4},
    {'country': 'Portugal', 'flag': '🇵🇹', 'specialty': 'Agilité', 'bonus_stat': 'agilite', 'bonus': 4},
    {'country': 'Corée du Sud', 'flag': '🇰🇷', 'specialty': 'Intelligence', 'bonus_stat': 'intelligence', 'bonus': 4},
    {'country': 'Argentine', 'flag': '🇦🇷', 'specialty': 'Force', 'bonus_stat': 'force', 'bonus': 4},
    {'country': 'Mexique', 'flag': '🇲🇽', 'specialty': 'Moral', 'bonus_stat': 'moral', 'bonus': 4},
]

CEREALS = {
    'mais': {
        'name': 'Maïs', 'emoji': '🌽', 'cost': 5,
        'description': 'Base équilibrée, petit boost partout',
        'hunger_restore': 20, 'energy_restore': 5,
        'stats': {'vitesse': 0.5, 'endurance': 0.5, 'agilite': 0.5, 'force': 0.5, 'intelligence': 0.5, 'moral': 0.5},
        'valeur_fourragere': 100
    },
    'orge': {
        'name': 'Orge', 'emoji': '🌾', 'cost': 8,
        'description': '+Endurance +Force',
        'hunger_restore': 30, 'energy_restore': 8,
        'stats': {'endurance': 2.0, 'force': 1.5, 'vitesse': 0.3},
        'valeur_fourragere': 97
    },
    'ble': {
        'name': 'Blé', 'emoji': '🌿', 'cost': 10,
        'description': '+Force +Vitesse',
        'hunger_restore': 25, 'energy_restore': 5,
        'stats': {'force': 2.0, 'vitesse': 1.5, 'endurance': 0.5},
        'valeur_fourragere': 105
    },
    'seigle': {
        'name': 'Seigle', 'emoji': '🌱', 'cost': 7,
        'description': '+Agilité +Intelligence',
        'hunger_restore': 20, 'energy_restore': 5,
        'stats': {'agilite': 2.0, 'intelligence': 1.5},
        'valeur_fourragere': 102
    },
    'triticale': {
        'name': 'Triticale', 'emoji': '🍃', 'cost': 9,
        'description': '+Vitesse +Endurance',
        'hunger_restore': 25, 'energy_restore': 10,
        'stats': {'vitesse': 2.0, 'endurance': 1.5, 'moral': 0.5},
        'valeur_fourragere': 100
    },
    'avoine': {
        'name': 'Avoine', 'emoji': '🥣', 'cost': 6,
        'description': '+Moral +Agilité — récupération',
        'hunger_restore': 15, 'energy_restore': 15,
        'stats': {'moral': 2.5, 'agilite': 1.0},
        'valeur_fourragere': 82
    }
}

TRAININGS = {
    'sprint': {
        'name': 'Sprint', 'emoji': '💨',
        'description': 'Course courte et explosive',
        'energy_cost': 25, 'hunger_cost': 10,
        'stats': {'vitesse': 3.0, 'endurance': 1.0},
        'min_happiness': 20
    },
    'cross': {
        'name': 'Cross-country', 'emoji': '🏃',
        'description': 'Longue distance, mental d\'acier',
        'energy_cost': 35, 'hunger_cost': 15,
        'stats': {'endurance': 3.0, 'force': 1.0, 'vitesse': 0.5},
        'min_happiness': 20
    },
    'obstacles': {
        'name': 'Parcours d\'obstacles', 'emoji': '🏅',
        'description': 'Agilité et réflexes',
        'energy_cost': 30, 'hunger_cost': 10,
        'stats': {'agilite': 3.0, 'intelligence': 1.0},
        'min_happiness': 30
    },
    'sparring': {
        'name': 'Sparring', 'emoji': '🥊',
        'description': 'Combat amical, gagne en puissance',
        'energy_cost': 30, 'hunger_cost': 15,
        'stats': {'force': 3.0, 'moral': 0.5, 'endurance': 0.5},
        'min_happiness': 30
    },
    'puzzles': {
        'name': 'Puzzles & Stratégie', 'emoji': '🧩',
        'description': 'Entraînement cérébral',
        'energy_cost': 15, 'hunger_cost': 5,
        'stats': {'intelligence': 3.0, 'moral': 1.0},
        'min_happiness': 10
    },
    'repos': {
        'name': 'Repos & Détente', 'emoji': '😴',
        'description': 'Récupération complète',
        'energy_cost': -40, 'hunger_cost': 5,
        'stats': {'moral': 2.0},
        'happiness_bonus': 15,
        'min_happiness': 0
    }
}

CHARCUTERIE = [
    {'name': 'Jambon', 'emoji': '🍖', 'msg': 'Un beau jambon fumé au bois de hêtre'},
    {'name': 'Saucisson sec', 'emoji': '🌭', 'msg': 'Tranché finement, un régal à l\'apéro'},
    {'name': 'Rillettes', 'emoji': '🥫', 'msg': 'Étalées sur du pain de campagne'},
    {'name': 'Pâté de campagne', 'emoji': '🍞', 'msg': 'Avec cornichons et moutarde'},
    {'name': 'Boudin noir', 'emoji': '⬛', 'msg': 'Aux pommes, comme mémé'},
    {'name': 'Andouillette', 'emoji': '🌯', 'msg': 'AAAAA — pour les connaisseurs'},
    {'name': 'Chipolatas', 'emoji': '🥓', 'msg': 'Grillées au barbecue'},
    {'name': 'Lardons fumés', 'emoji': '🥘', 'msg': 'Dans une bonne tartiflette'},
    {'name': 'Côtes de porc', 'emoji': '🥩', 'msg': 'Marinées à la perfection'},
    {'name': 'Terrine', 'emoji': '🫕', 'msg': 'En bocal, souvenir éternel'},
    {'name': 'Jambon de Bayonne', 'emoji': '🏔️', 'msg': 'Séché 12 mois'},
    {'name': 'Grattons', 'emoji': '🍿', 'msg': 'Croustillants à l\'apéro'},
]

CHARCUTERIE_PREMIUM = [
    {'name': 'Jambon Grand Cru', 'emoji': '🏅', 'msg': 'Affiné par des années de course'},
    {'name': 'Pata Negra d\'Exception', 'emoji': '🖤', 'msg': 'Le summum du groin'},
    {'name': 'Saucisson Millésimé', 'emoji': '🍷', 'msg': 'Séché lentement, saveur incomparable'},
    {'name': 'Rillettes Prestige', 'emoji': '👑', 'msg': 'Recette secrète du Derby'},
]

EPITAPHS = [
    "Ci-gît {name}, qui courut plus vite que son ombre... mais pas assez vite.",
    "{name} repose ici. Son groin brillait plus que son palmarès.",
    "RIP {name} — Parti trop tôt, transformé trop vite. Groin groin... *silence*",
    "{name} galope désormais dans les pâturages éternels du Valhalla porcin.",
    "Ici dort {name}. {wins} victoires. Zéro regret. Beaucoup de charcuterie.",
    "En mémoire de {name}, dont le courage n'avait d'égal que sa malchance.",
    "{name} — Tu étais un cochon parmi les cochons. Le meilleur d'entre nous.",
    "Repose en paix {name}. Ton sacrifice nourrit les apéros de la nation.",
    "{name} n'est plus. Mais son jambon, lui, est éternel.",
    "Adieu {name}. Tu méritais mieux qu'un dernier virage vers l'abattoir.",
]

PIG_NAME_PREFIXES = [
    'Groin', 'Porcinet', 'Truffe', 'Lardon', 'Boudin', 'Saucisse',
    'Cochon', 'Museau', 'Grognon', 'Jambon', 'Pâté', 'Rillette',
    'Andouille', 'Terrine', 'Gratton', 'Porc',
]
PIG_NAME_SUFFIXES = [
    'de Feu', 'Doré', 'Sauvage', 'Express', 'Turbo', 'Suprême',
    'le Grand', 'le Terrible', 'le Brave', 'le Magnifique',
    'de l\'Ombre', 'du Tonnerre', 'Infernal', 'le Rapide',
    'de Fer', 'le Féroce', 'le Rusé', 'Légendaire',
]

RARITIES = {
    'commun': {
        'name': 'Commun', 'color': '#9ca3af', 'emoji': '⚪',
        'stats_range': (5, 20), 'max_races_range': (40, 60),
        'price_range': (15, 30), 'weight': 50
    },
    'rare': {
        'name': 'Rare', 'color': '#3b82f6', 'emoji': '🔵',
        'stats_range': (15, 35), 'max_races_range': (60, 80),
        'price_range': (30, 60), 'weight': 30
    },
    'epique': {
        'name': 'Épique', 'color': '#a855f7', 'emoji': '🟣',
        'stats_range': (25, 50), 'max_races_range': (80, 100),
        'price_range': (60, 120), 'weight': 15
    },
    'legendaire': {
        'name': 'Légendaire', 'color': '#f59e0b', 'emoji': '🟡',
        'stats_range': (40, 70), 'max_races_range': (100, 150),
        'price_range': (120, 250), 'weight': 5
    }
}

# ─── HELPERS CONFIG ─────────────────────────────────────────────────────────

def get_config(key, default=''):
    c = GameConfig.query.filter_by(key=key).first()
    return c.value if c else default

def set_config(key, value):
    c = GameConfig.query.filter_by(key=key).first()
    if c:
        c.value = str(value)
    else:
        db.session.add(GameConfig(key=key, value=str(value)))
    db.session.commit()

def init_default_config():
    defaults = {
        'race_hour': '14',
        'race_minute': '00',
        'market_day': '4',       # 0=lundi, 4=vendredi
        'market_hour': '13',
        'market_minute': '45',
        'market_duration': '120', # minutes
    }
    for k, v in defaults.items():
        if not GameConfig.query.filter_by(key=k).first():
            db.session.add(GameConfig(key=k, value=v))
    db.session.commit()

# ─── HELPERS COCHON ─────────────────────────────────────────────────────────

def calculate_pig_power(pig):
    return (pig.vitesse + pig.endurance + pig.agilite +
            pig.force + pig.intelligence + pig.moral) / 6

def xp_for_level(level):
    return int(100 * (level ** 1.5))

def check_level_up(pig):
    while pig.xp >= xp_for_level(pig.level + 1):
        pig.level += 1
        pig.happiness = min(100, pig.happiness + 10)

def update_pig_state(pig):
    now = datetime.utcnow()
    if not pig.last_updated:
        pig.last_updated = now
        return
    hours = (now - pig.last_updated).total_seconds() / 3600
    if hours < 0.01:
        return
    hours = min(hours, 24)
    pig.hunger = max(0, pig.hunger - hours * 2)
    if pig.hunger > 30:
        pig.energy = min(100, pig.energy + hours * 5)
    else:
        pig.energy = max(0, pig.energy - hours * 1)
    if pig.hunger < 15:
        pig.happiness = max(0, pig.happiness - hours * 3)
    elif pig.hunger < 30:
        pig.happiness = max(0, pig.happiness - hours * 1)
    elif pig.happiness < 60:
        pig.happiness = min(60, pig.happiness + hours * 0.3)
    pig.last_updated = now
    db.session.commit()

def get_or_create_pig(user):
    pig = Pig.query.filter_by(user_id=user.id, is_alive=True).first()
    if not pig:
        origin = random.choice(PIG_ORIGINS)
        pig = Pig(
            user_id=user.id,
            name=f"Cochon de {user.username}",
            emoji='🐷',
            origin_country=origin['country'],
            origin_flag=origin['flag']
        )
        # Bonus d'origine
        setattr(pig, origin['bonus_stat'], getattr(pig, origin['bonus_stat']) + origin['bonus'])
        db.session.add(pig)
        db.session.commit()
    return pig

def send_to_abattoir(pig, cause='abattoir'):
    charcuterie = random.choice(CHARCUTERIE)
    epitaph_template = random.choice(EPITAPHS)
    pig.is_alive = False
    pig.death_date = datetime.utcnow()
    pig.death_cause = cause
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = epitaph_template.format(name=pig.name, wins=pig.races_won)
    pig.challenge_mort_wager = 0
    db.session.commit()

def retire_pig_old_age(pig):
    charcuterie = random.choice(CHARCUTERIE_PREMIUM)
    pig.is_alive = False
    pig.death_date = datetime.utcnow()
    pig.death_cause = 'vieillesse'
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = f"{pig.name} a pris sa retraite après {pig.races_entered} courses glorieuses. Un cochon bien vieilli fait le meilleur jambon."
    pig.challenge_mort_wager = 0
    db.session.commit()

def get_dead_pigs_abattoir():
    return Pig.query.filter_by(is_alive=False).order_by(Pig.death_date.desc()).all()

def get_legendary_pigs():
    return Pig.query.filter(Pig.is_alive == False, Pig.races_won >= 3).order_by(Pig.races_won.desc()).all()

# ─── HELPERS BITGROIN ───────────────────────────────────────────────────────

def get_prix_moyen_groin():
    """Prix moyen du groin basé sur les dernières ventes du marché."""
    recent_sales = Auction.query.filter_by(status='sold') \
        .order_by(Auction.ends_at.desc()).limit(10).all()
    if recent_sales:
        return round(sum(a.current_bid for a in recent_sales) / len(recent_sales), 2)
    # Pas de ventes : estimer depuis les enchères actives
    active = Auction.query.filter_by(status='active').all()
    if active:
        return round(sum(a.starting_price for a in active) / len(active), 2)
    return 42.0  # Prix par défaut, la réponse à tout

# ─── HELPERS MARCHÉ ─────────────────────────────────────────────────────────

def get_next_market_time():
    """Retourne le prochain vendredi 13:45 (ou l'heure configurée)."""
    market_day = int(get_config('market_day', '4'))
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))

    now = datetime.now()
    # Trouver le prochain jour de marché
    days_ahead = market_day - now.weekday()
    if days_ahead < 0 or (days_ahead == 0 and now.hour * 60 + now.minute >= market_hour * 60 + market_minute + int(get_config('market_duration', '120'))):
        days_ahead += 7
    next_market = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_market

def is_market_open():
    """Le marché est-il ouvert en ce moment ?"""
    market_day = int(get_config('market_day', '4'))
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))
    duration = int(get_config('market_duration', '120'))

    now = datetime.now()
    if now.weekday() != market_day:
        return False
    market_start = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0)
    market_end = market_start + timedelta(minutes=duration)
    return market_start <= now <= market_end

def get_market_close_time():
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))
    duration = int(get_config('market_duration', '120'))
    now = datetime.now()
    market_start = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0)
    return market_start + timedelta(minutes=duration)

def generate_auction_pig():
    rarities = list(RARITIES.keys())
    weights = [RARITIES[r]['weight'] for r in rarities]
    rarity_key = random.choices(rarities, weights=weights, k=1)[0]
    rarity = RARITIES[rarity_key]

    name = f"{random.choice(PIG_NAME_PREFIXES)} {random.choice(PIG_NAME_SUFFIXES)}"
    emoji = random.choice(PIG_EMOJIS)
    origin = random.choice(PIG_ORIGINS)

    min_s, max_s = rarity['stats_range']
    min_r, max_r = rarity['max_races_range']
    min_p, max_p = rarity['price_range']

    # Calculer la fin : soit fin du marché si ouvert, soit dans 2h
    if is_market_open():
        ends = get_market_close_time()
    else:
        ends = datetime.utcnow() + timedelta(hours=2)

    stats = {s: round(random.uniform(min_s, max_s), 1) for s in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']}
    # Bonus d'origine
    stats[origin['bonus_stat']] = min(100, stats[origin['bonus_stat']] + origin['bonus'])

    return Auction(
        pig_name=name, pig_emoji=emoji,
        pig_vitesse=stats['vitesse'], pig_endurance=stats['endurance'],
        pig_agilite=stats['agilite'], pig_force=stats['force'],
        pig_intelligence=stats['intelligence'], pig_moral=stats['moral'],
        pig_rarity=rarity_key,
        pig_max_races=random.randint(min_r, max_r),
        pig_origin=origin['country'], pig_origin_flag=origin['flag'],
        starting_price=random.randint(min_p, max_p),
        current_bid=0,
        ends_at=ends,
        status='active'
    )

def resolve_auctions():
    now = datetime.utcnow()
    expired = Auction.query.filter(Auction.status == 'active', Auction.ends_at <= now).all()

    for auction in expired:
        if auction.bidder_id and auction.current_bid > 0:
            auction.status = 'sold'
            winner = User.query.get(auction.bidder_id)
            if winner:
                current_pig = Pig.query.filter_by(user_id=winner.id, is_alive=True).first()
                if current_pig:
                    send_to_abattoir(current_pig, cause='sacrifice')
                origin_data = next((o for o in PIG_ORIGINS if o['country'] == auction.pig_origin), PIG_ORIGINS[0])
                new_pig = Pig(
                    user_id=winner.id, name=auction.pig_name, emoji=auction.pig_emoji,
                    vitesse=auction.pig_vitesse, endurance=auction.pig_endurance,
                    agilite=auction.pig_agilite, force=auction.pig_force,
                    intelligence=auction.pig_intelligence, moral=auction.pig_moral,
                    max_races=auction.pig_max_races, rarity=auction.pig_rarity,
                    origin_country=auction.pig_origin, origin_flag=auction.pig_origin_flag,
                    energy=80, hunger=60, happiness=70
                )
                db.session.add(new_pig)
            # Payer le vendeur si c'est un joueur
            if auction.seller_id:
                seller = User.query.get(auction.seller_id)
                if seller:
                    seller.balance = round(seller.balance + auction.current_bid, 2)
        else:
            auction.status = 'expired'

    # Générer des cochons si marché ouvert et peu d'enchères
    if is_market_open():
        active_count = Auction.query.filter_by(status='active').count()
        while active_count < 5:
            db.session.add(generate_auction_pig())
            active_count += 1

    db.session.commit()

# ─── HELPERS COURSE ─────────────────────────────────────────────────────────

def get_next_race_time():
    """Retourne le prochain horaire de course (quotidien)."""
    race_hour = int(get_config('race_hour', '14'))
    race_minute = int(get_config('race_minute', '00'))
    now = datetime.now()
    today_race = now.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
    if now >= today_race:
        return today_race + timedelta(days=1)
    return today_race

def ensure_next_race():
    next_time = get_next_race_time()
    existing = Race.query.filter(
        Race.scheduled_at == next_time,
        Race.status.in_(['upcoming', 'open'])
    ).first()
    if existing:
        return existing

    race = Race(scheduled_at=next_time, status='open')
    db.session.add(race)
    db.session.flush()

    MAX_PARTICIPANTS = 8
    participants_list = []
    all_powers = []

    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.energy > 20, Pig.hunger > 20).all()
    for p in fit_pigs:
        update_pig_state(p)
    fit_pigs = [p for p in fit_pigs if p.energy > 20 and p.hunger > 20]
    fit_pigs.sort(key=lambda p: calculate_pig_power(p), reverse=True)
    fit_pigs = fit_pigs[:MAX_PARTICIPANTS]

    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        all_powers.append(power)
        owner = User.query.get(pig.user_id)
        p = Participant(
            race_id=race.id, name=pig.name, emoji=pig.emoji,
            pig_id=pig.id, owner_name=owner.username if owner else None,
            odds=0, win_probability=0
        )
        db.session.add(p)
        participants_list.append(p)

    npc_count = min(MAX_PARTICIPANTS - len(fit_pigs), len(PIGS))
    if npc_count > 0:
        player_names = {pig.name for pig in fit_pigs}
        available_npcs = [npc for npc in PIGS if npc['name'] not in player_names]
        selected_npcs = random.sample(available_npcs, min(npc_count, len(available_npcs)))
        for npc in selected_npcs:
            npc_power = random.uniform(20, 40)
            all_powers.append(npc_power)
            p = Participant(
                race_id=race.id, name=npc['name'], emoji=npc['emoji'],
                pig_id=None, owner_name=None, odds=0, win_probability=0
            )
            db.session.add(p)
            participants_list.append(p)

    total_power = sum(all_powers) if all_powers else 1
    margin = 1.15
    for i, p in enumerate(participants_list):
        prob = all_powers[i] / total_power
        p.win_probability = prob
        raw_odds = (1 / prob) * margin
        p.odds = max(1.5, round(raw_odds * 2) / 2)

    db.session.commit()
    return race

def run_race_if_needed():
    now = datetime.now()
    due_races = Race.query.filter(Race.status == 'open', Race.scheduled_at <= now).all()

    for race in due_races:
        participants = Participant.query.filter_by(race_id=race.id).all()
        if not participants:
            continue

        names = [p.name for p in participants]
        weights = [p.win_probability for p in participants]
        winner_name = random.choices(names, weights=weights, k=1)[0]

        order = list(participants)
        random.shuffle(order)
        order = [p for p in order if p.name == winner_name] + \
                [p for p in order if p.name != winner_name]
        for i, p in enumerate(order):
            p.finish_position = i + 1

        winner_participant = next(p for p in participants if p.name == winner_name)
        race.winner_name = winner_name
        race.winner_odds = winner_participant.odds
        race.finished_at = now
        race.status = 'finished'

        POSITION_XP = {1: 100, 2: 60, 3: 40, 4: 25, 5: 15, 6: 10, 7: 5, 8: 3}
        num_participants = len(order)

        for p in order:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if not pig or not pig.is_alive:
                    continue
                pig.races_entered += 1
                xp_gained = POSITION_XP.get(p.finish_position, 3)

                if pig.challenge_mort_wager > 0:
                    wager = pig.challenge_mort_wager
                    owner = User.query.get(pig.user_id)
                    if p.finish_position <= 3:
                        if owner:
                            owner.balance = round(owner.balance + wager * 3, 2)
                        xp_gained *= 2
                        pig.happiness = min(100, pig.happiness + 15)
                    elif p.finish_position == num_participants:
                        send_to_abattoir(pig, cause='challenge')
                        pig.challenge_mort_wager = 0
                        continue
                    pig.challenge_mort_wager = 0

                pig.xp += xp_gained
                if p.finish_position == 1:
                    pig.races_won += 1
                    pig.vitesse = min(100, pig.vitesse + random.uniform(0.5, 1.5))
                    pig.endurance = min(100, pig.endurance + random.uniform(0.5, 1.5))
                    pig.moral = min(100, pig.moral + 2)
                elif p.finish_position <= 3:
                    pig.moral = min(100, pig.moral + 1)
                    stat = random.choice(['vitesse', 'endurance', 'agilite', 'force', 'intelligence'])
                    setattr(pig, stat, min(100, getattr(pig, stat) + random.uniform(0.3, 0.8)))

                pig.energy = max(0, pig.energy - 15)
                pig.hunger = max(0, pig.hunger - 10)
                pig.last_updated = datetime.utcnow()
                check_level_up(pig)

                if pig.max_races and pig.races_entered >= pig.max_races:
                    retire_pig_old_age(pig)

        bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
        for bet in bets:
            if bet.pig_name == winner_name:
                winnings = round(bet.amount * bet.odds_at_bet, 2)
                bet.status = 'won'
                bet.winnings = winnings
                user = User.query.get(bet.user_id)
                if user:
                    user.balance = round(user.balance + winnings, 2)
            else:
                bet.status = 'lost'
                bet.winnings = 0.0

        db.session.commit()

# ─── ROUTES ─────────────────────────────────────────────────────────────────

JOURS_FR = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

@app.route('/')
def index():
    run_race_if_needed()
    ensure_next_race()

    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(5).all()

    user = None
    user_bets = []
    pig = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            pig = get_or_create_pig(user)
            if next_race:
                user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()

    participants = []
    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()

    prix_groin = get_prix_moyen_groin()

    return render_template('index.html',
        user=user, pig=pig, next_race=next_race,
        participants=participants, recent_races=recent_races,
        user_bets=user_bets, now=datetime.now(),
        prix_groin=prix_groin,
        market_open=is_market_open(),
        next_market=get_next_market_time()
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            return render_template('auth.html', error="Remplis tous les champs !", mode='register')
        if len(username) < 3:
            return render_template('auth.html', error="Pseudo trop court (min 3 caractères)", mode='register')
        if User.query.filter_by(username=username).first():
            return render_template('auth.html', error="Ce pseudo est déjà pris !", mode='register')
        user = User(username=username, password_hash=generate_password_hash(password), balance=100.0)
        db.session.add(user)
        db.session.flush()
        origin = random.choice(PIG_ORIGINS)
        pig = Pig(user_id=user.id, name=f"Cochon de {username}", emoji='🐷',
                  origin_country=origin['country'], origin_flag=origin['flag'])
        setattr(pig, origin['bonus_stat'], getattr(pig, origin['bonus_stat']) + origin['bonus'])
        db.session.add(pig)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('mon_cochon'))
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return render_template('auth.html', error="Identifiants incorrects !", mode='login')
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/bet', methods=['POST'])
def place_bet():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    run_race_if_needed()
    user = User.query.get(session['user_id'])
    race_id = request.form.get('race_id', type=int)
    pig_name = request.form.get('pig_name', '').strip()
    amount = request.form.get('amount', type=float)
    if not all([race_id, pig_name, amount]):
        return redirect(url_for('index'))
    race = Race.query.get(race_id)
    if not race or race.status != 'open':
        return redirect(url_for('index'))
    now = datetime.now()
    if (race.scheduled_at - now).total_seconds() < 30:
        return redirect(url_for('index'))
    participant = Participant.query.filter_by(race_id=race_id, name=pig_name).first()
    if not participant:
        return redirect(url_for('index'))
    if amount <= 0 or amount > user.balance:
        return redirect(url_for('index'))
    existing = Bet.query.filter_by(user_id=user.id, race_id=race_id, pig_name=pig_name).first()
    if existing:
        return redirect(url_for('index'))
    bet = Bet(user_id=user.id, race_id=race_id, pig_name=pig_name,
              amount=amount, odds_at_bet=participant.odds, status='pending')
    user.balance = round(user.balance - amount, 2)
    db.session.add(bet)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.placed_at.desc()).limit(50).all()
    return render_template('history.html', user=user, bets=bets)

# ─── ROUTES COCHON ──────────────────────────────────────────────────────────

@app.route('/mon-cochon')
def mon_cochon():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    update_pig_state(pig)
    races_remaining = max(0, (pig.max_races or 80) - pig.races_entered)
    age_days = (datetime.utcnow() - pig.created_at).days if pig.created_at else 0
    rarity_info = RARITIES.get(pig.rarity or 'commun', RARITIES['commun'])
    return render_template('mon_cochon.html',
        user=user, pig=pig, cereals=CEREALS, trainings=TRAININGS,
        xp_next=xp_for_level(pig.level + 1),
        pig_power=round(calculate_pig_power(pig), 1),
        pig_emojis=PIG_EMOJIS,
        races_remaining=races_remaining, age_days=age_days,
        rarity_info=rarity_info
    )

@app.route('/feed', methods=['POST'])
def feed():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    update_pig_state(pig)
    cereal_key = request.form.get('cereal')
    if cereal_key not in CEREALS:
        return redirect(url_for('mon_cochon'))
    cereal = CEREALS[cereal_key]
    if user.balance < cereal['cost']:
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('mon_cochon'))
    if pig.hunger >= 95:
        flash("Ton cochon n'a plus faim !", "warning")
        return redirect(url_for('mon_cochon'))
    user.balance = round(user.balance - cereal['cost'], 2)
    pig.hunger = min(100, pig.hunger + cereal['hunger_restore'])
    pig.energy = min(100, pig.energy + cereal.get('energy_restore', 0))
    for stat, boost in cereal['stats'].items():
        current = getattr(pig, stat, None)
        if current is not None:
            setattr(pig, stat, min(100, current + boost))
    pig.last_updated = datetime.utcnow()
    db.session.commit()
    flash(f"{cereal['emoji']} {cereal['name']} donné ! Miam !", "success")
    return redirect(url_for('mon_cochon'))

@app.route('/train', methods=['POST'])
def train():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    update_pig_state(pig)
    training_key = request.form.get('training')
    if training_key not in TRAININGS:
        return redirect(url_for('mon_cochon'))
    training = TRAININGS[training_key]
    if training['energy_cost'] > 0 and pig.energy < training['energy_cost']:
        flash("Ton cochon est trop fatigué !", "error")
        return redirect(url_for('mon_cochon'))
    if pig.hunger < training.get('hunger_cost', 0):
        flash("Ton cochon a trop faim pour s'entraîner !", "error")
        return redirect(url_for('mon_cochon'))
    if pig.happiness < training.get('min_happiness', 0):
        flash("Ton cochon n'est pas assez heureux !", "error")
        return redirect(url_for('mon_cochon'))
    pig.energy = max(0, min(100, pig.energy - training['energy_cost']))
    pig.hunger = max(0, pig.hunger - training.get('hunger_cost', 0))
    if 'happiness_bonus' in training:
        pig.happiness = min(100, pig.happiness + training['happiness_bonus'])
    for stat, boost in training['stats'].items():
        current = getattr(pig, stat, None)
        if current is not None:
            setattr(pig, stat, min(100, current + boost))
    pig.last_updated = datetime.utcnow()
    db.session.commit()
    flash(f"{training['emoji']} {training['name']} terminé !", "success")
    return redirect(url_for('mon_cochon'))

@app.route('/rename-pig', methods=['POST'])
def rename_pig():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    new_name = request.form.get('name', '').strip()
    new_emoji = request.form.get('emoji', '').strip()
    if new_name and 2 <= len(new_name) <= 30:
        pig.name = new_name
    if new_emoji and new_emoji in PIG_EMOJIS:
        pig.emoji = new_emoji
    db.session.commit()
    return redirect(url_for('mon_cochon'))

@app.route('/challenge-mort', methods=['POST'])
def challenge_mort():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    wager = request.form.get('wager', type=float)
    if not wager or wager < 10:
        flash("Mise minimum : 10 BG pour le Challenge de la Mort !", "error")
        return redirect(url_for('mon_cochon'))
    if wager > user.balance:
        flash("T'as pas les moyens de jouer avec la vie de ton cochon !", "error")
        return redirect(url_for('mon_cochon'))
    if pig.challenge_mort_wager > 0:
        flash("Un Challenge de la Mort est déjà en cours !", "warning")
        return redirect(url_for('mon_cochon'))
    if pig.energy <= 20 or pig.hunger <= 20:
        flash("Ton cochon est trop faible pour le Challenge !", "error")
        return redirect(url_for('mon_cochon'))
    user.balance = round(user.balance - wager, 2)
    pig.challenge_mort_wager = wager
    db.session.commit()
    flash(f"🔪 CHALLENGE DE LA MORT ACTIVÉ ! Mise : {wager:.0f} BG", "warning")
    return redirect(url_for('mon_cochon'))

@app.route('/cancel-challenge', methods=['POST'])
def cancel_challenge():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = get_or_create_pig(user)
    if pig.challenge_mort_wager <= 0:
        return redirect(url_for('mon_cochon'))
    refund = round(pig.challenge_mort_wager * 0.5, 2)
    user.balance = round(user.balance + refund, 2)
    pig.challenge_mort_wager = 0
    db.session.commit()
    flash(f"😰 Challenge annulé... Remboursement : {refund:.0f} BG (50%)", "warning")
    return redirect(url_for('mon_cochon'))

# ─── ROUTES MARCHÉ ──────────────────────────────────────────────────────────

@app.route('/marche')
def marche():
    resolve_auctions()

    active_auctions = Auction.query.filter_by(status='active').order_by(Auction.ends_at).all()
    recent_sold = Auction.query.filter_by(status='sold').order_by(Auction.ends_at.desc()).limit(5).all()

    user = None
    pig = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            pig = Pig.query.filter_by(user_id=user.id, is_alive=True).first()

    market_open = is_market_open()
    next_market = get_next_market_time()
    market_day_name = JOURS_FR[int(get_config('market_day', '4'))]
    market_time = f"{get_config('market_hour', '13')}h{get_config('market_minute', '45')}"
    prix_groin = get_prix_moyen_groin()

    return render_template('marche.html',
        user=user, pig=pig,
        auctions=active_auctions, recent_sold=recent_sold,
        rarities=RARITIES, now=datetime.utcnow(),
        market_open=market_open, next_market=next_market,
        market_day_name=market_day_name, market_time=market_time,
        prix_groin=prix_groin, origins=PIG_ORIGINS
    )

@app.route('/bid', methods=['POST'])
def bid():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    auction_id = request.form.get('auction_id', type=int)
    bid_amount = request.form.get('bid_amount', type=float)
    auction = Auction.query.get(auction_id)
    if not auction or auction.status != 'active':
        flash("Cette enchère n'est plus disponible !", "error")
        return redirect(url_for('marche'))
    if datetime.utcnow() >= auction.ends_at:
        flash("L'enchère est terminée !", "error")
        return redirect(url_for('marche'))
    min_bid = auction.current_bid + 5 if auction.current_bid > 0 else auction.starting_price
    if not bid_amount or bid_amount < min_bid:
        flash(f"Enchère minimum : {min_bid:.0f} BG !", "error")
        return redirect(url_for('marche'))
    if bid_amount > user.balance:
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('marche'))
    if auction.bidder_id:
        prev_bidder = User.query.get(auction.bidder_id)
        if prev_bidder:
            prev_bidder.balance = round(prev_bidder.balance + auction.current_bid, 2)
    user.balance = round(user.balance - bid_amount, 2)
    auction.current_bid = bid_amount
    auction.bidder_id = user.id
    db.session.commit()
    flash(f"Enchère placée : {bid_amount:.0f} BG sur {auction.pig_name} !", "success")
    return redirect(url_for('marche'))

@app.route('/sell-pig', methods=['POST'])
def sell_pig():
    """Mettre son cochon en vente sur le marché."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not is_market_open():
        flash("Le marché est fermé ! Reviens le jour du marché.", "error")
        return redirect(url_for('marche'))
    user = User.query.get(session['user_id'])
    pig = Pig.query.filter_by(user_id=user.id, is_alive=True).first()
    if not pig:
        flash("Tu n'as pas de cochon à vendre !", "error")
        return redirect(url_for('marche'))
    starting_price = request.form.get('price', type=float)
    if not starting_price or starting_price < 5:
        flash("Prix minimum : 5 BG !", "error")
        return redirect(url_for('marche'))

    auction = Auction(
        pig_name=pig.name, pig_emoji=pig.emoji,
        pig_vitesse=pig.vitesse, pig_endurance=pig.endurance,
        pig_agilite=pig.agilite, pig_force=pig.force,
        pig_intelligence=pig.intelligence, pig_moral=pig.moral,
        pig_rarity=pig.rarity or 'commun',
        pig_max_races=max(0, (pig.max_races or 80) - pig.races_entered),
        pig_origin=pig.origin_country or 'France',
        pig_origin_flag=pig.origin_flag or '🇫🇷',
        starting_price=starting_price,
        current_bid=0,
        seller_id=user.id,
        source_pig_id=pig.id,
        ends_at=get_market_close_time(),
        status='active'
    )
    # Retirer le cochon du joueur (il est en vente)
    pig.is_alive = False
    pig.death_cause = 'vendu'
    pig.death_date = datetime.utcnow()
    pig.charcuterie_type = 'En vente'
    pig.charcuterie_emoji = '🏷️'
    pig.epitaph = f"{pig.name} a été mis en vente au Marché aux Groins."
    db.session.add(auction)
    db.session.commit()
    flash(f"🏷️ {pig.name} est en vente pour {starting_price:.0f} BG minimum !", "success")
    return redirect(url_for('marche'))

# ─── ROUTES ABATTOIR & CIMETIÈRE ───────────────────────────────────────────

@app.route('/abattoir')
def abattoir():
    dead_pigs = [p for p in get_dead_pigs_abattoir() if p.death_cause != 'vendu']
    total_dead = len(dead_pigs)
    most_common = {}
    for p in dead_pigs:
        t = p.charcuterie_type or 'Inconnu'
        most_common[t] = most_common.get(t, 0) + 1
    top_product = max(most_common, key=most_common.get) if most_common else None
    last_victim = dead_pigs[0] if dead_pigs else None
    return render_template('abattoir.html',
        dead_pigs=dead_pigs, total_dead=total_dead,
        top_product=top_product, last_victim=last_victim,
        user=User.query.get(session.get('user_id'))
    )

@app.route('/cimetiere')
def cimetiere():
    legends = get_legendary_pigs()
    all_dead = [p for p in get_dead_pigs_abattoir() if p.death_cause != 'vendu']
    return render_template('cimetiere.html',
        legends=legends, total_dead=len(all_dead), total_legends=len(legends),
        user=User.query.get(session.get('user_id'))
    )

# ─── ROUTES ADMIN ──────────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash("Accès réservé aux administrateurs.", "error")
        return redirect(url_for('index'))

    users = User.query.all()
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(10).all()

    return render_template('admin.html',
        user=user, users=users,
        next_race=next_race, recent_races=recent_races,
        config={
            'race_hour': get_config('race_hour', '14'),
            'race_minute': get_config('race_minute', '00'),
            'market_day': get_config('market_day', '4'),
            'market_hour': get_config('market_hour', '13'),
            'market_minute': get_config('market_minute', '45'),
            'market_duration': get_config('market_duration', '120'),
        },
        jours=JOURS_FR
    )

@app.route('/admin/save', methods=['POST'])
def admin_save():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('index'))

    for key in ['race_hour', 'race_minute', 'market_day', 'market_hour', 'market_minute', 'market_duration']:
        val = request.form.get(key)
        if val is not None:
            set_config(key, val)

    flash("Configuration sauvegardée !", "success")
    return redirect(url_for('admin'))

@app.route('/admin/force-race', methods=['POST'])
def admin_force_race():
    """Force le lancement immédiat d'une course."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('index'))

    # Créer une course qui démarre maintenant
    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()

    MAX_PARTICIPANTS = 8
    participants_list = []
    all_powers = []

    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.energy > 20, Pig.hunger > 20).all()
    for p in fit_pigs:
        update_pig_state(p)
    fit_pigs = [p for p in fit_pigs if p.energy > 20 and p.hunger > 20]
    fit_pigs.sort(key=lambda p: calculate_pig_power(p), reverse=True)
    fit_pigs = fit_pigs[:MAX_PARTICIPANTS]

    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        all_powers.append(power)
        owner = User.query.get(pig.user_id)
        p = Participant(race_id=race.id, name=pig.name, emoji=pig.emoji,
                        pig_id=pig.id, owner_name=owner.username if owner else None,
                        odds=0, win_probability=0)
        db.session.add(p)
        participants_list.append(p)

    player_names = {pig.name for pig in fit_pigs}
    available_npcs = [npc for npc in PIGS if npc['name'] not in player_names]
    npc_count = min(MAX_PARTICIPANTS - len(fit_pigs), len(available_npcs))
    for npc in random.sample(available_npcs, npc_count):
        npc_power = random.uniform(20, 40)
        all_powers.append(npc_power)
        p = Participant(race_id=race.id, name=npc['name'], emoji=npc['emoji'],
                        pig_id=None, owner_name=None, odds=0, win_probability=0)
        db.session.add(p)
        participants_list.append(p)

    total_power = sum(all_powers) if all_powers else 1
    for i, p in enumerate(participants_list):
        prob = all_powers[i] / total_power
        p.win_probability = prob
        p.odds = max(1.5, round((1 / prob) * 1.15 * 2) / 2)

    db.session.commit()
    run_race_if_needed()
    flash("🏁 Course forcée ! Résultats disponibles.", "success")
    return redirect(url_for('admin'))

# ─── API ────────────────────────────────────────────────────────────────────

@app.route('/legendes-pop')
def legendes_pop():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    pop_pigs = [
        {'name': 'Babe', 'emoji': '🐑', 'desc': 'Le cochon devenu berger. Un cœur d\'or et une volonté de fer.', 'category': 'Film'},
        {'name': 'Miss Piggy', 'emoji': '🎀', 'desc': 'Diva absolue du Muppet Show. Maîtrise le karaté et la mode.', 'category': 'TV'},
        {'name': 'Spider-Cochon', 'emoji': '🕷️', 'desc': 'Aussi connu sous le nom de Harry Crotte. Marche au plafond (parfois).', 'category': 'Animation'},
        {'name': 'Naf-Naf, Nif-Nif & Nouf-Nouf', 'emoji': '🏠', 'desc': 'Les Trois Petits Cochons originels. Le loup s\'en casse encore les dents.', 'category': 'Conte'},
        {'name': 'Porcinet', 'emoji': '🧣', 'desc': 'Petit mais courageux (quand il n\'a pas peur). Meilleur ami de Winnie l\'Ourson.', 'category': 'Animation'},
        {'name': 'Pumbaa', 'emoji': '🐗', 'desc': 'Hakuna Matata ! Un phacochère à l\'appétit d\'ogre et au cœur tendre.', 'category': 'Animation'},
        {'name': 'Napoléon', 'emoji': '👑', 'desc': 'Leader incontesté de la Ferme des Animaux. Dictateur charismatique.', 'category': 'Littérature'},
        {'name': 'Bayonne', 'emoji': '🪙', 'desc': 'Le cochon tirelire de Toy Story. Cynique mais fidèle.', 'category': 'Animation'},
        {'name': 'Fleury Michon', 'emoji': '🍖', 'desc': 'L\'ambassadeur de la charcuterie. Une légende en barquette.', 'category': 'Industrie'},
        {'name': 'Justin Bridou', 'emoji': '🥖', 'desc': 'Le roi du saucisson, le vrai copain de l\'apéro.', 'category': 'Industrie'},
        {'name': 'Peppa Pig', 'emoji': '☔', 'desc': 'Adore sauter dans les flaques de boue. Icône mondiale indétrônable.', 'category': 'Animation'},
        {'name': 'Ganon', 'emoji': '🔱', 'desc': 'Le destructeur suprême (Zelda) sous sa forme de bête. Plutôt grognon.', 'category': 'Jeu Vidéo'},
    ]
    return render_template('legendes_pop.html', user=user, pop_pigs=pop_pigs)

@app.route('/api/countdown')
def api_countdown():
    run_race_if_needed()
    ensure_next_race()
    next_race = Race.query.filter_by(status='open').order_by(Race.scheduled_at).first()
    if not next_race:
        return jsonify({'seconds': 86400, 'race_id': None})
    now = datetime.now()
    seconds = max(0, int((next_race.scheduled_at - now).total_seconds()))
    return jsonify({'seconds': seconds, 'race_id': next_race.id})

@app.route('/api/latest_result')
def api_latest_result():
    race = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).first()
    if not race:
        return jsonify({'result': None})
    participants = Participant.query.filter_by(race_id=race.id).order_by(Participant.finish_position).all()
    return jsonify({
        'result': {
            'winner': race.winner_name, 'odds': race.winner_odds,
            'finished_at': race.finished_at.strftime('%H:%M') if race.finished_at else None,
            'positions': [
                {'name': p.name, 'emoji': p.emoji, 'pos': p.finish_position,
                 'is_player': p.pig_id is not None, 'owner': p.owner_name}
                for p in participants
            ]
        }
    })

@app.route('/api/pig')
def api_pig():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    pig = Pig.query.filter_by(user_id=user.id, is_alive=True).first()
    if not pig:
        return jsonify({'error': 'Pas de cochon'}), 404
    update_pig_state(pig)
    return jsonify({
        'name': pig.name, 'emoji': pig.emoji,
        'level': pig.level, 'xp': pig.xp,
        'xp_next': xp_for_level(pig.level + 1),
        'stats': {k: round(getattr(pig, k), 1) for k in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']},
        'energy': round(pig.energy, 1), 'hunger': round(pig.hunger, 1),
        'happiness': round(pig.happiness, 1),
        'power': round(calculate_pig_power(pig), 1),
        'origin': pig.origin_country, 'origin_flag': pig.origin_flag,
        'races_entered': pig.races_entered, 'races_won': pig.races_won
    })

@app.route('/api/prix-groin')
def api_prix_groin():
    return jsonify({'prix': get_prix_moyen_groin()})

# ─── INIT ───────────────────────────────────────────────────────────────────

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
        ('user', 'is_admin', 'BOOLEAN DEFAULT 0'),
        ('auction', 'seller_id', 'INTEGER'),
        ('auction', 'source_pig_id', 'INTEGER'),
        ('auction', 'pig_origin', 'VARCHAR(30)'),
        ('auction', 'pig_origin_flag', 'VARCHAR(10)'),
    ]
    with db.engine.connect() as conn:
        for table, col, col_type in migrations:
            try:
                conn.execute(db.text(f"SELECT {col} FROM {table} LIMIT 1"))
            except Exception:
                try:
                    conn.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
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
    ]
    for u in default_users:
        existing = User.query.filter_by(username=u['username']).first()
        if existing:
            existing.password_hash = generate_password_hash('mdp1234')
            if u.get('admin'):
                existing.is_admin = True
        else:
            origin_data = next((o for o in PIG_ORIGINS if o['country'] == u.get('origin', 'France')), PIG_ORIGINS[0])
            user = User(
                username=u['username'],
                password_hash=generate_password_hash('mdp1234'),
                balance=100.0,
                is_admin=u.get('admin', False)
            )
            db.session.add(user)
            db.session.flush()
            pig = Pig(
                user_id=user.id, name=u['pig_name'], emoji=u['emoji'],
                origin_country=origin_data['country'], origin_flag=origin_data['flag']
            )
            setattr(pig, origin_data['bonus_stat'], getattr(pig, origin_data['bonus_stat']) + origin_data['bonus'])
            db.session.add(pig)
    db.session.commit()

with app.app_context():
    db.create_all()
    migrate_db()
    init_default_config()
    seed_users()
    ensure_next_race()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
