"""Pig catalogs, origins, rarity tables, and generated naming parts."""

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

PIG_NAME_PREFIXES = [
    'Groin', 'Porcinet', 'Truffe', 'Lardon', 'Boudin', 'Saucisse',
    'Cochon', 'Museau', 'Grognon', 'Jambon', 'Pâté', 'Rillette',
    'Andouille', 'Terrine', 'Gratton', 'Porc',
]

PIG_NAME_SUFFIXES = [
    'de Feu', 'Doré', 'Sauvage', 'Express', 'Turbo', 'Suprême',
    'le Grand', 'le Terrible', 'le Brave', 'le Magnifique',
    "de l'Ombre", 'du Tonnerre', 'Infernal', 'le Rapide',
    'de Fer', 'le Féroce', 'le Rusé', 'Légendaire',
]

RARITIES = {
    'commun': {
        'name': 'Commun', 'color': '#9ca3af', 'emoji': '⚪',
        'stats_range': (5, 20), 'max_races_range': (20, 30),
        'price_range': (15, 30), 'weight': 50,
    },
    'rare': {
        'name': 'Rare', 'color': '#3b82f6', 'emoji': '🔵',
        'stats_range': (15, 35), 'max_races_range': (30, 40),
        'price_range': (30, 60), 'weight': 30,
    },
    'epique': {
        'name': 'Épique', 'color': '#a855f7', 'emoji': '🟣',
        'stats_range': (25, 50), 'max_races_range': (40, 50),
        'price_range': (60, 120), 'weight': 15,
    },
    'legendaire': {
        'name': 'Légendaire', 'color': '#f59e0b', 'emoji': '🟡',
        'stats_range': (40, 70), 'max_races_range': (50, 75),
        'price_range': (120, 250), 'weight': 5,
    },
}
