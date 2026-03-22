from dataclasses import dataclass

from helpers import get_config


@dataclass(frozen=True)
class GameSettings:
    race_hour: int
    race_minute: int
    market_day: int
    market_hour: int
    market_minute: int
    market_duration: int
    min_real_participants: int
    empty_race_mode: str

    @classmethod
    def load(cls):
        return cls(
            race_hour=_get_int_config('race_hour', 14),
            race_minute=_get_int_config('race_minute', 0),
            market_day=_get_int_config('market_day', 4),
            market_hour=_get_int_config('market_hour', 13),
            market_minute=_get_int_config('market_minute', 45),
            market_duration=_get_int_config('market_duration', 120),
            min_real_participants=_get_int_config('min_real_participants', 2),
            empty_race_mode=get_config('empty_race_mode', 'fill') or 'fill',
        )


def _get_int_config(key, default):
    raw_value = get_config(key, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(default)


def get_game_settings():
    return GameSettings.load()
