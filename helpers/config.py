"""Configuration helpers — get/set GameConfig + cache TTL."""

import json
import time

from extensions import db
from models import GameConfig

# Cache memoire simple {key: (value, timestamp)}
_config_cache = {}
_CACHE_TTL = 10  # secondes


def get_config(key, default=''):
    now = time.time()
    cached = _config_cache.get(key)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    c = GameConfig.query.filter_by(key=key).first()
    value = c.value if c else default
    _config_cache[key] = (value, now)
    return value


def set_config(key, value):
    c = GameConfig.query.filter_by(key=key).first()
    if c:
        c.value = str(value)
    else:
        db.session.add(GameConfig(key=key, value=str(value)))
    db.session.commit()
    # Invalider le cache pour cette cle
    _config_cache.pop(key, None)


def invalidate_config_cache():
    """Vide tout le cache config (utile apres un changement en masse)."""
    _config_cache.clear()


# ── Thèmes de course par défaut (un par jour de la semaine) ──────────────
DEFAULT_RACE_THEMES = {
    "0": {"emoji": "🌧️", "name": "Lundi de la Pataugeoire", "tag": "Boue + Force",
           "description": "Boue lourde, appuis glissants et contacts rugueux : les cochons puissants y gagnent un vrai avantage.",
           "accent": "amber", "focus_stat": "force", "focus_label": "Force favorisee",
           "reward_multiplier": 1, "event_label": "Theme quotidien",
           "planning_hint": "Ideal pour tes profils costauds qui aiment pousser dans la gadoue."},
    "1": {"emoji": "🥓", "name": "Trot du Jambon", "tag": "Classique equilibre",
           "description": "Le format le plus fiable pour remplir ton quota sans surprise majeure.",
           "accent": "pink", "focus_stat": "polyvalence", "focus_label": "Stats equilibrees",
           "reward_multiplier": 1, "event_label": "Routine rentable",
           "planning_hint": "Parfait pour caser un cochon regulier entre deux gros rendez-vous."},
    "2": {"emoji": "🏃", "name": "Mercredi Marathon", "tag": "Longue distance",
           "description": "Le rail s'etire, le tempo use les reserves et seuls les cochons endurants gardent leur allure jusqu'au bout.",
           "accent": "cyan", "focus_stat": "endurance", "focus_label": "Endurance favorisee",
           "reward_multiplier": 1, "event_label": "Theme quotidien",
           "planning_hint": "A reserver a tes moteurs les plus constants pour securiser la semaine."},
    "3": {"emoji": "🥓", "name": "Trot du Jambon", "tag": "Classique equilibre",
           "description": "Le format le plus fiable pour remplir ton quota sans surprise majeure.",
           "accent": "pink", "focus_stat": "polyvalence", "focus_label": "Stats equilibrees",
           "reward_multiplier": 1, "event_label": "Routine rentable",
           "planning_hint": "Parfait pour caser un cochon regulier entre deux gros rendez-vous."},
    "4": {"emoji": "🏆", "name": "Grand Prix du Vendredi", "tag": "Recompenses x3",
           "description": "Le grand rendez-vous asynchrone de la semaine : plus de prestige, plus de pression et des primes d'elevage triplees.",
           "accent": "red", "focus_stat": "moral", "focus_label": "Prestige maximal",
           "reward_multiplier": 3, "event_label": "Evenement majeur",
           "planning_hint": "Garde au moins un top cochon disponible pour ce pic de rentabilite."},
    "5": {"emoji": "🌿", "name": "Derby des Bauges Calmes", "tag": "Repos ou event",
           "description": "Un creneau souple pour finir ton quota, tester des doublures ou garder du jus pour vendredi.",
           "accent": "emerald", "focus_stat": "rotation", "focus_label": "Gestion d'effectif",
           "reward_multiplier": 1, "event_label": "Souplesse",
           "planning_hint": "Utilise-le pour lisser la fatigue et terminer ta semaine en 5 minutes."},
    "6": {"emoji": "🌿", "name": "Derby des Bauges Calmes", "tag": "Repos ou event",
           "description": "Un creneau souple pour finir ton quota, tester des doublures ou garder du jus pour vendredi.",
           "accent": "emerald", "focus_stat": "rotation", "focus_label": "Gestion d'effectif",
           "reward_multiplier": 1, "event_label": "Souplesse",
           "planning_hint": "Utilise-le pour lisser la fatigue et terminer ta semaine en 5 minutes."},
}


def init_default_config():
    defaults = {
        # Planification des courses et du marché
        'race_hour': '14',
        'race_minute': '00',
        'market_day': '4',
        'market_hour': '13',
        'market_minute': '45',
        'market_duration': '120',
        'min_real_participants': '2',
        'empty_race_mode': 'fill',
        'timezone': 'Europe/Paris',
        # Système financier (anti-baleine, secours, solidarité)
        'balance_emergency_threshold': '10.0',
        'balance_emergency_amount': '20.0',
        'balance_emergency_hours': '12',
        'balance_casino_daily_cap': '500.0',
        'balance_tax_threshold_1': '2000.0',
        'balance_tax_rate_1': '0.20',
        'balance_tax_threshold_2': '5000.0',
        'balance_tax_rate_2': '0.50',
        'balance_solidarity_threshold': '50.0',
        'balance_solidarity_amount': '30.0',
        # Cochons — biologie et limites
        'pig_max_slots': '4',
        'pig_retirement_min_wins': '3',
        'pig_weight_default_kg': '112.0',
        'pig_weight_min_kg': '75.0',
        'pig_weight_max_kg': '190.0',
        'pig_weight_malus_ratio': '0.20',
        'pig_weight_malus_max': '0.45',
        'pig_injury_min_risk': '2.0',
        'pig_injury_max_risk': '18.0',
        'pig_vet_response_minutes': '20',
        # Bourse aux grains
        'bourse_surcharge_factor': '0.05',
        'bourse_movement_divisor': '10',
    }
    # Moteur de course : JSON blob (inséré séparément pour éviter un import circulaire)
    if not GameConfig.query.filter_by(key='race_engine_config').first():
        try:
            from services.race_engine_service import RaceEngineSettings
            race_engine_json = RaceEngineSettings.defaults().to_json()
            db.session.add(GameConfig(key='race_engine_config', value=race_engine_json))
        except Exception:
            pass  # Ne jamais bloquer le démarrage
    for k, v in defaults.items():
        if not GameConfig.query.filter_by(key=k).first():
            db.session.add(GameConfig(key=k, value=v))
    db.session.commit()
    invalidate_config_cache()
