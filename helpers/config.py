"""Configuration helpers — get/set GameConfig + cache TTL."""

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


def init_default_config():
    defaults = {
        'race_hour': '14',
        'race_minute': '00',
        'market_day': '4',
        'market_hour': '13',
        'market_minute': '45',
        'market_duration': '120',
        'min_real_participants': '2',
        'empty_race_mode': 'fill',
    }
    for k, v in defaults.items():
        if not GameConfig.query.filter_by(key=k).first():
            db.session.add(GameConfig(key=k, value=v))
    db.session.commit()
    invalidate_config_cache()
