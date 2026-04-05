"""Economy and finance default values."""

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
RACE_POSITION_REWARDS = {1: 100.0, 2: 50.0, 3: 25.0}

WEEKLY_RACE_QUOTA = 3
WEEKLY_BACON_TICKETS = 3
DAILY_LOGIN_REWARD = 15.0
MIN_BET_RACE = 5
MAX_BET_RACE = 500
COMPLEX_BET_MIN_SELECTIONS = 3  # Paris avec 3+ selections necessitent un cochon participant

TAX_THRESHOLD_1 = 2000.0
TAX_RATE_1 = 0.20
TAX_THRESHOLD_2 = 5000.0
TAX_RATE_2 = 0.50

TAX_EXEMPT_REASON_CODES = frozenset({
    'daily_reward', 'emergency_relief', 'challenge_payout',
    'solidarity_relief', 'breed_refund',
    'bet_payout', 'bet_payout_adjustment', 'bet_refund',
})

CASINO_REASON_CODES = frozenset({
    'blackjack_win', 'blackjack_blackjack', 'blackjack_push',
    'poker_win', 'poker_push',
})
CASINO_DAILY_WIN_CAP = 500.0

BET_TYPES = {
    'win': {
        'label': 'Groin Jackpot',
        'icon': '🥇',
        'selection_count': 1,
        'top_n': 1,
        'order_matters': True,
        'house_edge': 1.15,
        'description': "Choisis un cochon. S'il termine 1er, tu gagnes le pactole de bacon.",
    },
    'place': {
        'label': 'Groin Pas Trop Nul',
        'icon': '🥉',
        'selection_count': 1,
        'top_n': 3,
        'order_matters': False,
        'house_edge': 1.15,
        'description': "Ton cochon doit finir dans les 3 premiers. Même un goret fatigué peut passer.",
    },
    'exacta': {
        'label': 'Duo de Cochons',
        'icon': '🥈',
        'selection_count': 2,
        'top_n': 2,
        'order_matters': True,
        'house_edge': 1.25,
        'description': "Choisis 2 cochons. Ils doivent finir 1er et 2e… sans s'arrêter pour manger.",
    },
    'quinela_place': {
        'label': 'Duo dans la Boue',
        'icon': '🐽',
        'selection_count': 2,
        'top_n': 3,
        'order_matters': False,
        'house_edge': 1.20,
        'description': "Tes 2 cochons doivent être dans les 3 premiers. Un bon plongeon dans la gadoue peut aider.",
    },
    'tierce_any': {
        'label': 'Trio Sauciflard',
        'icon': '🥪',
        'selection_count': 3,
        'top_n': 3,
        'order_matters': False,
        'house_edge': 1.25,
        'description': "Choisis 3 cochons qui doivent finir dans les 3 premiers, dans n'importe quel ordre.",
    },
    'tierce': {
        'label': 'Trio Bacon Parfait',
        'icon': '🎯',
        'selection_count': 3,
        'top_n': 3,
        'order_matters': True,
        'house_edge': 1.30,
        'description': "Choisis les 3 premiers cochons dans l'ordre exact. Là c'est du grand art porcin.",
    },
    'quarte': {
        'label': 'La Bagarre du Poulailler',
        'icon': '⚔️',
        'selection_count': 4,
        'top_n': 4,
        'order_matters': False,
        'house_edge': 1.18,
        'description': "Trouve les 4 premiers cochons. Ça pousse, ça grogne, ça part dans tous les sens.",
    },
    'quinte': {
        'label': 'Le Grand Goret',
        'icon': '👑',
        'selection_count': 5,
        'top_n': 5,
        'order_matters': False,
        'house_edge': 1.15,
        'description': "Trouve les 5 premiers cochons. Le jackpot ultime du jambon.",
    },
    'two_of_four': {
        'label': 'Deux dans la Soue',
        'icon': '🐖',
        'selection_count': 2,
        'top_n': 4,
        'order_matters': False,
        'house_edge': 1.10,
        'description': "Trouve 2 cochons parmi les 4 premiers. Même les plus patauds ont leur chance.",
    },
    'quarte_order': {
        'label': 'La Super Porcherie',
        'icon': '🏰',
        'selection_count': 4,
        'top_n': 4,
        'order_matters': True,
        'house_edge': 1.40,
        'description': "Trouve les 4 premiers cochons dans l'ordre exact. Les pros du groin seulement.",
    },
    'rafle': {
        'label': 'La Rafle du Bacon',
        'icon': '🥓',
        'selection_count': 5,
        'top_n': 5,
        'order_matters': True,
        'house_edge': 1.45,
        'description': "Trouve les 5 premiers cochons dans l'ordre exact. Le pari ultime des vrais éleveurs.",
    },
}
