from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json

from exceptions import ValidationError
from helpers.config import get_config, invalidate_config_cache, set_config
from services.admin_settings_service import save_admin_pig_settings, save_race_engine_settings_json
from services.economy_service import (
    _normalize_progression_settings,
    _normalize_settings,
    get_economy_settings,
    get_progression_settings,
    save_economy_settings,
    save_progression_settings,
)
from services.finance_service import (
    FinanceSettings,
    get_finance_settings,
    save_finance_settings,
)
from services.game_settings_service import get_game_settings
from services.gameplay_settings_service import (
    get_gameplay_settings,
    get_minigame_settings,
    parse_bundle_gameplay_settings,
    parse_bundle_minigame_settings,
    save_gameplay_settings,
    save_minigame_settings,
)
from services.pig_power_service import get_pig_settings
from services.race_engine_service import get_race_engine_settings

SCHEMA_VERSION = 1
EXPORT_FILENAME_PREFIX = 'derby-des-groins-settings'


def _utcnow_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _serialize_dataclass(settings):
    return asdict(settings)


def _serialize_bundle():
    finance = _serialize_dataclass(get_finance_settings())
    economy = _serialize_dataclass(get_economy_settings())
    progression = _serialize_dataclass(get_progression_settings())
    pigs = _serialize_dataclass(get_pig_settings())
    gameplay = get_gameplay_settings().to_dict()
    minigames = get_minigame_settings().to_dict()
    schedule_settings = get_game_settings()
    schedule = {
        'race_hour': schedule_settings.race_hour,
        'race_minute': schedule_settings.race_minute,
        'market_days_raw': schedule_settings.market_days_raw,
        'market_hour': schedule_settings.market_hour,
        'market_minute': schedule_settings.market_minute,
        'market_duration': schedule_settings.market_duration,
        'min_real_participants': schedule_settings.min_real_participants,
        'empty_race_mode': schedule_settings.empty_race_mode,
        'race_schedule': schedule_settings.schedule_dict,
    }
    bourse = {
        'surcharge_factor': float(get_config('bourse_surcharge_factor', '0.05') or 0.05),
        'movement_divisor': int(float(get_config('bourse_movement_divisor', '10') or 10)),
    }
    race_engine = get_race_engine_settings().to_dict()

    return {
        'schema_version': SCHEMA_VERSION,
        'exported_at': _utcnow_iso(),
        'finance': finance,
        'economy': economy,
        'progression': progression,
        'pigs': pigs,
        'gameplay': gameplay,
        'minigames': minigames,
        'schedule': schedule,
        'bourse': bourse,
        'race_engine': race_engine,
    }


def build_game_settings_bundle():
    return _serialize_bundle()


def build_game_settings_bundle_json():
    return json.dumps(build_game_settings_bundle(), ensure_ascii=False, indent=2, sort_keys=True)


def build_game_settings_bundle_filename():
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return f'{EXPORT_FILENAME_PREFIX}-{timestamp}.json'


def _parse_json(raw_json: str):
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'JSON invalide : {exc}') from exc
    if not isinstance(payload, dict):
        raise ValidationError("Le bundle doit être un objet JSON.")
    return payload


def _coerce_schedule_settings(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section schedule invalide dans le JSON.")
    race_schedule = payload.get('race_schedule', {})
    if isinstance(race_schedule, str):
        try:
            race_schedule = json.loads(race_schedule)
        except (TypeError, ValueError):
            race_schedule = {}
    return {
        'race_hour': str(int(float(payload.get('race_hour', 14)))),
        'race_minute': str(int(float(payload.get('race_minute', 0)))),
        'market_day': str(payload.get('market_days_raw', payload.get('market_day', '4'))),
        'market_hour': str(int(float(payload.get('market_hour', 13)))),
        'market_minute': str(int(float(payload.get('market_minute', 45)))),
        'market_duration': str(max(1, int(float(payload.get('market_duration', 120))))),
        'min_real_participants': str(max(0, int(float(payload.get('min_real_participants', 2))))),
        'empty_race_mode': str(payload.get('empty_race_mode', 'fill') or 'fill'),
        'race_schedule': json.dumps(race_schedule if isinstance(race_schedule, dict) else {}, ensure_ascii=False),
    }


def _coerce_bourse_settings(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section bourse invalide dans le JSON.")
    return {
        'bourse_surcharge_factor': str(max(0.0, float(payload.get('surcharge_factor', 0.05)))),
        'bourse_movement_divisor': str(max(1, int(float(payload.get('movement_divisor', 10))))),
    }


def _parse_finance_settings(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section finance invalide dans le JSON.")
    current = get_finance_settings()
    return FinanceSettings(
        emergency_threshold=float(payload.get('emergency_threshold', current.emergency_threshold)),
        emergency_amount=float(payload.get('emergency_amount', current.emergency_amount)),
        emergency_hours=int(float(payload.get('emergency_hours', current.emergency_hours))),
        casino_daily_cap=float(payload.get('casino_daily_cap', current.casino_daily_cap)),
        tax_threshold_1=float(payload.get('tax_threshold_1', current.tax_threshold_1)),
        tax_rate_1=float(payload.get('tax_rate_1', current.tax_rate_1)),
        tax_threshold_2=float(payload.get('tax_threshold_2', current.tax_threshold_2)),
        tax_rate_2=float(payload.get('tax_rate_2', current.tax_rate_2)),
        solidarity_threshold=float(payload.get('solidarity_threshold', current.solidarity_threshold)),
        solidarity_amount=float(payload.get('solidarity_amount', current.solidarity_amount)),
    )


def _parse_economy_settings(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section economy invalide dans le JSON.")
    current = get_economy_settings()
    return _normalize_settings(
        welcome_bonus=payload.get('welcome_bonus', current.welcome_bonus),
        daily_login_reward=payload.get('daily_login_reward', current.daily_login_reward),
        weekly_bacon_tickets=payload.get('weekly_bacon_tickets', current.weekly_bacon_tickets),
        weekly_race_quota=payload.get('weekly_race_quota', current.weekly_race_quota),
        race_appearance_reward=payload.get('race_appearance_reward', current.race_appearance_reward),
        race_position_rewards=payload.get('race_position_rewards', current.race_position_rewards),
        replacement_pig_cost=payload.get('replacement_pig_cost', current.replacement_pig_cost),
        second_pig_cost=payload.get('second_pig_cost', current.second_pig_cost),
        additional_pig_step_cost=payload.get('additional_pig_step_cost', current.additional_pig_step_cost),
        breeding_cost=payload.get('breeding_cost', current.breeding_cost),
        feeding_pressure_per_pig=payload.get('feeding_pressure_per_pig', current.feeding_pressure_per_pig),
        min_bet_race=payload.get('min_bet_race', current.min_bet_race),
        max_bet_race=payload.get('max_bet_race', current.max_bet_race),
        max_payout_race=payload.get('max_payout_race', current.max_payout_race),
        truffe_daily_limit=payload.get('truffe_daily_limit', current.truffe_daily_limit),
        truffe_replay_cost=payload.get('truffe_replay_cost', current.truffe_replay_cost),
        bets_per_race_limit=payload.get('bets_per_race_limit', current.bets_per_race_limit),
        bet_types=payload.get('bet_types', current.bet_types),
    )


def _parse_progression_settings(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section progression invalide dans le JSON.")
    current = get_progression_settings()
    return _normalize_progression_settings(
        hunger_decay_per_hour=payload.get('hunger_decay_per_hour', current.hunger_decay_per_hour),
        energy_regen_hunger_threshold=payload.get('energy_regen_hunger_threshold', current.energy_regen_hunger_threshold),
        energy_regen_per_hour=payload.get('energy_regen_per_hour', current.energy_regen_per_hour),
        energy_drain_per_hour=payload.get('energy_drain_per_hour', current.energy_drain_per_hour),
        low_hunger_happiness_drain_per_hour=payload.get('low_hunger_happiness_drain_per_hour', current.low_hunger_happiness_drain_per_hour),
        mid_hunger_happiness_drain_per_hour=payload.get('mid_hunger_happiness_drain_per_hour', current.mid_hunger_happiness_drain_per_hour),
        passive_happiness_regen_per_hour=payload.get('passive_happiness_regen_per_hour', current.passive_happiness_regen_per_hour),
        passive_happiness_regen_cap=payload.get('passive_happiness_regen_cap', current.passive_happiness_regen_cap),
        freshness_grace_hours=payload.get('freshness_grace_hours', current.freshness_grace_hours),
        freshness_decay_per_workday=payload.get('freshness_decay_per_workday', current.freshness_decay_per_workday),
        level_xp_base=payload.get('level_xp_base', current.level_xp_base),
        level_xp_exponent=payload.get('level_xp_exponent', current.level_xp_exponent),
        level_happiness_bonus=payload.get('level_happiness_bonus', current.level_happiness_bonus),
        training_stat_gain_multiplier=payload.get('training_stat_gain_multiplier', current.training_stat_gain_multiplier),
        training_happiness_multiplier=payload.get('training_happiness_multiplier', current.training_happiness_multiplier),
        school_stat_gain_multiplier=payload.get('school_stat_gain_multiplier', current.school_stat_gain_multiplier),
        school_xp_multiplier=payload.get('school_xp_multiplier', current.school_xp_multiplier),
        school_wrong_xp_multiplier=payload.get('school_wrong_xp_multiplier', current.school_wrong_xp_multiplier),
        school_happiness_multiplier=payload.get('school_happiness_multiplier', current.school_happiness_multiplier),
        school_wrong_happiness_multiplier=payload.get('school_wrong_happiness_multiplier', current.school_wrong_happiness_multiplier),
        typing_stat_gain_multiplier=payload.get('typing_stat_gain_multiplier', current.typing_stat_gain_multiplier),
        typing_xp_reward=payload.get('typing_xp_reward', current.typing_xp_reward),
        race_position_xp=payload.get('race_position_xp', current.race_position_xp),
        race_winner_stat_gain_multiplier=payload.get('race_winner_stat_gain_multiplier', current.race_winner_stat_gain_multiplier),
        race_podium_stat_gain_multiplier=payload.get('race_podium_stat_gain_multiplier', current.race_podium_stat_gain_multiplier),
        race_energy_cost=payload.get('race_energy_cost', current.race_energy_cost),
        race_hunger_cost=payload.get('race_hunger_cost', current.race_hunger_cost),
        race_weight_delta=payload.get('race_weight_delta', current.race_weight_delta),
        recent_race_penalty_under_24h=payload.get('recent_race_penalty_under_24h', current.recent_race_penalty_under_24h),
        recent_race_penalty_under_48h=payload.get('recent_race_penalty_under_48h', current.recent_race_penalty_under_48h),
        comeback_speed_bonus_multiplier=payload.get('comeback_speed_bonus_multiplier', current.comeback_speed_bonus_multiplier),
        vet_energy_cost=payload.get('vet_energy_cost', current.vet_energy_cost),
        vet_happiness_cost=payload.get('vet_happiness_cost', current.vet_happiness_cost),
    )


def _build_pig_form_payload(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Section pigs invalide dans le JSON.")
    current = get_pig_settings()
    return {
        'pig_max_slots': payload.get('max_slots', current.max_slots),
        'pig_retirement_min_wins': payload.get('retirement_min_wins', current.retirement_min_wins),
        'pig_default_max_races': payload.get('default_max_races', current.default_max_races),
        'pig_weight_default_kg': payload.get('weight_default_kg', current.weight_default_kg),
        'pig_weight_min_kg': payload.get('weight_min_kg', current.weight_min_kg),
        'pig_weight_max_kg': payload.get('weight_max_kg', current.weight_max_kg),
        'pig_weight_malus_ratio': payload.get('weight_malus_ratio', current.weight_malus_ratio),
        'pig_weight_malus_max': payload.get('weight_malus_max', current.weight_malus_max),
        'pig_injury_min_risk': payload.get('injury_min_risk', current.injury_min_risk),
        'pig_injury_max_risk': payload.get('injury_max_risk', current.injury_max_risk),
        'pig_vet_response_minutes': payload.get('vet_response_minutes', current.vet_response_minutes),
        'pig_weight_rules_json': json.dumps(
            payload.get('weight_rules', asdict(current.weight_rules)),
            ensure_ascii=False,
            indent=2,
        ),
    }


def import_game_settings_bundle(raw_json: str):
    payload = _parse_json(raw_json)
    schema_version = int(payload.get('schema_version', SCHEMA_VERSION) or SCHEMA_VERSION)
    if schema_version != SCHEMA_VERSION:
        raise ValidationError(
            f"Version de schéma non supportée ({schema_version}). Version attendue : {SCHEMA_VERSION}."
        )

    known_sections = {
        'schema_version', 'exported_at', 'finance', 'economy', 'progression',
        'pigs', 'gameplay', 'minigames', 'schedule', 'bourse', 'race_engine',
    }
    unknown = sorted(key for key in payload.keys() if key not in known_sections)
    if unknown:
        raise ValidationError(f"Sections inconnues dans le bundle : {', '.join(unknown)}")

    if 'finance' in payload:
        save_finance_settings(_parse_finance_settings(payload['finance']))
    if 'economy' in payload:
        save_economy_settings(_parse_economy_settings(payload['economy']))
    if 'progression' in payload:
        save_progression_settings(_parse_progression_settings(payload['progression']))
    if 'pigs' in payload:
        save_admin_pig_settings(_build_pig_form_payload(payload['pigs']), get_pig_settings())
    if 'gameplay' in payload:
        save_gameplay_settings(parse_bundle_gameplay_settings(payload['gameplay']))
    if 'minigames' in payload:
        save_minigame_settings(parse_bundle_minigame_settings(payload['minigames']))
    if 'schedule' in payload:
        for key, value in _coerce_schedule_settings(payload['schedule']).items():
            set_config(key, value)
    if 'bourse' in payload:
        for key, value in _coerce_bourse_settings(payload['bourse']).items():
            set_config(key, value)
    if 'race_engine' in payload:
        if not isinstance(payload['race_engine'], dict):
            raise ValidationError("Section race_engine invalide dans le JSON.")
        save_race_engine_settings_json(json.dumps(payload['race_engine'], ensure_ascii=False, indent=2))

    invalidate_config_cache()
    return build_game_settings_bundle()
