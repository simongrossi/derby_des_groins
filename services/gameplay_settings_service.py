from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from config.gameplay_defaults import (
    PENDU_EXTRA_PLAY_COST,
    PENDU_FREE_PLAYS_PER_DAY,
    RACE_MAX_PER_TICK,
    SCHOOL_COOLDOWN_MINUTES,
    SCHOOL_XP_DECAY_FLOOR,
    SCHOOL_XP_DECAY_THRESHOLDS,
    SNACK_SHARE_DAILY_LIMIT,
    TRAIN_DAILY_CAP,
)
from exceptions import ValidationError
from helpers.config import get_config, invalidate_config_cache, set_config

DEFAULT_PENDU_WIN_REWARD = 25.0
DEFAULT_PENDU_MAX_ERRORS = 7
DEFAULT_PENDU_LOSS_HAPPINESS_PENALTY = 20.0
DEFAULT_PENDU_LOSS_ENERGY_PENALTY = 10.0
DEFAULT_AGENDA_REWARD = 25.0
DEFAULT_AGENDA_REQUIRED_CATCHES = 5
DEFAULT_AGENDA_GAME_DURATION = 30
DEFAULT_AGENDA_MAX_PLAYS_PER_DAY = 1
DEFAULT_TRUFFE_REWARD = 20.0
DEFAULT_TRUFFE_MAX_CLICKS = 7
DEFAULT_TRUFFE_GRID_SIZE = 20

GAMEPLAY_SETTINGS_KEY = 'settings_gameplay'
MINIGAME_SETTINGS_KEY = 'settings_minigames'


@dataclass(frozen=True)
class GameplaySettings:
    snack_share_daily_limit: int
    train_daily_cap: int
    school_cooldown_minutes: int
    school_xp_decay_thresholds: list[tuple[int, float]]
    school_xp_decay_floor: float
    race_max_per_tick: int

    def to_dict(self):
        payload = asdict(self)
        payload['school_xp_decay_thresholds'] = [
            {'threshold': int(threshold), 'multiplier': float(multiplier)}
            for threshold, multiplier in self.school_xp_decay_thresholds
        ]
        return payload


@dataclass(frozen=True)
class MinigameSettings:
    pendu_free_plays_per_day: int
    pendu_extra_play_cost: int
    pendu_win_reward: float
    pendu_max_errors: int
    pendu_loss_happiness_penalty: float
    pendu_loss_energy_penalty: float
    agenda_reward: float
    agenda_required_catches: int
    agenda_game_duration: int
    agenda_max_plays_per_day: int
    truffe_reward: float
    truffe_max_clicks: int
    truffe_grid_size: int

    def to_dict(self):
        return asdict(self)


def _load_blob(key: str) -> dict:
    raw = get_config(key, '')
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_int(value, default, minimum=0, maximum=None):
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = int(default)
    parsed = max(int(minimum), parsed)
    if maximum is not None:
        parsed = min(int(maximum), parsed)
    return parsed


def _coerce_float(value, default, minimum=0.0, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    parsed = max(float(minimum), parsed)
    if maximum is not None:
        parsed = min(float(maximum), parsed)
    return round(parsed, 3)


def _normalize_decay_thresholds(raw_thresholds):
    source = raw_thresholds if isinstance(raw_thresholds, list) else []
    normalized: list[tuple[int, float]] = []
    for item in source:
        if isinstance(item, dict):
            threshold = item.get('threshold')
            multiplier = item.get('multiplier')
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            threshold, multiplier = item[0], item[1]
        else:
            continue
        normalized.append((
            _coerce_int(threshold, 1, minimum=1, maximum=100),
            _coerce_float(multiplier, 1.0, minimum=0.0, maximum=10.0),
        ))

    if not normalized:
        normalized = [(int(threshold), float(multiplier)) for threshold, multiplier in SCHOOL_XP_DECAY_THRESHOLDS]
    normalized.sort(key=lambda item: item[0])
    return normalized


def _normalize_gameplay_settings(payload=None) -> GameplaySettings:
    source = payload if isinstance(payload, dict) else {}
    return GameplaySettings(
        snack_share_daily_limit=_coerce_int(
            source.get('snack_share_daily_limit', SNACK_SHARE_DAILY_LIMIT),
            SNACK_SHARE_DAILY_LIMIT,
            minimum=0,
            maximum=20,
        ),
        train_daily_cap=_coerce_int(
            source.get('train_daily_cap', TRAIN_DAILY_CAP),
            TRAIN_DAILY_CAP,
            minimum=0,
            maximum=100,
        ),
        school_cooldown_minutes=_coerce_int(
            source.get('school_cooldown_minutes', SCHOOL_COOLDOWN_MINUTES),
            SCHOOL_COOLDOWN_MINUTES,
            minimum=0,
            maximum=1440,
        ),
        school_xp_decay_thresholds=_normalize_decay_thresholds(
            source.get('school_xp_decay_thresholds', SCHOOL_XP_DECAY_THRESHOLDS)
        ),
        school_xp_decay_floor=_coerce_float(
            source.get('school_xp_decay_floor', SCHOOL_XP_DECAY_FLOOR),
            SCHOOL_XP_DECAY_FLOOR,
            minimum=0.0,
            maximum=10.0,
        ),
        race_max_per_tick=_coerce_int(
            source.get('race_max_per_tick', RACE_MAX_PER_TICK),
            RACE_MAX_PER_TICK,
            minimum=1,
            maximum=50,
        ),
    )


def _normalize_minigame_settings(payload=None) -> MinigameSettings:
    source = payload if isinstance(payload, dict) else {}
    return MinigameSettings(
        pendu_free_plays_per_day=_coerce_int(
            source.get('pendu_free_plays_per_day', PENDU_FREE_PLAYS_PER_DAY),
            PENDU_FREE_PLAYS_PER_DAY,
            minimum=0,
            maximum=50,
        ),
        pendu_extra_play_cost=_coerce_int(
            source.get('pendu_extra_play_cost', PENDU_EXTRA_PLAY_COST),
            PENDU_EXTRA_PLAY_COST,
            minimum=0,
            maximum=10000,
        ),
        pendu_win_reward=_coerce_float(
            source.get('pendu_win_reward', DEFAULT_PENDU_WIN_REWARD),
            DEFAULT_PENDU_WIN_REWARD,
            minimum=0.0,
            maximum=100000.0,
        ),
        pendu_max_errors=_coerce_int(
            source.get('pendu_max_errors', DEFAULT_PENDU_MAX_ERRORS),
            DEFAULT_PENDU_MAX_ERRORS,
            minimum=1,
            maximum=26,
        ),
        pendu_loss_happiness_penalty=_coerce_float(
            source.get('pendu_loss_happiness_penalty', DEFAULT_PENDU_LOSS_HAPPINESS_PENALTY),
            DEFAULT_PENDU_LOSS_HAPPINESS_PENALTY,
            minimum=0.0,
            maximum=100.0,
        ),
        pendu_loss_energy_penalty=_coerce_float(
            source.get('pendu_loss_energy_penalty', DEFAULT_PENDU_LOSS_ENERGY_PENALTY),
            DEFAULT_PENDU_LOSS_ENERGY_PENALTY,
            minimum=0.0,
            maximum=100.0,
        ),
        agenda_reward=_coerce_float(
            source.get('agenda_reward', DEFAULT_AGENDA_REWARD),
            DEFAULT_AGENDA_REWARD,
            minimum=0.0,
            maximum=100000.0,
        ),
        agenda_required_catches=_coerce_int(
            source.get('agenda_required_catches', DEFAULT_AGENDA_REQUIRED_CATCHES),
            DEFAULT_AGENDA_REQUIRED_CATCHES,
            minimum=1,
            maximum=200,
        ),
        agenda_game_duration=_coerce_int(
            source.get('agenda_game_duration', DEFAULT_AGENDA_GAME_DURATION),
            DEFAULT_AGENDA_GAME_DURATION,
            minimum=5,
            maximum=3600,
        ),
        agenda_max_plays_per_day=_coerce_int(
            source.get('agenda_max_plays_per_day', DEFAULT_AGENDA_MAX_PLAYS_PER_DAY),
            DEFAULT_AGENDA_MAX_PLAYS_PER_DAY,
            minimum=0,
            maximum=50,
        ),
        truffe_reward=_coerce_float(
            source.get('truffe_reward', DEFAULT_TRUFFE_REWARD),
            DEFAULT_TRUFFE_REWARD,
            minimum=0.0,
            maximum=100000.0,
        ),
        truffe_max_clicks=_coerce_int(
            source.get('truffe_max_clicks', DEFAULT_TRUFFE_MAX_CLICKS),
            DEFAULT_TRUFFE_MAX_CLICKS,
            minimum=1,
            maximum=100,
        ),
        truffe_grid_size=_coerce_int(
            source.get('truffe_grid_size', DEFAULT_TRUFFE_GRID_SIZE),
            DEFAULT_TRUFFE_GRID_SIZE,
            minimum=3,
            maximum=100,
        ),
    )


def get_gameplay_settings() -> GameplaySettings:
    return _normalize_gameplay_settings(_load_blob(GAMEPLAY_SETTINGS_KEY))


def get_minigame_settings() -> MinigameSettings:
    return _normalize_minigame_settings(_load_blob(MINIGAME_SETTINGS_KEY))


def save_gameplay_settings(settings: GameplaySettings):
    set_config(GAMEPLAY_SETTINGS_KEY, json.dumps(settings.to_dict(), ensure_ascii=False, indent=2))
    invalidate_config_cache()


def save_minigame_settings(settings: MinigameSettings):
    set_config(MINIGAME_SETTINGS_KEY, json.dumps(settings.to_dict(), ensure_ascii=False, indent=2))
    invalidate_config_cache()


def build_gameplay_settings_from_form(form, current_settings=None):
    current = current_settings or get_gameplay_settings()
    thresholds = []
    for index in range(1, 4):
        threshold_value = form.get(f'gameplay_school_decay_threshold_{index}', '')
        multiplier_value = form.get(f'gameplay_school_decay_multiplier_{index}', '')
        if threshold_value == '' and multiplier_value == '':
            continue
        thresholds.append({
            'threshold': threshold_value,
            'multiplier': multiplier_value,
        })

    return _normalize_gameplay_settings({
        'snack_share_daily_limit': form.get('gameplay_snack_share_daily_limit', current.snack_share_daily_limit),
        'train_daily_cap': form.get('gameplay_train_daily_cap', current.train_daily_cap),
        'school_cooldown_minutes': form.get('gameplay_school_cooldown_minutes', current.school_cooldown_minutes),
        'school_xp_decay_thresholds': thresholds or current.school_xp_decay_thresholds,
        'school_xp_decay_floor': form.get('gameplay_school_xp_decay_floor', current.school_xp_decay_floor),
        'race_max_per_tick': form.get('gameplay_race_max_per_tick', current.race_max_per_tick),
    })


def build_minigame_settings_from_form(form, current_settings=None):
    current = current_settings or get_minigame_settings()
    return _normalize_minigame_settings({
        'pendu_free_plays_per_day': form.get('minigame_pendu_free_plays_per_day', current.pendu_free_plays_per_day),
        'pendu_extra_play_cost': form.get('minigame_pendu_extra_play_cost', current.pendu_extra_play_cost),
        'pendu_win_reward': form.get('minigame_pendu_win_reward', current.pendu_win_reward),
        'pendu_max_errors': form.get('minigame_pendu_max_errors', current.pendu_max_errors),
        'pendu_loss_happiness_penalty': form.get('minigame_pendu_loss_happiness_penalty', current.pendu_loss_happiness_penalty),
        'pendu_loss_energy_penalty': form.get('minigame_pendu_loss_energy_penalty', current.pendu_loss_energy_penalty),
        'agenda_reward': form.get('minigame_agenda_reward', current.agenda_reward),
        'agenda_required_catches': form.get('minigame_agenda_required_catches', current.agenda_required_catches),
        'agenda_game_duration': form.get('minigame_agenda_game_duration', current.agenda_game_duration),
        'agenda_max_plays_per_day': form.get('minigame_agenda_max_plays_per_day', current.agenda_max_plays_per_day),
        'truffe_reward': form.get('minigame_truffe_reward', current.truffe_reward),
        'truffe_max_clicks': form.get('minigame_truffe_max_clicks', current.truffe_max_clicks),
        'truffe_grid_size': form.get('minigame_truffe_grid_size', current.truffe_grid_size),
    })


def parse_bundle_gameplay_settings(payload) -> GameplaySettings:
    if not isinstance(payload, dict):
        raise ValidationError("Section gameplay invalide dans le JSON.")
    return _normalize_gameplay_settings(payload)


def parse_bundle_minigame_settings(payload) -> MinigameSettings:
    if not isinstance(payload, dict):
        raise ValidationError("Section minigames invalide dans le JSON.")
    return _normalize_minigame_settings(payload)
