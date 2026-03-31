from dataclasses import dataclass
import json

from helpers.config import get_config


@dataclass(frozen=True)
class GameSettings:
    race_hour: int
    race_minute: int
    market_days_raw: str          # ex: "1,3,4" — jours du marché séparés par virgules
    market_hour: int
    market_minute: int
    market_duration: int
    min_real_participants: int
    empty_race_mode: str
    race_schedule: str

    @classmethod
    def load(cls):
        # Schedule par défaut : toutes les 30 minutes de 08:00 à 22:00
        default_times = [f"{h:02d}:00" for h in range(8, 23)] + [f"{h:02d}:30" for h in range(8, 22)]
        default_times.sort()
        default_schedule = {str(i): default_times for i in range(7)}

        return cls(
            race_hour=_get_int_config('race_hour', 14),
            race_minute=_get_int_config('race_minute', 0),
            market_days_raw=get_config('market_day', '4') or '4',
            market_hour=_get_int_config('market_hour', 13),
            market_minute=_get_int_config('market_minute', 45),
            market_duration=_get_int_config('market_duration', 120),
            min_real_participants=_get_int_config('min_real_participants', 2),
            empty_race_mode=get_config('empty_race_mode', 'fill') or 'fill',
            race_schedule=get_config('race_schedule', json.dumps(default_schedule)),
        )

    @property
    def market_days(self):
        """Liste triée des jours de marché (0=Lundi … 6=Dimanche)."""
        try:
            return sorted(int(d.strip()) for d in self.market_days_raw.split(',') if d.strip().isdigit() and 0 <= int(d.strip()) <= 6)
        except (TypeError, ValueError):
            return [4]

    @property
    def market_day(self):
        """Rétro-compatibilité : retourne le premier jour de marché."""
        days = self.market_days
        return days[0] if days else 4

    @property
    def schedule_dict(self):
        import json
        try:
            return json.loads(self.race_schedule)
        except (TypeError, ValueError):
            return {}


def _get_int_config(key, default):
    raw_value = get_config(key, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(default)


def get_game_settings():
    import json # ensure json is available if used in load
    return GameSettings.load()
