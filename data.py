IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO = 0.20
MAX_WEIGHT_PERFORMANCE_MALUS = 0.45
FRESHNESS_BONUS_HOURS = 2
FRESHNESS_MORAL_BONUS = 0.10
SNACK_SHARE_DAILY_LIMIT = 3
OFFICE_SNACKS = {
    'pomme': {'name': 'Pomme', 'emoji': '🍎', 'hunger_restore': 5},
    'biscuit': {'name': 'Biscuit', 'emoji': '🍪', 'hunger_restore': 5},
}

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

PRELOADED_PIG_NAMES = [
    "Lard Vador",
    "Trop Lard",
    "Lard de Rien",
    "Lard Déco",
    "Lard Plastique",
    "Lard Scénic",
    "Lard Choix",
    "Lard Magnac",
    "Porcasse",
    "Jean-Luc Porcard",
    "Cochonou Reeves",
    "Hambone",
    "Francis Bacon",
    "Albert Ein-Styr",
    "Groseille",
    "Spider-Cochon",
    "Groin de Sel",
    "Groin de Folie",
    "Truie sans fin",
    "Gros Groin",
    "À tire-d'aile et de groin",
    "Cochon-Air",
    "Porc-Salut",
    "Porc-Royal",
    "Harry Pot-au-feu",
    "Justin Bridou",
]

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
        'weight_delta': 0.5,
        'valeur_fourragere': 100
    },
    'orge': {
        'name': 'Orge', 'emoji': '🌾', 'cost': 8,
        'description': '+Endurance +Force',
        'hunger_restore': 30, 'energy_restore': 8,
        'stats': {'endurance': 2.0, 'force': 1.5, 'vitesse': 0.3},
        'weight_delta': 0.9,
        'valeur_fourragere': 97
    },
    'ble': {
        'name': 'Blé', 'emoji': '🌿', 'cost': 10,
        'description': '+Force +Vitesse',
        'hunger_restore': 25, 'energy_restore': 5,
        'stats': {'force': 2.0, 'vitesse': 1.5, 'endurance': 0.5},
        'weight_delta': 0.8,
        'valeur_fourragere': 105
    },
    'seigle': {
        'name': 'Seigle', 'emoji': '🌱', 'cost': 7,
        'description': '+Agilité +Intelligence',
        'hunger_restore': 20, 'energy_restore': 5,
        'stats': {'agilite': 2.0, 'intelligence': 1.5},
        'weight_delta': 0.3,
        'valeur_fourragere': 102
    },
    'triticale': {
        'name': 'Triticale', 'emoji': '🍃', 'cost': 9,
        'description': '+Vitesse +Endurance',
        'hunger_restore': 25, 'energy_restore': 10,
        'stats': {'vitesse': 2.0, 'endurance': 1.5, 'moral': 0.5},
        'weight_delta': 0.4,
        'valeur_fourragere': 100
    },
    'avoine': {
        'name': 'Avoine', 'emoji': '🥣', 'cost': 6,
        'description': '+Moral +Agilité — récupération',
        'hunger_restore': 15, 'energy_restore': 15,
        'stats': {'moral': 2.5, 'agilite': 1.0},
        'weight_delta': 0.2,
        'valeur_fourragere': 82
    }
}

TRAININGS = {
    'sprint': {
        'name': 'Sprint', 'emoji': '💨',
        'description': 'Course courte et explosive',
        'energy_cost': 25, 'hunger_cost': 10,
        'stats': {'vitesse': 0.6, 'endurance': 0.2},
        'weight_delta': -0.7,
        'min_happiness': 20
    },
    'cross': {
        'name': 'Cross-country', 'emoji': '🏃',
        'description': 'Longue distance, mental d\'acier',
        'energy_cost': 35, 'hunger_cost': 15,
        'stats': {'endurance': 0.6, 'force': 0.2, 'vitesse': 0.1},
        'weight_delta': -1.0,
        'min_happiness': 20
    },
    'obstacles': {
        'name': 'Parcours d\'obstacles', 'emoji': '🏅',
        'description': 'Agilité et réflexes',
        'energy_cost': 30, 'hunger_cost': 10,
        'stats': {'agilite': 0.6, 'intelligence': 0.2},
        'weight_delta': -0.6,
        'min_happiness': 30
    },
    'sparring': {
        'name': 'Sparring', 'emoji': '🥊',
        'description': 'Combat amical, gagne en puissance',
        'energy_cost': 30, 'hunger_cost': 15,
        'stats': {'force': 0.6, 'moral': 0.1, 'endurance': 0.1},
        'weight_delta': 0.2,
        'min_happiness': 30
    },
    'puzzles': {
        'name': 'Puzzles & Stratégie', 'emoji': '🧩',
        'description': 'Entraînement cérébral',
        'energy_cost': 15, 'hunger_cost': 5,
        'stats': {'intelligence': 0.6, 'moral': 0.2},
        'weight_delta': 0.1,
        'min_happiness': 10
    },
    'repos': {
        'name': 'Repos & Détente', 'emoji': '😴',
        'description': 'Récupération complète',
        'energy_cost': -40, 'hunger_cost': 5,
        'stats': {'moral': 0.4},
        'weight_delta': 0.5,
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
        'stats': {'intelligence': 0.5, 'agilite': 0.3},
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
        'stats': {'endurance': 0.4, 'moral': 0.2},
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
        'stats': {'moral': 0.4, 'intelligence': 0.3},
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
        'stats': {'vitesse': 0.3, 'agilite': 0.3, 'intelligence': 0.2},
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

STAT_DESCRIPTIONS = {
    'vitesse': 'Vitesse de pointe sur terrain plat. Crucial pour le sprint final.',
    'endurance': 'Résistance à la fatigue. Permet de maintenir une vitesse élevée plus longtemps.',
    'agilite': 'Aisance dans les virages et les dépassements. Réduit les risques de bousculade.',
    'force': 'Puissance de poussée. Utile pour les départs et les terrains difficiles.',
    'intelligence': 'Lecture de course. Améliore les trajectoires et la gestion de l\'effort.',
    'moral': 'Détermination du cochon. Un moral haut donne un bonus global à toutes les stats en course.',
}

EMERGENCY_RELIEF_THRESHOLD = 10.0
EMERGENCY_RELIEF_AMOUNT = 20.0
EMERGENCY_RELIEF_HOURS = 12
SECOND_PIG_COST = 30.0
REPLACEMENT_PIG_COST = 15.0
MAX_PIG_SLOTS = 4
BREEDING_COST = 45.0
RETIREMENT_HERITAGE_MIN_WINS = 3
FEEDING_PRESSURE_PER_PIG = 0.2
BETTING_HOUSE_EDGE = 1.18
EXACTA_HOUSE_EDGE = 1.28
TIERCE_HOUSE_EDGE = 1.28
RACE_APPEARANCE_REWARD = 6.0
RACE_POSITION_REWARDS = {1: 25.0, 2: 12.0, 3: 6.0}
VET_RESPONSE_MINUTES = 5
MIN_INJURY_RISK = 8.0
MAX_INJURY_RISK = 40.0
DEFAULT_PIG_WEIGHT_KG = 112.0
MIN_PIG_WEIGHT_KG = 75.0
MAX_PIG_WEIGHT_KG = 190.0
WEEKLY_RACE_QUOTA = 3
WEEKLY_BACON_TICKETS = 3
DAILY_LOGIN_REWARD = 15.0

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
        'stats_range': (5, 20), 'max_races_range': (20, 30),
        'price_range': (15, 30), 'weight': 50
    },
    'rare': {
        'name': 'Rare', 'color': '#3b82f6', 'emoji': '🔵',
        'stats_range': (15, 35), 'max_races_range': (30, 40),
        'price_range': (30, 60), 'weight': 30
    },
    'epique': {
        'name': 'Épique', 'color': '#a855f7', 'emoji': '🟣',
        'stats_range': (25, 50), 'max_races_range': (40, 50),
        'price_range': (60, 120), 'weight': 15
    },
    'legendaire': {
        'name': 'Légendaire', 'color': '#f59e0b', 'emoji': '🟡',
        'stats_range': (40, 70), 'max_races_range': (50, 75),
        'price_range': (120, 250), 'weight': 5
    }
}
JOURS_FR = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

PIG_TYPING_WORDS = [
    "groin", "jambon", "lisier", "tirelire", "salaison", "couenne", "truffe", "porcherie",
    "rillettes", "lardon", "bacon", "saucisson", "charcuterie", "cochon", "verrat", "truie",
    "porcelet", "porc", "boudin", "andouillette", "museau", "hure", "griffon", "soie",
    "lisier", "auge", "paille", "foin", "ferme", "elevage", "paddock", "course",
    "galop", "vitesse", "champion", "medaille", "victoire", "podium", "derby", "grognement",
    "paté", "terrine", "cotelette", "palette", "échine", "travers", "poitrine", "jambe",
]

PIG_COURSE_SEGMENT_TYPES = ['PLAT', 'MONTEE', 'DESCENTE', 'VIRAGE', 'BOUE']

# ---------------------------------------------------------------------------
# Moteur de course -- constantes d'equilibrage (race_engine.py)
# ---------------------------------------------------------------------------
# Toutes les "magic numbers" sont ici pour faciliter le tuning sans toucher
# au code algorithmique.

# Limite de tours pour eviter une boucle infinie
RACE_MAX_TURNS = 120

# -- Strategie --
RACE_ATTACK_THRESHOLD = 71
RACE_NEUTRAL_MAX = 70
RACE_STRATEGY_ECONOMY_MIN_MULT = 0.72
RACE_STRATEGY_ATTACK_MAX_MULT = 1.18
RACE_STRATEGY_ECONOMY_RECOVERY = 2.2
RACE_STRATEGY_NEUTRAL_FATIGUE = 1.2
RACE_ATTACK_FATIGUE_EXPONENT = 1.6

# -- Vitesse de base --
RACE_BASE_SPEED_VIT_MULT = 0.75      # coefficient principal sur le plat
RACE_BASE_SPEED_CONSTANT = 2.0       # plancher additif de base_speed
RACE_MIN_FINAL_SPEED = 0.5           # vitesse minimale garantie par tour
RACE_SEGMENT_SPEED_CAP = 30.0        # plafond de vitesse sur terrain libre
RACE_VIRAGE_SPEED_CAP = 18.0         # plafond dans les virages
RACE_BOUE_SPEED_CAP = 14.0           # plafond dans la boue

# -- Fatigue --
RACE_FATIGUE_SPEED_PENALTY_FLOOR = 0.4
RACE_FATIGUE_SPEED_PENALTY_DIVISOR = 100.0
RACE_ENDURANCE_FATIGUE_DIVISOR = 1.0
RACE_RECENT_RACE_PENALTY_FLOOR = 0.88

# -- Terrain : MONTEE --
RACE_MONTEE_SPEED_MULT = 0.8
RACE_MONTEE_FORCE_MULT = 1.2
RACE_MONTEE_TERRAIN_MOD = 0.86

# -- Terrain : DESCENTE --
RACE_DESCENTE_SPEED_MULT = 0.95
RACE_DESCENTE_TERRAIN_MOD = 1.08
RACE_DESCENTE_AGI_RISK_REDUCTION = 140.0
RACE_STUMBLE_BASE_CHANCE_DESCENTE = 0.12
RACE_STUMBLE_SPEED_MULT = 0.5

# -- Terrain : VIRAGE / BOUE --
RACE_STUMBLE_BASE_CHANCE_VIRAGE = 0.09
RACE_VIRAGE_AGI_MULT = 0.9
RACE_VIRAGE_TERRAIN_MOD = 0.88
RACE_BOUE_AGI_MULT = 0.75
RACE_BOUE_TERRAIN_MOD = 0.76

# -- Aspiration (Drafting) --
RACE_DRAFT_MIN_DIST = 1.0
RACE_DRAFT_MAX_DIST = 3.0
RACE_DRAFT_BONUS_MIN = 0.8
RACE_DRAFT_BONUS_MAX = 1.8
RACE_DRAFT_NO_FATIGUE_BONUS = 1.8
RACE_FATIGUE_HEADWIND_PENALTY = 0.8

# -- Variance --
RACE_VARIANCE_MIN = 0.98
RACE_VARIANCE_MAX = 1.02

# ---------------------------------------------------------------------------
# Bourse aux Grains -- marche dynamique de cereales
# ---------------------------------------------------------------------------
# Grille 7x7 avec valeurs symetriques : le centre (indice 3) vaut 0.
# Plus on s'eloigne du centre, plus le surcout augmente.
BOURSE_GRID_SIZE = 7
BOURSE_GRID_VALUES = [6, 4, 2, 0, 2, 4, 6]     # valeur par indice 0-6

BOURSE_DEFAULT_POS = 3                            # centre de la grille (0-indexed)
BOURSE_BLOCK_MIN = 1                              # centre du bloc 3x3 : min = 1
BOURSE_BLOCK_MAX = 5                              # centre du bloc 3x3 : max = 5

# Facteur de conversion valeur -> surcout (chaque point = +5% du prix de base)
BOURSE_SURCHARGE_FACTOR = 0.05

BOURSE_MOVEMENT_DIVISOR = 10                      # 1 point de mouvement / N achats
BOURSE_MIN_MOVEMENT = 1                           # minimum garanti

# Disposition des grains dans le bloc 3x3
# (dx, dy) relatif au centre du bloc -> cle cereal (None = case vide)
# dy=-1 = haut, dy=+1 = bas ; dx=-1 = gauche, dx=+1 = droite
BOURSE_GRAIN_LAYOUT = {
    (-1, -1): 'orge',       # coin haut-gauche    🌾
    ( 0, -1): 'triticale',  # bord haut           🍃
    ( 1, -1): 'ble',        # coin haut-droit     🌿
    (-1,  0): None,         # bord gauche (vide)
    ( 0,  0): 'mais',       # CENTRE = grain de base 🌽
    ( 1,  0): None,         # bord droit (vide)
    (-1,  1): 'seigle',     # coin bas-gauche     🌱
    ( 0,  1): None,         # bord bas (vide)
    ( 1,  1): 'avoine',     # coin bas-droit      🥣
}
