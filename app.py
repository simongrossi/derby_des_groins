from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, func, or_, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import atexit
import random
import math
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.config['SECRET_KEY'] = 'derby-des-groins-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///derby.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_ENABLED'] = os.environ.get('DERBY_DISABLE_SCHEDULER', '0') != '1'

db = SQLAlchemy(app)
scheduler = None
APP_TIMEZONE = ZoneInfo(os.environ.get('DERBY_TIMEZONE', 'Europe/Paris'))

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
    last_relief_at = db.Column(db.DateTime, nullable=True)
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
    school_sessions_completed = db.Column(db.Integer, default=0)

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

    # Blessures & Vétérinaire
    is_injured = db.Column(db.Boolean, default=False)
    injury_risk = db.Column(db.Float, default=10.0)
    vet_deadline = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    last_school_at = db.Column(db.DateTime, nullable=True)

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
    bet_type = db.Column(db.String(20), default='win')
    selection_order = db.Column(db.String(240), nullable=True)
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

SCHOOL_COOLDOWN_MINUTES = 30

SCHOOL_LESSONS = {
    'strategie': {
        'name': 'Strategie de Virage',
        'emoji': '📐',
        'description': 'Apprendre a lire la piste et garder sa relance au bon moment.',
        'question': 'Dans un virage serre, quelle est la meilleure approche ?',
        'answers': [
            {'text': 'Ralentir legerement puis accelerer en sortie', 'correct': True, 'feedback': 'Bonne lecture. La sortie de virage fait gagner plus de terrain que l entree heroique.'},
            {'text': 'Foncer tout droit et compter sur la chance', 'correct': False, 'feedback': 'La chance ne tient pas la corde tres longtemps.'},
            {'text': 'S arreter pour observer les autres', 'correct': False, 'feedback': 'Observer c est bien, planter ses sabots au milieu de la piste un peu moins.'},
            {'text': 'Suivre le plus bruyant du groupe', 'correct': False, 'feedback': 'Le vacarme n est pas une tactique de course.'},
        ],
        'stats': {'intelligence': 2.5, 'agilite': 1.5},
        'xp': 24,
        'wrong_xp': 6,
        'energy_cost': 10,
        'hunger_cost': 4,
        'min_happiness': 15,
        'happiness_bonus': 5,
        'wrong_happiness_penalty': 6,
    },
    'nutrition': {
        'name': 'Nutrition du Champion',
        'emoji': '🥗',
        'description': 'Comprendre quand manger pour tenir jusqu au sprint final.',
        'question': 'Quel repas prepare le mieux un cochon juste avant la course ?',
        'answers': [
            {'text': 'Un repas equilibre et facile a digerer', 'correct': True, 'feedback': 'Exact. Du carburant utile, pas un festival du bidou.'},
            {'text': 'Une fondue XXL servie tres chaude', 'correct': False, 'feedback': 'Excellente idee pour une sieste, beaucoup moins pour un depart.'},
            {'text': 'Aucun repas pour courir leger', 'correct': False, 'feedback': 'Leger, oui. Debout au depart, beaucoup moins sur.'},
            {'text': 'Trois desserts et un soda surprise', 'correct': False, 'feedback': 'Ton cochon applaudit, son endurance beaucoup moins.'},
        ],
        'stats': {'endurance': 2.0, 'moral': 1.0},
        'xp': 22,
        'wrong_xp': 5,
        'energy_cost': 8,
        'hunger_cost': 3,
        'min_happiness': 10,
        'happiness_bonus': 4,
        'wrong_happiness_penalty': 5,
    },
    'mental': {
        'name': 'Mental d Acier',
        'emoji': '🧠',
        'description': 'Gerer la pression, la foule et les petits cochons qui fanfaronnent.',
        'question': 'Comment garder son sang-froid juste avant le depart ?',
        'answers': [
            {'text': 'Respirer, se concentrer et ignorer la provoc', 'correct': True, 'feedback': 'Parfait. Le calme fait plus de degats que les cris.'},
            {'text': 'Repondre a toutes les moqueries', 'correct': False, 'feedback': 'Ton cochon gagne peut-etre une dispute, pas une course.'},
            {'text': 'Dormir sur la ligne de depart', 'correct': False, 'feedback': 'Repos mal place. Ambiance sieste, resultat desastreux.'},
            {'text': 'Paniquer tres fort tres tot', 'correct': False, 'feedback': 'Technique peu recommandee par l academie porcine.'},
        ],
        'stats': {'moral': 2.0, 'intelligence': 1.5},
        'xp': 26,
        'wrong_xp': 6,
        'energy_cost': 9,
        'hunger_cost': 3,
        'min_happiness': 20,
        'happiness_bonus': 6,
        'wrong_happiness_penalty': 4,
    },
    'video': {
        'name': 'Analyse Video',
        'emoji': '🎥',
        'description': 'Revision des departs fulgurants et des depassements bien sentis.',
        'question': 'Quel detail faut-il surveiller sur une rediffusion de course ?',
        'answers': [
            {'text': 'Le timing des accelerations et les ouvertures dans le trafic', 'correct': True, 'feedback': 'Exact. Les details repetes font les champions reguliers.'},
            {'text': 'La couleur des bottes du soigneur', 'correct': False, 'feedback': 'Elegant, mais pas franchement decisif sur 400 metres.'},
            {'text': 'Le nombre de spectateurs au premier rang', 'correct': False, 'feedback': 'Flatteur pour l ego, inutile pour la trajectoire.'},
            {'text': 'La meilleure pose pour la photo d arrivee', 'correct': False, 'feedback': 'D abord la course, ensuite la couverture de magazine.'},
        ],
        'stats': {'vitesse': 1.5, 'agilite': 1.5, 'intelligence': 1.0},
        'xp': 24,
        'wrong_xp': 6,
        'energy_cost': 11,
        'hunger_cost': 4,
        'min_happiness': 15,
        'happiness_bonus': 5,
        'wrong_happiness_penalty': 5,
    },
}

STAT_LABELS = {
    'vitesse': 'VIT',
    'endurance': 'END',
    'agilite': 'AGI',
    'force': 'FOR',
    'intelligence': 'INT',
    'moral': 'MOR',
}

EMERGENCY_RELIEF_THRESHOLD = 10.0
EMERGENCY_RELIEF_AMOUNT = 20.0
EMERGENCY_RELIEF_HOURS = 12
SECOND_PIG_COST = 30.0
REPLACEMENT_PIG_COST = 15.0
BETTING_HOUSE_EDGE = 1.18
EXACTA_HOUSE_EDGE = 1.28
TIERCE_HOUSE_EDGE = 1.28
RACE_APPEARANCE_REWARD = 6.0
RACE_POSITION_REWARDS = {1: 25.0, 2: 12.0, 3: 6.0}
VET_RESPONSE_MINUTES = 5
MIN_INJURY_RISK = 8.0
MAX_INJURY_RISK = 40.0

BET_TYPES = {
    'win': {
        'label': 'Simple gagnant',
        'icon': '🥇',
        'selection_count': 1,
        'house_edge': BETTING_HOUSE_EDGE,
        'description': "Trouver uniquement le vainqueur.",
    },
    'exacta': {
        'label': 'Couple ordre',
        'icon': '🥈',
        'selection_count': 2,
        'house_edge': EXACTA_HOUSE_EDGE,
        'description': "Trouver les 2 premiers dans l'ordre.",
    },
    'tierce': {
        'label': 'Tierce ordre',
        'icon': '🎯',
        'selection_count': 3,
        'house_edge': TIERCE_HOUSE_EDGE,
        'description': "Trouver le podium complet dans l'ordre.",
    },
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
    stats = [pig.vitesse, pig.endurance, pig.agilite, pig.force, pig.intelligence, pig.moral]
    stat_score = sum(math.sqrt(max(0.0, stat) / 100.0) * 100 for stat in stats) / len(stats)
    condition_factor = 0.8 + (((pig.energy + pig.hunger + pig.happiness) / 3.0) / 100.0) * 0.4
    return round(stat_score * condition_factor, 2)

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

def get_cooldown_remaining(last_action, minutes):
    if not last_action:
        return 0
    elapsed = (datetime.utcnow() - last_action).total_seconds()
    return max(0, int(minutes * 60 - elapsed))

def format_duration_short(total_seconds):
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    if minutes and seconds:
        return f"{minutes}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"

def get_seconds_until(deadline):
    if not deadline:
        return 0
    return max(0, int((deadline - datetime.utcnow()).total_seconds()))

def get_active_listing_count(user):
    return Auction.query.filter_by(seller_id=user.id, status='active').count()

def get_pig_slot_count(user):
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    return active_pigs + get_active_listing_count(user)

def get_adoption_cost(user):
    slot_count = get_pig_slot_count(user)
    if slot_count >= 2:
        return None
    if Pig.query.filter_by(user_id=user.id, is_alive=True).count() == 0:
        return REPLACEMENT_PIG_COST
    return SECOND_PIG_COST

def get_market_unlock_progress(user):
    total_races = sum(p.races_entered for p in Pig.query.filter_by(user_id=user.id).all())
    account_age_hours = ((datetime.utcnow() - user.created_at).total_seconds() / 3600) if user.created_at else 0
    unlocked = account_age_hours >= 24 or total_races >= 3
    return unlocked, total_races, account_age_hours

def get_market_lock_reason(user):
    unlocked, total_races, account_age_hours = get_market_unlock_progress(user)
    if unlocked:
        return None
    remaining_races = max(0, 3 - total_races)
    remaining_hours = max(0, int(math.ceil(24 - account_age_hours)))
    return f"Le marché se débloque après 3 courses disputées ou 24h d'ancienneté. Il te reste {remaining_races} course(s) ou environ {remaining_hours}h."

def apply_origin_bonus(pig, origin):
    base_value = getattr(pig, origin['bonus_stat']) or 10.0
    setattr(pig, origin['bonus_stat'], base_value + origin['bonus'])

def supports_row_level_locking():
    try:
        return db.engine.dialect.name != 'sqlite'
    except Exception:
        return False

def apply_row_lock(query):
    if supports_row_level_locking():
        return query.with_for_update()
    return query

def adjust_user_balance(user_id, delta, minimum_balance=None):
    if delta == 0:
        return True

    stmt = update(User).where(User.id == user_id)
    if minimum_balance is not None:
        stmt = stmt.where(User.balance >= minimum_balance)
    stmt = stmt.values(balance=func.round(User.balance + delta, 2))

    result = db.session.execute(stmt)
    if result.rowcount != 1:
        db.session.rollback()
        return False
    return True

def debit_user_balance(user_id, amount):
    if amount <= 0:
        return False
    return adjust_user_balance(user_id, -amount, minimum_balance=amount)

def credit_user_balance(user_id, amount):
    if amount <= 0:
        return True
    return adjust_user_balance(user_id, amount)

def reserve_pig_challenge_slot(pig_id, wager):
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager <= 0)
        .values(challenge_mort_wager=wager)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False
    return True

def release_pig_challenge_slot(pig_id):
    pig = Pig.query.get(pig_id)
    if not pig or pig.challenge_mort_wager <= 0:
        return 0.0

    current_wager = round(pig.challenge_mort_wager or 0.0, 2)
    refund = round(current_wager * 0.5, 2)
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager == current_wager)
        .values(challenge_mort_wager=0.0)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return 0.0
    return refund

def maybe_grant_emergency_relief(user):
    if not user:
        return 0.0

    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=EMERGENCY_RELIEF_HOURS)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.balance < EMERGENCY_RELIEF_THRESHOLD,
            or_(User.last_relief_at.is_(None), User.last_relief_at <= cooldown_limit),
        )
        .values(
            balance=func.round(User.balance + EMERGENCY_RELIEF_AMOUNT, 2),
            last_relief_at=now,
        )
    )
    if result.rowcount != 1:
        db.session.rollback()
        return 0.0

    db.session.commit()
    return EMERGENCY_RELIEF_AMOUNT

def normalize_bet_type(bet_type):
    if bet_type in BET_TYPES:
        return bet_type
    return 'win'

def serialize_selection_ids(selection_ids):
    return ",".join(str(int(selection_id)) for selection_id in selection_ids)

def parse_selection_ids(raw_selection):
    if not raw_selection:
        return []
    selection_ids = []
    for raw_part in str(raw_selection).split(','):
        part = raw_part.strip()
        if not part:
            continue
        if not part.isdigit():
            return []
        selection_ids.append(int(part))
    return selection_ids

def format_bet_label(participants):
    return " -> ".join(participant.name for participant in participants)

def calculate_ordered_finish_probability(participants_by_id, ordered_ids):
    remaining_probabilities = {
        participant_id: max(participant.win_probability or 0.0, 0.0)
        for participant_id, participant in participants_by_id.items()
    }
    remaining_total = sum(remaining_probabilities.values())
    if remaining_total <= 0:
        return 0.0

    combined_probability = 1.0
    for participant_id in ordered_ids:
        current_probability = remaining_probabilities.get(participant_id)
        if current_probability is None or current_probability <= 0 or remaining_total <= 0:
            return 0.0
        combined_probability *= current_probability / remaining_total
        remaining_total -= current_probability
        del remaining_probabilities[participant_id]

    return combined_probability

def calculate_bet_odds(participants_by_id, ordered_ids, bet_type):
    bet_config = BET_TYPES[normalize_bet_type(bet_type)]
    probability = calculate_ordered_finish_probability(participants_by_id, ordered_ids)
    if probability <= 0:
        return 0.0
    raw_odds = (1 / probability) / bet_config['house_edge']
    return max(1.1, math.floor(raw_odds * 10) / 10)

def build_weighted_finish_order(participants):
    remaining = list(participants)
    finish_order = []
    while remaining:
        weights = [max(participant.win_probability or 0.0, 0.000001) for participant in remaining]
        chosen = random.choices(remaining, weights=weights, k=1)[0]
        finish_order.append(chosen)
        remaining.remove(chosen)
    return finish_order

def get_bet_selection_ids(bet, participants_by_id):
    selection_ids = parse_selection_ids(getattr(bet, 'selection_order', None))
    if selection_ids:
        return selection_ids
    matching_participant = next((participant for participant in participants_by_id.values() if participant.name == bet.pig_name), None)
    if matching_participant:
        return [matching_participant.id]
    return []

def refresh_race_betting_lines(race):
    if not race or race.status != 'open':
        return
    if Bet.query.filter_by(race_id=race.id).count() > 0:
        return
    participants = Participant.query.filter_by(race_id=race.id).all()
    if not participants:
        return
    total_prob = sum(p.win_probability for p in participants) or 1.0
    participants_by_id = {participant.id: participant for participant in participants}
    for participant in participants:
        participant.win_probability = participant.win_probability / total_prob
    for participant in participants:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')
    db.session.commit()

def get_user_active_pigs(user):
    """Retourne les cochons vivants. Crée uniquement le tout premier si nécessaire."""
    pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    if not pigs:
        if Pig.query.filter_by(user_id=user.id).count() > 0:
            return []
        origin = random.choice(PIG_ORIGINS)
        pig = Pig(
            user_id=user.id,
            name=f"Cochon de {user.username}",
            emoji='🐷',
            origin_country=origin['country'],
            origin_flag=origin['flag']
        )
        # Bonus d'origine
        apply_origin_bonus(pig, origin)
        db.session.add(pig)
        db.session.commit()
        return [pig]
    return pigs

def get_first_injured_pig(user_id):
    if not user_id:
        return None
    return Pig.query.filter_by(user_id=user_id, is_alive=True, is_injured=True).order_by(Pig.vet_deadline.asc(), Pig.id.asc()).first()

def check_vet_deadlines():
    now = datetime.utcnow()
    injured_pigs = Pig.query.filter_by(is_injured=True, is_alive=True).all()
    for pig in injured_pigs:
        if pig.vet_deadline and now > pig.vet_deadline:
            send_to_abattoir(pig, cause='blessure')

def send_to_abattoir(pig, cause='abattoir', commit=True):
    charcuterie = random.choice(CHARCUTERIE)
    epitaph_template = random.choice(EPITAPHS)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = cause
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = epitaph_template.format(name=pig.name, wins=pig.races_won)
    pig.challenge_mort_wager = 0
    if commit:
        db.session.commit()

def retire_pig_old_age(pig, commit=True):
    charcuterie = random.choice(CHARCUTERIE_PREMIUM)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
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

@app.context_processor
def inject_injured_pig_nav():
    injured_pig_nav_id = None
    if 'user_id' in session:
        injured_pig = get_first_injured_pig(session.get('user_id'))
        injured_pig_nav_id = injured_pig.id if injured_pig else None
    return {'injured_pig_nav_id': injured_pig_nav_id}

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
        auction = apply_row_lock(Auction.query.filter_by(id=auction.id)).first()
        if not auction or auction.status != 'active' or auction.ends_at > now:
            continue
        if auction.bidder_id and auction.current_bid > 0:
            auction.status = 'sold'
            winner = User.query.get(auction.bidder_id)
            if winner:
                active_pigs = Pig.query.filter_by(user_id=winner.id, is_alive=True).order_by(Pig.id).all()
                if len(active_pigs) >= 2:
                    # Sacrifier le plus ancien pour respecter la limite de 2
                    send_to_abattoir(active_pigs[0], cause='sacrifice', commit=False)
                
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
                credit_user_balance(auction.seller_id, auction.current_bid)
        else:
            auction.status = 'expired'
            if auction.seller_id and auction.source_pig_id:
                returned_pig = Pig.query.get(auction.source_pig_id)
                if returned_pig and returned_pig.user_id == auction.seller_id:
                    returned_pig.is_alive = True
                    returned_pig.death_date = None
                    returned_pig.death_cause = None
                    returned_pig.charcuterie_type = None
                    returned_pig.charcuterie_emoji = None
                    returned_pig.epitaph = None

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
        refresh_race_betting_lines(existing)
        return existing

    race = Race(scheduled_at=next_time, status='open')
    db.session.add(race)
    db.session.flush()

    MAX_PARTICIPANTS = 8
    participants_list = []
    all_powers = []
    player_powers = []

    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.is_injured == False, Pig.energy > 20, Pig.hunger > 20).all()
    for p in fit_pigs:
        update_pig_state(p)
    fit_pigs = [p for p in fit_pigs if not p.is_injured and p.energy > 20 and p.hunger > 20]
    fit_pigs.sort(key=lambda p: calculate_pig_power(p), reverse=True)
    fit_pigs = fit_pigs[:MAX_PARTICIPANTS]

    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        player_powers.append(power)
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
        avg_player_power = sum(player_powers) / len(player_powers) if player_powers else 34.0
        npc_min_power = max(22.0, avg_player_power * 0.9)
        npc_max_power = max(npc_min_power + 2.0, avg_player_power * 1.1)
        for npc in selected_npcs:
            npc_power = random.uniform(npc_min_power, npc_max_power)
            all_powers.append(npc_power)
            p = Participant(
                race_id=race.id, name=npc['name'], emoji=npc['emoji'],
                pig_id=None, owner_name=None, odds=0, win_probability=0
            )
            db.session.add(p)
            participants_list.append(p)

    total_power = sum(all_powers) if all_powers else 1
    for i, p in enumerate(participants_list):
        prob = all_powers[i] / total_power
        p.win_probability = prob
    db.session.flush()
    participants_by_id = {participant.id: participant for participant in participants_list}
    for participant in participants_list:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')

    db.session.commit()
    return race

def run_race_if_needed():
    now = datetime.now()
    due_races = Race.query.filter(Race.status == 'open', Race.scheduled_at <= now).all()

    for race in due_races:
        participants = Participant.query.filter_by(race_id=race.id).all()
        if not participants:
            continue

        participants_by_id = {participant.id: participant for participant in participants}
        order = build_weighted_finish_order(participants)
        for i, p in enumerate(order):
            p.finish_position = i + 1

        winner_participant = order[0]
        race.winner_name = winner_participant.name
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
                owner = User.query.get(pig.user_id)
                pig.races_entered += 1
                xp_gained = POSITION_XP.get(p.finish_position, 3)

                if owner:
                    reward = RACE_APPEARANCE_REWARD + RACE_POSITION_REWARDS.get(p.finish_position, 0.0)
                    credit_user_balance(owner.id, reward)

                if pig.challenge_mort_wager > 0:
                    wager = pig.challenge_mort_wager
                    if p.finish_position <= 3:
                        if owner:
                            credit_user_balance(owner.id, wager * 3)
                        xp_gained *= 2
                        pig.happiness = min(100, pig.happiness + 15)
                    elif p.finish_position == num_participants:
                        send_to_abattoir(pig, cause='challenge', commit=False)
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

                base_risk = (pig.injury_risk or MIN_INJURY_RISK) / 100.0
                fatigue_factor = 1.0 + max(0, (50 - pig.energy) / 100)
                hunger_factor = 1.0 + max(0, (30 - pig.hunger) / 100)
                effective_risk = min(0.70, base_risk * fatigue_factor * hunger_factor)
                if random.random() < effective_risk and not pig.is_injured:
                    pig.is_injured = True
                    pig.vet_deadline = datetime.utcnow() + timedelta(minutes=VET_RESPONSE_MINUTES)
                    pig.challenge_mort_wager = 0
                else:
                    pig.injury_risk = min(MAX_INJURY_RISK, (pig.injury_risk or MIN_INJURY_RISK) + random.uniform(0.3, 0.8))

                if pig.max_races and pig.races_entered >= pig.max_races:
                    retire_pig_old_age(pig, commit=False)

        bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
        finish_order_ids = [participant.id for participant in order]
        for bet in bets:
            bet_type = normalize_bet_type(getattr(bet, 'bet_type', None))
            expected_count = BET_TYPES[bet_type]['selection_count']
            selection_ids = get_bet_selection_ids(bet, participants_by_id)
            if len(selection_ids) == expected_count and finish_order_ids[:expected_count] == selection_ids:
                winnings = round(bet.amount * bet.odds_at_bet, 2)
                bet.status = 'won'
                bet.winnings = winnings
                credit_user_balance(bet.user_id, winnings)
            else:
                bet.status = 'lost'
                bet.winnings = 0.0

        db.session.commit()

    if due_races:
        ensure_next_race()

# ─── ROUTES ─────────────────────────────────────────────────────────────────

JOURS_FR = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

@app.route('/')
def index():
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(5).all()

    user = None
    user_bets = []
    pigs = []
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
            if next_race:
                user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()

    participants = []
    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()

    prix_groin = get_prix_moyen_groin()

    return render_template('index.html',
        user=user, pigs=pigs, next_race=next_race,
        participants=participants, recent_races=recent_races,
        user_bets=user_bets, now=datetime.now(),
        bet_types=BET_TYPES,
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
        apply_origin_bonus(pig, origin)
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

@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not current_password or not new_password or not confirm_password:
            flash("Remplis tous les champs pour changer ton mot de passe.", "warning")
        elif not check_password_hash(user.password_hash, current_password):
            flash("Ton mot de passe actuel est incorrect.", "error")
        elif len(new_password) < 6:
            flash("Ton nouveau mot de passe doit faire au moins 6 caractères.", "warning")
        elif current_password == new_password:
            flash("Choisis un mot de passe différent de l'actuel.", "warning")
        elif new_password != confirm_password:
            flash("La confirmation du nouveau mot de passe ne correspond pas.", "error")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Mot de passe mis à jour avec succès.", "success")
        return redirect(url_for('profil'))

    pigs = Pig.query.filter_by(user_id=user.id).order_by(Pig.created_at.desc()).all()
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.placed_at.desc()).all()
    active_listings = Auction.query.filter_by(seller_id=user.id, status='active').all()
    active_listing_ids = {listing.source_pig_id for listing in active_listings if listing.source_pig_id}

    active_pigs = [pig for pig in pigs if pig.is_alive]
    retired_pigs = [pig for pig in pigs if not pig.is_alive and pig.id not in active_listing_ids]
    total_races = sum((pig.races_entered or 0) for pig in pigs)
    total_wins = sum((pig.races_won or 0) for pig in pigs)
    total_school_sessions = sum((pig.school_sessions_completed or 0) for pig in pigs)
    legendary_pigs = sum(1 for pig in pigs if pig.rarity == 'legendaire')
    best_pig = max(pigs, key=lambda pig: ((pig.races_won or 0), (pig.level or 0), (pig.xp or 0)), default=None)

    won_bets = [bet for bet in bets if bet.status == 'won']
    lost_bets = [bet for bet in bets if bet.status == 'lost']
    pending_bets = [bet for bet in bets if bet.status == 'pending']
    settled_bets = won_bets + lost_bets

    total_staked = round(sum((bet.amount or 0.0) for bet in bets), 2)
    total_winnings = round(sum((bet.winnings or 0.0) for bet in won_bets), 2)
    total_profit = round(total_winnings - sum((bet.amount or 0.0) for bet in settled_bets), 2)
    race_win_rate = round((total_wins / total_races) * 100, 1) if total_races else 0.0
    bet_win_rate = round((len(won_bets) / len(settled_bets)) * 100, 1) if settled_bets else 0.0

    market_unlocked, market_progress_races, account_age_hours = get_market_unlock_progress(user)
    market_hours_left = max(0, int(math.ceil(24 - account_age_hours)))

    return render_template(
        'profil.html',
        user=user,
        pigs=pigs,
        active_pigs=active_pigs,
        retired_pigs=retired_pigs,
        best_pig=best_pig,
        total_races=total_races,
        total_wins=total_wins,
        total_school_sessions=total_school_sessions,
        legendary_pigs=legendary_pigs,
        race_win_rate=race_win_rate,
        bets=bets,
        won_bets=won_bets,
        lost_bets=lost_bets,
        pending_bets=pending_bets,
        total_staked=total_staked,
        total_winnings=total_winnings,
        total_profit=total_profit,
        bet_win_rate=bet_win_rate,
        bet_types=BET_TYPES,
        market_unlocked=market_unlocked,
        market_progress_races=market_progress_races,
        market_hours_left=market_hours_left,
        market_lock_reason=get_market_lock_reason(user),
        active_listing_count=get_active_listing_count(user),
        active_listing_ids=active_listing_ids,
    )

@app.route('/bet', methods=['POST'])
def place_bet():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))

    race_id = request.form.get('race_id', type=int)
    bet_type = normalize_bet_type(request.form.get('bet_type', 'win'))
    selection_ids = parse_selection_ids(request.form.get('selection_order', '').strip())
    amount = request.form.get('amount', type=float)
    if not all([race_id, amount]):
        flash("Ticket incomplet. Choisis ton pari et ta mise.", "warning")
        return redirect(url_for('index'))

    race = apply_row_lock(Race.query.filter_by(id=race_id)).first()
    if not race or race.status != 'open':
        flash("Cette course n'accepte plus de paris.", "warning")
        return redirect(url_for('index'))

    now = datetime.now()
    if (race.scheduled_at - now).total_seconds() < 30:
        flash("Les paris ferment 30 secondes avant le départ.", "warning")
        return redirect(url_for('index'))

    participants = Participant.query.filter_by(race_id=race_id).all()
    participants_by_id = {participant.id: participant for participant in participants}
    expected_count = BET_TYPES[bet_type]['selection_count']
    if len(participants) < expected_count:
        flash("Pas assez de partants pour ce type de ticket.", "warning")
        return redirect(url_for('index'))

    if len(selection_ids) != expected_count or len(set(selection_ids)) != expected_count:
        flash(f"Ce ticket demande {expected_count} cochon(s) distinct(s) dans l'ordre.", "warning")
        return redirect(url_for('index'))

    selected_participants = [participants_by_id.get(selection_id) for selection_id in selection_ids]
    if any(participant is None for participant in selected_participants):
        flash("Sélection invalide pour cette course.", "error")
        return redirect(url_for('index'))

    if amount <= 0:
        flash("Mise invalide pour ton solde actuel.", "error")
        return redirect(url_for('index'))

    existing = apply_row_lock(Bet.query.filter_by(user_id=user.id, race_id=race_id)).first()
    if existing:
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('index'))

    odds_at_bet = calculate_bet_odds(participants_by_id, selection_ids, bet_type)
    if odds_at_bet <= 0:
        flash("Impossible de calculer la cote de ce ticket.", "error")
        return redirect(url_for('index'))

    bet_label = format_bet_label(selected_participants)
    bet = Bet(
        user_id=user.id,
        race_id=race_id,
        pig_name=bet_label,
        bet_type=bet_type,
        selection_order=serialize_selection_ids(selection_ids),
        amount=amount,
        odds_at_bet=odds_at_bet,
        status='pending'
    )
    try:
        if not debit_user_balance(user.id, amount):
            flash("Pas assez de BitGroins pour valider ce ticket.", "error")
            return redirect(url_for('index'))
        db.session.add(bet)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('index'))

    flash(f"{BET_TYPES[bet_type]['icon']} Ticket {BET_TYPES[bet_type]['label'].lower()} validé sur {bet_label}.", "success")
    return redirect(url_for('index'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.placed_at.desc()).limit(50).all()
    return render_template('history.html', user=user, bets=bets, bet_types=BET_TYPES)

# ─── ROUTES COCHON ──────────────────────────────────────────────────────────

@app.route('/mon-cochon')
def mon_cochon():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    relief_amount = maybe_grant_emergency_relief(user)
    if relief_amount > 0:
        db.session.refresh(user)
        flash(f"🛟 Prime d'élevage d'urgence: +{relief_amount:.0f} BG pour relancer ton élevage.", "success")
    pigs = get_user_active_pigs(user)
    adoption_cost = get_adoption_cost(user)
    active_listing_count = get_active_listing_count(user)
    
    # Préparer les données pour chaque cochon
    pigs_data = []
    for p in pigs:
        update_pig_state(p)
        races_remaining = max(0, (p.max_races or 80) - p.races_entered)
        age_days = (datetime.utcnow() - p.created_at).days if p.created_at else 0
        rarity_info = RARITIES.get(p.rarity or 'commun', RARITIES['commun'])
        school_cooldown = get_cooldown_remaining(p.last_school_at, SCHOOL_COOLDOWN_MINUTES)
        vet_seconds_left = get_seconds_until(p.vet_deadline) if p.is_injured else 0
        pigs_data.append({
            'pig': p,
            'races_remaining': races_remaining,
            'age_days': age_days,
            'rarity_info': rarity_info,
            'power': round(calculate_pig_power(p), 1),
            'xp_next': xp_for_level(p.level + 1),
            'school_cooldown': school_cooldown,
            'school_cooldown_label': format_duration_short(school_cooldown),
            'vet_seconds_left': vet_seconds_left,
            'vet_deadline_label': format_duration_short(vet_seconds_left),
        })

    return render_template('mon_cochon.html',
        user=user, pigs_data=pigs_data, cereals=CEREALS, trainings=TRAININGS,
        school_lessons=SCHOOL_LESSONS, school_cooldown_minutes=SCHOOL_COOLDOWN_MINUTES,
        pig_emojis=PIG_EMOJIS, stat_labels=STAT_LABELS,
        adoption_cost=adoption_cost, active_listing_count=active_listing_count
    )

@app.route('/adopt-second-pig')
def adopt_second_pig():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    if get_pig_slot_count(user) >= 2:
        flash("Tu as déjà le maximum de cochons (2) !", "warning")
        return redirect(url_for('mon_cochon'))

    cost = get_adoption_cost(user)
    if cost is None:
        flash("Impossible d'adopter un nouveau cochon pour l'instant.", "warning")
        return redirect(url_for('mon_cochon'))
    if not debit_user_balance(user.id, cost):
        flash(f"Il te faut {cost:.0f} BG pour adopter un nouveau cochon !", "error")
        return redirect(url_for('mon_cochon'))

    origin = random.choice(PIG_ORIGINS)
    new_pig = Pig(
        user_id=user.id,
        name=f"Second de {user.username}" if active_pigs else f"Rescapé de {user.username}",
        emoji='🐖',
        origin_country=origin['country'],
        origin_flag=origin['flag']
    )
    apply_origin_bonus(new_pig, origin)
    db.session.add(new_pig)
    db.session.commit()
    if active_pigs:
        flash("✨ Nouveau cochon adopté ! Bienvenue dans l'écurie.", "success")
    else:
        flash("✨ Un cochon de secours rejoint ton élevage. C'est reparti.", "success")
    return redirect(url_for('mon_cochon'))

@app.route('/feed', methods=['POST'])
def feed():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
    
    update_pig_state(pig)
    cereal_key = request.form.get('cereal')
    if cereal_key not in CEREALS:
        return redirect(url_for('mon_cochon'))
    cereal = CEREALS[cereal_key]
    if pig.hunger >= 95:
        flash("Ton cochon n'a plus faim !", "warning")
        return redirect(url_for('mon_cochon'))
    if not debit_user_balance(user.id, cereal['cost']):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('mon_cochon'))

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
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
    
    update_pig_state(pig)
    if pig.is_injured:
        flash("Ton cochon est blessé. Passe d'abord par le vétérinaire.", "warning")
        return redirect(url_for('veterinaire', pig_id=pig.id))
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

@app.route('/school', methods=['POST'])
def school():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))

    update_pig_state(pig)
    if pig.is_injured:
        flash("L'école attendra. Ton cochon doit d'abord passer au vétérinaire.", "warning")
        return redirect(url_for('veterinaire', pig_id=pig.id))
    lesson_key = request.form.get('lesson')
    if lesson_key not in SCHOOL_LESSONS:
        flash("Cours introuvable !", "error")
        return redirect(url_for('mon_cochon'))

    lesson = SCHOOL_LESSONS[lesson_key]
    cooldown = get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES)
    if cooldown > 0:
        flash(f"La salle de classe est fermee pour l'instant. Reviens dans {format_duration_short(cooldown)}.", "warning")
        return redirect(url_for('mon_cochon'))

    answer_idx = request.form.get('answer_idx', type=int)
    answers = lesson['answers']
    if answer_idx is None or answer_idx < 0 or answer_idx >= len(answers):
        flash("Reponse invalide !", "error")
        return redirect(url_for('mon_cochon'))

    if pig.energy < lesson['energy_cost']:
        flash("Ton cochon est trop fatigue pour suivre ce cours.", "error")
        return redirect(url_for('mon_cochon'))
    if pig.hunger < lesson['hunger_cost']:
        flash("Ton cochon a trop faim pour se concentrer.", "error")
        return redirect(url_for('mon_cochon'))
    if pig.happiness < lesson['min_happiness']:
        flash("Ton cochon boude l'ecole aujourd'hui. Remonte-lui le moral d'abord.", "warning")
        return redirect(url_for('mon_cochon'))

    selected_answer = answers[answer_idx]
    pig.energy = max(0, pig.energy - lesson['energy_cost'])
    pig.hunger = max(0, pig.hunger - lesson['hunger_cost'])
    pig.last_school_at = datetime.utcnow()
    pig.school_sessions_completed = (pig.school_sessions_completed or 0) + 1

    if selected_answer['correct']:
        for stat, boost in lesson['stats'].items():
            current = getattr(pig, stat, None)
            if current is not None:
                setattr(pig, stat, min(100, current + boost))
        pig.xp += lesson['xp']
        pig.happiness = min(100, pig.happiness + lesson.get('happiness_bonus', 0))
        feedback_prefix = "Cours valide avec mention groin-tres-bien."
        category = "success"
    else:
        pig.xp += lesson.get('wrong_xp', 0)
        pig.happiness = max(0, pig.happiness - lesson.get('wrong_happiness_penalty', 0))
        feedback_prefix = "Le cours etait plus complique que prevu."
        category = "warning"

    pig.last_updated = datetime.utcnow()
    check_level_up(pig)
    db.session.commit()
    flash(f"{lesson['emoji']} {lesson['name']} - {feedback_prefix} {selected_answer['feedback']}", category)
    return redirect(url_for('mon_cochon'))

@app.route('/rename-pig', methods=['POST'])
def rename_pig():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
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
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
    
    update_pig_state(pig)
    if pig.is_injured:
        flash("Impossible d'inscrire un cochon blessé au Challenge de la Mort.", "error")
        return redirect(url_for('veterinaire', pig_id=pig.id))
    wager = request.form.get('wager', type=float)
    if not wager or wager < 10:
        flash("Mise minimum : 10 BG pour le Challenge de la Mort !", "error")
        return redirect(url_for('mon_cochon'))
    if pig.challenge_mort_wager > 0:
        flash("Tu es déjà inscrit au Challenge de la Mort !", "warning")
        return redirect(url_for('mon_cochon'))
    if pig.energy <= 20 or pig.hunger <= 20:
        flash("Ton cochon est trop faible pour le Challenge !", "error")
        return redirect(url_for('mon_cochon'))

    if not debit_user_balance(user.id, wager):
        flash("T'as pas les moyens de jouer avec la vie de ton cochon !", "error")
        return redirect(url_for('mon_cochon'))
    if not reserve_pig_challenge_slot(pig.id, wager):
        db.session.rollback()
        flash("Tu es déjà inscrit au Challenge de la Mort !", "warning")
        return redirect(url_for('mon_cochon'))

    if commit:
        db.session.commit()
    flash(f"💀 {pig.name} inscrit au Challenge de la Mort ({wager:.0f} BG) ! Bonne chance...", "success")
    return redirect(url_for('mon_cochon'))

@app.route('/cancel-challenge', methods=['POST'])
def cancel_challenge():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
    
    if pig.challenge_mort_wager <= 0:
        return redirect(url_for('mon_cochon'))

    refund = release_pig_challenge_slot(pig.id)
    if refund <= 0:
        flash("Le challenge a déjà été annulé ou réglé ailleurs.", "warning")
        return redirect(url_for('mon_cochon'))
    credit_user_balance(user.id, refund)
    db.session.commit()
    flash(f"😰 Challenge annulé pour {pig.name}... Remboursement : {refund:.0f} BG (50%)", "warning")
    return redirect(url_for('mon_cochon'))

@app.route('/sacrifice-pig', methods=['POST'])
def sacrifice_pig():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('mon_cochon'))
    
    send_to_abattoir(pig, cause='sacrifice_volontaire')
    flash(f"🔪 {pig.name} a été envoyé à l'abattoir volontairement. Paix à ses côtelettes.", "warning")
    return redirect(url_for('mon_cochon'))

# ─── ROUTES MARCHÉ ──────────────────────────────────────────────────────────

@app.route('/marche')
def marche():
    active_auctions = Auction.query.filter_by(status='active').order_by(Auction.ends_at).all()
    recent_sold = Auction.query.filter_by(status='sold').order_by(Auction.ends_at.desc()).limit(5).all()

    user = None
    pigs = [] # Initialize pigs list
    market_access = False
    market_lock_reason = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            # Get all active pigs for the user to potentially sell
            pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
            market_access = get_market_unlock_progress(user)[0]
            market_lock_reason = get_market_lock_reason(user)

    market_open = is_market_open()
    next_market = get_next_market_time()
    market_day_name = JOURS_FR[int(get_config('market_day', '4'))]
    market_time = f"{get_config('market_hour', '13')}h{get_config('market_minute', '45')}"
    prix_groin = get_prix_moyen_groin()

    return render_template('marche.html',
        user=user, pigs=pigs, # Pass all pigs for the user
        auctions=active_auctions, recent_sold=recent_sold,
        rarities=RARITIES, now=datetime.utcnow(),
        market_open=market_open, next_market=next_market,
        market_day_name=market_day_name, market_time=market_time,
        prix_groin=prix_groin, origins=PIG_ORIGINS,
        market_access=market_access, market_lock_reason=market_lock_reason
    )

@app.route('/bid', methods=['POST'])
def bid():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not get_market_unlock_progress(user)[0]:
        flash(get_market_lock_reason(user), "warning")
        return redirect(url_for('marche'))
    auction_id = request.form.get('auction_id', type=int)
    bid_amount = request.form.get('bid_amount', type=float)
    auction = apply_row_lock(Auction.query.filter_by(id=auction_id)).first()
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

    if not debit_user_balance(user.id, bid_amount):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('marche'))

    previous_bidder_id = auction.bidder_id
    previous_bid_amount = round(auction.current_bid or 0.0, 2)
    auction_conditions = [
        Auction.id == auction.id,
        Auction.status == 'active',
        Auction.ends_at > datetime.utcnow(),
        Auction.current_bid == previous_bid_amount,
    ]
    if previous_bidder_id is None:
        auction_conditions.append(Auction.bidder_id.is_(None))
    else:
        auction_conditions.append(Auction.bidder_id == previous_bidder_id)

    result = db.session.execute(
        update(Auction)
        .where(*auction_conditions)
        .values(current_bid=bid_amount, bidder_id=user.id)
    )
    if result.rowcount != 1:
        db.session.rollback()
        flash("Quelqu'un a enchéri juste avant toi. Recharge le marché et retente.", "warning")
        return redirect(url_for('marche'))

    if previous_bidder_id and previous_bid_amount > 0:
        credit_user_balance(previous_bidder_id, previous_bid_amount)

    db.session.commit()
    flash(f"Enchère placée : {bid_amount:.0f} BG sur {auction.pig_name} !", "success")
    return redirect(url_for('marche'))

@app.route('/sell-pig', methods=['POST'])
def sell_pig():
    """Mettre son cochon en vente sur le marché."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not get_market_unlock_progress(user)[0]:
        flash(get_market_lock_reason(user), "warning")
        return redirect(url_for('marche'))
    if not is_market_open():
        flash("Le marché est fermé ! Reviens le jour du marché.", "error")
        return redirect(url_for('marche'))
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.filter_by(id=pig_id, user_id=user.id, is_alive=True).first()
    if not pig:
        flash("Tu n'as pas ce cochon ou il n'est plus disponible !", "error")
        return redirect(url_for('marche'))
    if pig.is_injured:
        flash("Impossible de vendre un cochon blessé. Il doit d'abord voir le vétérinaire.", "warning")
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
    player_powers = []

    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.is_injured == False, Pig.energy > 20, Pig.hunger > 20).all()
    for p in fit_pigs:
        update_pig_state(p)
    fit_pigs = [p for p in fit_pigs if not p.is_injured and p.energy > 20 and p.hunger > 20]
    fit_pigs.sort(key=lambda p: calculate_pig_power(p), reverse=True)
    fit_pigs = fit_pigs[:MAX_PARTICIPANTS]

    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        player_powers.append(power)
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
    avg_player_power = sum(player_powers) / len(player_powers) if player_powers else 34.0
    npc_min_power = max(22.0, avg_player_power * 0.9)
    npc_max_power = max(npc_min_power + 2.0, avg_player_power * 1.1)
    for npc in random.sample(available_npcs, npc_count):
        npc_power = random.uniform(npc_min_power, npc_max_power)
        all_powers.append(npc_power)
        p = Participant(race_id=race.id, name=npc['name'], emoji=npc['emoji'],
                        pig_id=None, owner_name=None, odds=0, win_probability=0)
        db.session.add(p)
        participants_list.append(p)

    total_power = sum(all_powers) if all_powers else 1
    for i, p in enumerate(participants_list):
        prob = all_powers[i] / total_power
        p.win_probability = prob
    db.session.flush()
    participants_by_id = {participant.id: participant for participant in participants_list}
    for participant in participants_list:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')

    db.session.commit()
    run_race_if_needed()
    flash("🏁 Course forcée ! Résultats disponibles.", "success")
    return redirect(url_for('admin'))

# ─── API ────────────────────────────────────────────────────────────────────

@app.route('/veterinaire/<int:pig_id>')
def veterinaire(pig_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return redirect(url_for('mon_cochon'))
    if not pig.is_alive:
        return redirect(url_for('cimetiere'))
    if not pig.is_injured:
        return redirect(url_for('mon_cochon'))
    seconds_left = get_seconds_until(pig.vet_deadline)
    return render_template('veterinaire.html', user=user, pig=pig, seconds_left=seconds_left)

@app.route('/veterinaire')
def veterinaire_index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    injured_pig = get_first_injured_pig(user.id)
    if injured_pig:
        return redirect(url_for('veterinaire', pig_id=injured_pig.id))

    pigs = get_user_active_pigs(user)
    pigs_data = []
    for pig in pigs:
        update_pig_state(pig)
        injury_risk = round(pig.injury_risk or MIN_INJURY_RISK, 1)
        pigs_data.append({
            'pig': pig,
            'injury_risk': injury_risk,
            'power': round(calculate_pig_power(pig), 1),
            'status': 'eleve' if injury_risk > 25 else ('modere' if injury_risk > 15 else 'faible'),
        })

    pigs_data.sort(key=lambda item: item['injury_risk'], reverse=True)
    avg_risk = round(sum(item['injury_risk'] for item in pigs_data) / len(pigs_data), 1) if pigs_data else 0.0
    max_risk = max((item['injury_risk'] for item in pigs_data), default=0.0)

    return render_template(
        'veterinaire_lobby.html',
        user=user,
        pigs_data=pigs_data,
        avg_risk=avg_risk,
        max_risk=max_risk,
    )

@app.route('/api/vet/solve', methods=['POST'])
def vet_solve():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    payload = request.get_json(silent=True) or {}
    pig_id = payload.get('pig_id')
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return jsonify({'error': 'Cochon introuvable'}), 404
    if not pig.is_alive:
        return jsonify({'dead': True, 'message': "Trop tard... il est passé de l'autre côté."}), 200
    if not pig.is_injured:
        return jsonify({'already_healed': True}), 200
    if pig.vet_deadline and datetime.utcnow() > pig.vet_deadline:
        send_to_abattoir(pig, cause='blessure')
        return jsonify({'dead': True, 'message': 'Le délai était dépassé. RIP.'}), 200

    pig.is_injured = False
    pig.vet_deadline = None
    pig.injury_risk = min(35.0, max(MIN_INJURY_RISK, (pig.injury_risk or MIN_INJURY_RISK) + 2.0))
    pig.energy = max(0, pig.energy - 10)
    pig.happiness = max(0, pig.happiness - 5)
    db.session.commit()
    return jsonify({'healed': True, 'message': f"{pig.name} s'en sort ! Repos, soupe tiède et pas de sprint tout de suite."})

@app.route('/api/vet/timeout', methods=['POST'])
def vet_timeout():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401
    user = User.query.get(session['user_id'])
    payload = request.get_json(silent=True) or {}
    pig_id = payload.get('pig_id')
    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id:
        return jsonify({'error': 'Cochon introuvable'}), 404
    if pig.is_alive and pig.is_injured:
        send_to_abattoir(pig, cause='blessure')
    return jsonify({'dead': True})

@app.route('/classement')
def classement():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    all_users = User.query.all()
    rankings = []
    
    for u in all_users:
        # Calcul des stats
        total_wins = db.session.query(db.func.sum(Pig.races_won)).filter(Pig.user_id == u.id).scalar() or 0
        total_races = db.session.query(db.func.sum(Pig.races_entered)).filter(Pig.user_id == u.id).scalar() or 0
        dead_pigs_count = Pig.query.filter_by(user_id=u.id, is_alive=False).count()
        win_rate = (total_wins / total_races * 100) if total_races > 0 else 0
        
        # Système de trophées
        trophies = []
        if u.balance >= 500: trophies.append({'n': 'Crésus', 'e': '💰', 'd': 'Avoir plus de 500 BG'})
        if total_wins >= 10: trophies.append({'n': 'Légende', 'e': '🏆', 'd': '10 victoires au total'})
        if dead_pigs_count >= 5: trophies.append({'n': 'Boucher', 'e': '🔪', 'd': '5 cochons à l\'abattoir'})
        if total_races >= 50: trophies.append({'n': 'Vétéran', 'e': '🎖️', 'd': '50 courses disputées'})
        
        rankings.append({
            'user': u,
            'total_wins': total_wins,
            'total_races': total_races,
            'win_rate': round(win_rate, 1),
            'dead_count': dead_pigs_count,
            'trophies': trophies,
            'score': round(u.balance + (total_wins * 50), 2) # Score arbitraire pour le tri
        })
    
    # Tri par score décroissant
    rankings.sort(key=lambda x: x['score'], reverse=True)
    
    # Données pour les graphiques (Top 5)
    top_5 = rankings[:5]
    chart_data = {
        'labels': [r['user'].username for r in top_5],
        'balances': [r['user'].balance for r in top_5],
        'wins': [r['total_wins'] for r in top_5]
    }
    
    return render_template('classement.html', user=user, rankings=rankings, chart_data=chart_data)

@app.route('/legendes-pop')
def legendes_pop():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    pop_pigs = [
        # Stars du Marché
        {'name': 'Porky Pig', 'emoji': '🎩', 'desc': 'Le pionnier. A transformé un bégaiement en une carrière légendaire.', 'category': 'Stars du Marché'},
        {'name': 'Miss Piggy', 'emoji': '🎀', 'desc': 'Influenceuse avant Instagram. Mélange unique de glamour et de violence passive-agressive.', 'category': 'Stars du Marché'},
        {'name': 'Peppa Pig', 'emoji': '☔', 'desc': 'CEO d’un empire mondial basé sur des grognements et des flaques de boue.', 'category': 'Stars du Marché'},
        {'name': 'Porcinet', 'emoji': '🧣', 'desc': '12 kg de stress, mais validé émotionnellement par toute une génération.', 'category': 'Stars du Marché'},

        # Intellectuels / Dangereux
        {'name': 'Napoléon', 'emoji': '👑', 'desc': 'Commence comme cochon, finit comme manager toxique (La Ferme des Animaux).', 'category': 'Niveau Dangereux'},
        {'name': 'Porco Rosso', 'emoji': '🛩️', 'desc': 'Pilote, philosophe, cochon. Trois problèmes complexes en un seul groin.', 'category': 'Niveau Dangereux'},
        {'name': 'Cochons (Pink Floyd)', 'emoji': '🎸', 'desc': 'Métaphore officielle des élites. Entrée validée par guitare électrique.', 'category': 'Niveau Dangereux'},
        {'name': 'Tête de cochon', 'emoji': '💀', 'desc': 'Quand un cochon mort devient plus charismatique que les humains (Sa Majesté des Mouches).', 'category': 'Niveau Dangereux'},

        # Cochons du Quotidien
        {'name': 'Cochon Minecraft', 'emoji': '🧊', 'desc': 'Moyen de transport discutable. Existe principalement pour être transformé en côtelette.', 'category': 'Quotidien Suspect'},
        {'name': 'Cochons Verts', 'emoji': '🤢', 'desc': 'Ingénieurs en structures inefficaces (Angry Birds).', 'category': 'Quotidien Suspect'},
        {'name': 'Hog Rider', 'emoji': '🔨', 'desc': 'Un homme qui crie sur un cochon. Personne ne remet ça en question.', 'category': 'Quotidien Suspect'},
        {'name': 'Hamm / Bayonne', 'emoji': '🪙', 'desc': 'Tirelire cynique de Toy Story. Le seul qui comprend réellement l’économie.', 'category': 'Quotidien Suspect'},

        # Patrimoine & Héritage
        {'name': 'Nif-Nif, Naf-Naf & Nouf-Nouf', 'emoji': '🏠', 'desc': 'Trois approches du BTP. Une seule résiste réellement au souffle du loup.', 'category': 'Patrimoine'},
        {'name': 'Babe', 'emoji': '🐑', 'desc': 'Le seul cochon avec un plan de carrière et une reconversion réussie.', 'category': 'Patrimoine'},
        {'name': 'Wilbur', 'emoji': '🕸️', 'desc': 'Sauvé par une araignée (Charlotte) meilleure en communication de crise que lui.', 'category': 'Patrimoine'},
        {'name': 'Peter Pig', 'emoji': '⚓', 'desc': 'Preuve que même chez Disney, certains cochons n’ont pas percé.', 'category': 'Patrimoine'},

        # Secondaires
        {'name': 'Petunia Pig', 'emoji': '👒', 'desc': 'Love interest officielle. Un potentiel inexploité par les studios.', 'category': 'Secondaires'},
        {'name': 'Piggy (Merrie Melodies)', 'emoji': '🤡', 'desc': 'Version bêta de Porky Pig. A servi de crash-test pour l’humour.', 'category': 'Secondaires'},
        {'name': 'Arnold Ziffel', 'emoji': '📺', 'desc': 'Cochon traité comme un humain complet. Personne ne pose de questions.', 'category': 'Secondaires'},
        {'name': 'Pumbaa', 'emoji': '🐗', 'desc': 'Techniquement un phacochère. Accepté dans la base pour raisons administratives.', 'category': 'Secondaires'},
    ]
    return render_template('legendes_pop.html', user=user, pop_pigs=pop_pigs)

@app.route('/api/countdown')
def api_countdown():
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
        'races_entered': pig.races_entered, 'races_won': pig.races_won,
        'school_sessions_completed': pig.school_sessions_completed or 0,
        'school_cooldown': get_cooldown_remaining(pig.last_school_at, SCHOOL_COOLDOWN_MINUTES),
        'is_injured': pig.is_injured,
        'injury_risk': round(pig.injury_risk or MIN_INJURY_RISK, 1),
        'vet_seconds_left': get_seconds_until(pig.vet_deadline) if pig.is_injured else 0
    })

@app.route('/api/prix-groin')
def api_prix_groin():
    return jsonify({'prix': get_prix_moyen_groin()})

# ─── SCHEDULER ──────────────────────────────────────────────────────────────

def scheduler_should_start():
    return app.config.get('SCHEDULER_ENABLED', True)

def run_scheduler_job(job_name, callback):
    with app.app_context():
        try:
            callback()
        except Exception:
            app.logger.exception("Scheduler job failed: %s", job_name)
            db.session.rollback()
        finally:
            db.session.remove()

def scheduled_race_tick():
    run_scheduler_job('race_tick', lambda: (run_race_if_needed(), ensure_next_race()))

def scheduled_auction_tick():
    run_scheduler_job('auction_tick', resolve_auctions)

def scheduled_vet_tick():
    run_scheduler_job('vet_tick', check_vet_deadlines)

def start_scheduler():
    global scheduler
    if scheduler is not None or not scheduler_should_start():
        return

    scheduler = BackgroundScheduler(timezone=APP_TIMEZONE)
    scheduler.add_job(
        scheduled_race_tick,
        IntervalTrigger(seconds=15, timezone=APP_TIMEZONE),
        id='race-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        scheduled_auction_tick,
        IntervalTrigger(minutes=1, timezone=APP_TIMEZONE),
        id='auction-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        scheduled_vet_tick,
        IntervalTrigger(seconds=15, timezone=APP_TIMEZONE),
        id='vet-tick',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler and scheduler.running else None)
    app.logger.info("Background scheduler started")

def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler = None

def should_autostart_scheduler():
    if not app.config.get('SCHEDULER_ENABLED', True):
        return False
    if os.environ.get('DERBY_FORCE_SCHEDULER') == '1':
        return True
    return os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

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
        ('pig', 'last_school_at', 'DATETIME'),
        ('pig', 'school_sessions_completed', 'INTEGER DEFAULT 0'),
        ('pig', 'is_injured', 'BOOLEAN DEFAULT 0'),
        ('pig', 'injury_risk', 'FLOAT DEFAULT 10.0'),
        ('pig', 'vet_deadline', 'DATETIME'),
        ('user', 'is_admin', 'BOOLEAN DEFAULT 0'),
        ('user', 'last_relief_at', 'DATETIME'),
        ('auction', 'seller_id', 'INTEGER'),
        ('auction', 'source_pig_id', 'INTEGER'),
        ('auction', 'pig_origin', 'VARCHAR(30)'),
        ('auction', 'pig_origin_flag', 'VARCHAR(10)'),
        ('bet', 'bet_type', 'VARCHAR(20) DEFAULT "win"'),
        ('bet', 'selection_order', 'VARCHAR(240)'),
    ]
    index_migrations = [
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_bet_user_race ON bet(user_id, race_id)',
        'CREATE INDEX IF NOT EXISTS ix_auction_status_ends_at ON auction(status, ends_at)',
        'CREATE INDEX IF NOT EXISTS ix_race_status_scheduled_at ON race(status, scheduled_at)',
        'CREATE INDEX IF NOT EXISTS ix_pig_vet_deadline ON pig(is_injured, is_alive, vet_deadline)',
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
            apply_origin_bonus(pig, origin_data)
            db.session.add(pig)

    demo_owner = User.query.filter_by(username='Christophe').first()
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
            )
            apply_origin_bonus(demo_pig, origin_data)
            db.session.add(demo_pig)
    db.session.commit()

with app.app_context():
    db.create_all()
    migrate_db()
    init_default_config()
    seed_users()
    ensure_next_race()

if should_autostart_scheduler():
    start_scheduler()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
