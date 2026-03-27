from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math

from sqlalchemy import func

from data import (
    BET_TYPES as DEFAULT_BET_TYPES,
    BREEDING_COST as DEFAULT_BREEDING_COST,
    DAILY_LOGIN_REWARD as DEFAULT_DAILY_LOGIN_REWARD,
    FEEDING_PRESSURE_PER_PIG as DEFAULT_FEEDING_PRESSURE_PER_PIG,
    MAX_BET_RACE as DEFAULT_MAX_BET_RACE,
    MAX_PIG_SLOTS,
    MIN_BET_RACE as DEFAULT_MIN_BET_RACE,
    RACE_APPEARANCE_REWARD as DEFAULT_RACE_APPEARANCE_REWARD,
    RACE_POSITION_REWARDS as DEFAULT_RACE_POSITION_REWARDS,
    REPLACEMENT_PIG_COST as DEFAULT_REPLACEMENT_PIG_COST,
    SECOND_PIG_COST as DEFAULT_SECOND_PIG_COST,
    WEEKLY_BACON_TICKETS as DEFAULT_WEEKLY_BACON_TICKETS,
    WEEKLY_RACE_QUOTA as DEFAULT_WEEKLY_RACE_QUOTA,
    JOURS_FR,
)
from extensions import db
from models import BalanceTransaction, Bet, GameConfig, Participant, Pig, Race, User

DEFAULT_WELCOME_BONUS = 100.0
DEFAULT_ADDITIONAL_PIG_STEP_COST = 15.0
DEFAULT_MAX_PAYOUT_RACE = 0.0
MAX_PARTICIPANTS_PER_RACE = 8
ECONOMY_POSITION_KEYS = (1, 2, 3)
SIMULATION_STRATEGIES = {
    'spread': 'Etale sur la semaine',
    'focus_friday': 'Optimise les meilleurs multiplicateurs',
}


@dataclass(frozen=True)
class EconomySettings:
    welcome_bonus: float
    daily_login_reward: float
    weekly_bacon_tickets: int
    weekly_race_quota: int
    race_appearance_reward: float
    race_position_rewards: dict[int, float]
    replacement_pig_cost: float
    second_pig_cost: float
    additional_pig_step_cost: float
    breeding_cost: float
    feeding_pressure_per_pig: float
    min_bet_race: float
    max_bet_race: float
    max_payout_race: float
    bet_types: dict[str, dict]


@dataclass(frozen=True)
class SimulationInputs:
    active_users: int
    pigs_per_user: int
    active_days_per_week: int
    races_per_pig_per_week: float
    strategy: str
    avg_stake: float
    tickets_used_per_user: float
    bet_type: str
    projection_weeks: int
    field_size: int


def _coerce_float(value, default, minimum=None, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return round(parsed, 2)


def _coerce_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = int(default)
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _load_json_config(key, default):
    from helpers.config import get_config

    raw = get_config(key, '')
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _serialize_json(data):
    return json.dumps(data, ensure_ascii=False)


def _normalize_bet_types(raw_overrides):
    bet_types = deepcopy(DEFAULT_BET_TYPES)
    overrides = raw_overrides if isinstance(raw_overrides, dict) else {}
    for key, meta in bet_types.items():
        override = overrides.get(key, {}) if isinstance(overrides.get(key), dict) else {}
        house_edge = _coerce_float(
            override.get('house_edge', meta.get('house_edge', 1.15)),
            meta.get('house_edge', 1.15),
            minimum=1.01,
            maximum=5.0,
        )
        meta['house_edge'] = house_edge
        meta['theoretical_return_pct'] = round((1 / house_edge) * 100, 1)
    return bet_types


def _normalize_position_rewards(raw_rewards):
    rewards = {}
    source = raw_rewards if isinstance(raw_rewards, dict) else {}
    for position in ECONOMY_POSITION_KEYS:
        rewards[position] = _coerce_float(
            source.get(str(position), source.get(position, DEFAULT_RACE_POSITION_REWARDS.get(position, 0.0))),
            DEFAULT_RACE_POSITION_REWARDS.get(position, 0.0),
            minimum=0.0,
        )
    return rewards


def _normalize_settings(
    welcome_bonus,
    daily_login_reward,
    weekly_bacon_tickets,
    weekly_race_quota,
    race_appearance_reward,
    race_position_rewards,
    replacement_pig_cost,
    second_pig_cost,
    additional_pig_step_cost,
    breeding_cost,
    feeding_pressure_per_pig,
    min_bet_race,
    max_bet_race,
    max_payout_race,
    bet_types,
):
    min_bet = _coerce_float(min_bet_race, DEFAULT_MIN_BET_RACE, minimum=1.0)
    max_bet = _coerce_float(max_bet_race, DEFAULT_MAX_BET_RACE, minimum=min_bet)
    payout_cap = _coerce_float(max_payout_race, DEFAULT_MAX_PAYOUT_RACE, minimum=0.0)
    return EconomySettings(
        welcome_bonus=_coerce_float(welcome_bonus, DEFAULT_WELCOME_BONUS, minimum=0.0),
        daily_login_reward=_coerce_float(daily_login_reward, DEFAULT_DAILY_LOGIN_REWARD, minimum=0.0),
        weekly_bacon_tickets=_coerce_int(weekly_bacon_tickets, DEFAULT_WEEKLY_BACON_TICKETS, minimum=0, maximum=20),
        weekly_race_quota=_coerce_int(weekly_race_quota, DEFAULT_WEEKLY_RACE_QUOTA, minimum=0, maximum=20),
        race_appearance_reward=_coerce_float(race_appearance_reward, DEFAULT_RACE_APPEARANCE_REWARD, minimum=0.0),
        race_position_rewards=_normalize_position_rewards(race_position_rewards),
        replacement_pig_cost=_coerce_float(replacement_pig_cost, DEFAULT_REPLACEMENT_PIG_COST, minimum=0.0),
        second_pig_cost=_coerce_float(second_pig_cost, DEFAULT_SECOND_PIG_COST, minimum=0.0),
        additional_pig_step_cost=_coerce_float(additional_pig_step_cost, DEFAULT_ADDITIONAL_PIG_STEP_COST, minimum=0.0),
        breeding_cost=_coerce_float(breeding_cost, DEFAULT_BREEDING_COST, minimum=0.0),
        feeding_pressure_per_pig=_coerce_float(
            feeding_pressure_per_pig,
            DEFAULT_FEEDING_PRESSURE_PER_PIG,
            minimum=0.0,
            maximum=3.0,
        ),
        min_bet_race=min_bet,
        max_bet_race=max_bet,
        max_payout_race=payout_cap,
        bet_types=_normalize_bet_types(bet_types),
    )


def get_economy_settings():
    from helpers.config import get_config

    return _normalize_settings(
        welcome_bonus=get_config('economy_welcome_bonus', str(DEFAULT_WELCOME_BONUS)),
        daily_login_reward=get_config('economy_daily_login_reward', str(DEFAULT_DAILY_LOGIN_REWARD)),
        weekly_bacon_tickets=get_config('economy_weekly_bacon_tickets', str(DEFAULT_WEEKLY_BACON_TICKETS)),
        weekly_race_quota=get_config('economy_weekly_race_quota', str(DEFAULT_WEEKLY_RACE_QUOTA)),
        race_appearance_reward=get_config('economy_race_appearance_reward', str(DEFAULT_RACE_APPEARANCE_REWARD)),
        race_position_rewards=_load_json_config('economy_race_position_rewards', DEFAULT_RACE_POSITION_REWARDS),
        replacement_pig_cost=get_config('economy_replacement_pig_cost', str(DEFAULT_REPLACEMENT_PIG_COST)),
        second_pig_cost=get_config('economy_second_pig_cost', str(DEFAULT_SECOND_PIG_COST)),
        additional_pig_step_cost=get_config('economy_additional_pig_step_cost', str(DEFAULT_ADDITIONAL_PIG_STEP_COST)),
        breeding_cost=get_config('economy_breeding_cost', str(DEFAULT_BREEDING_COST)),
        feeding_pressure_per_pig=get_config('economy_feeding_pressure_per_pig', str(DEFAULT_FEEDING_PRESSURE_PER_PIG)),
        min_bet_race=get_config('economy_min_bet_race', str(DEFAULT_MIN_BET_RACE)),
        max_bet_race=get_config('economy_max_bet_race', str(DEFAULT_MAX_BET_RACE)),
        max_payout_race=get_config('economy_max_payout_race', str(DEFAULT_MAX_PAYOUT_RACE)),
        bet_types=_load_json_config('economy_bet_type_overrides', {}),
    )


def build_economy_settings_from_form(form, current_settings=None):
    settings = current_settings or get_economy_settings()
    raw_bet_overrides = {}
    for bet_key, bet_meta in DEFAULT_BET_TYPES.items():
        raw_bet_overrides[bet_key] = {
            'house_edge': form.get(f'bet_house_edge_{bet_key}', bet_meta.get('house_edge', 1.15)),
        }

    raw_rewards = {
        position: form.get(f'race_reward_{position}', settings.race_position_rewards.get(position, 0.0))
        for position in ECONOMY_POSITION_KEYS
    }

    return _normalize_settings(
        welcome_bonus=form.get('welcome_bonus', settings.welcome_bonus),
        daily_login_reward=form.get('daily_login_reward', settings.daily_login_reward),
        weekly_bacon_tickets=form.get('weekly_bacon_tickets', settings.weekly_bacon_tickets),
        weekly_race_quota=form.get('weekly_race_quota', settings.weekly_race_quota),
        race_appearance_reward=form.get('race_appearance_reward', settings.race_appearance_reward),
        race_position_rewards=raw_rewards,
        replacement_pig_cost=form.get('replacement_pig_cost', settings.replacement_pig_cost),
        second_pig_cost=form.get('second_pig_cost', settings.second_pig_cost),
        additional_pig_step_cost=form.get('additional_pig_step_cost', settings.additional_pig_step_cost),
        breeding_cost=form.get('breeding_cost', settings.breeding_cost),
        feeding_pressure_per_pig=form.get('feeding_pressure_per_pig', settings.feeding_pressure_per_pig),
        min_bet_race=form.get('min_bet_race', settings.min_bet_race),
        max_bet_race=form.get('max_bet_race', settings.max_bet_race),
        max_payout_race=form.get('max_payout_race', settings.max_payout_race),
        bet_types=raw_bet_overrides,
    )


def save_economy_settings(settings):
    from helpers.config import invalidate_config_cache

    payload = {
        'economy_welcome_bonus': settings.welcome_bonus,
        'economy_daily_login_reward': settings.daily_login_reward,
        'economy_weekly_bacon_tickets': settings.weekly_bacon_tickets,
        'economy_weekly_race_quota': settings.weekly_race_quota,
        'economy_race_appearance_reward': settings.race_appearance_reward,
        'economy_race_position_rewards': _serialize_json({str(k): v for k, v in settings.race_position_rewards.items()}),
        'economy_replacement_pig_cost': settings.replacement_pig_cost,
        'economy_second_pig_cost': settings.second_pig_cost,
        'economy_additional_pig_step_cost': settings.additional_pig_step_cost,
        'economy_breeding_cost': settings.breeding_cost,
        'economy_feeding_pressure_per_pig': settings.feeding_pressure_per_pig,
        'economy_min_bet_race': settings.min_bet_race,
        'economy_max_bet_race': settings.max_bet_race,
        'economy_max_payout_race': settings.max_payout_race,
        'economy_bet_type_overrides': _serialize_json({
            key: {'house_edge': meta['house_edge']}
            for key, meta in settings.bet_types.items()
        }),
    }
    existing = {
        entry.key: entry
        for entry in GameConfig.query.filter(GameConfig.key.in_(list(payload.keys()))).all()
    }
    for key, value in payload.items():
        entry = existing.get(key)
        str_value = str(value)
        if entry:
            entry.value = str_value
        else:
            db.session.add(GameConfig(key=key, value=str_value))
    db.session.commit()
    invalidate_config_cache()


def get_configured_bet_types(settings=None):
    return deepcopy((settings or get_economy_settings()).bet_types)


def get_welcome_bonus_value(settings=None):
    return (settings or get_economy_settings()).welcome_bonus


def get_daily_login_reward_value(settings=None):
    return (settings or get_economy_settings()).daily_login_reward


def get_weekly_bacon_tickets_value(settings=None):
    return (settings or get_economy_settings()).weekly_bacon_tickets


def get_weekly_race_quota_value(settings=None):
    return (settings or get_economy_settings()).weekly_race_quota


def get_breeding_cost_value(settings=None):
    return (settings or get_economy_settings()).breeding_cost


def get_min_bet_race_value(settings=None):
    return (settings or get_economy_settings()).min_bet_race


def get_max_bet_race_value(settings=None):
    return (settings or get_economy_settings()).max_bet_race


def get_bet_limits(settings=None):
    economy = settings or get_economy_settings()
    return {
        'min_bet_race': economy.min_bet_race,
        'max_bet_race': economy.max_bet_race,
        'max_payout_race': economy.max_payout_race,
    }


def get_race_reward_settings(settings=None):
    economy = settings or get_economy_settings()
    return {
        'appearance_reward': economy.race_appearance_reward,
        'position_rewards': dict(economy.race_position_rewards),
    }


def calculate_adoption_cost_for_counts(active_count, slot_count=None, max_slots=None, settings=None):
    economy = settings or get_economy_settings()
    if max_slots is not None and slot_count is not None and slot_count >= max_slots:
        return None
    return get_adoption_cost_for_active_count(active_count, economy)


def get_feeding_multiplier_for_count(active_count, settings=None):
    return get_feeding_cost_multiplier_for_count(active_count, settings=settings)


def get_adoption_cost_for_active_count(active_count, settings=None):
    economy = settings or get_economy_settings()
    if active_count <= 0:
        return economy.replacement_pig_cost
    return round(
        economy.second_pig_cost + (max(0, active_count - 1) * economy.additional_pig_step_cost),
        2,
    )


def get_feeding_cost_multiplier_for_count(active_count, settings=None):
    economy = settings or get_economy_settings()
    if active_count <= 1:
        return 1.0
    return round(1.0 + ((active_count - 1) * economy.feeding_pressure_per_pig), 2)


def get_effective_bet_odds(raw_odds, amount, settings=None):
    economy = settings or get_economy_settings()
    odds = max(0.0, float(raw_odds or 0.0))
    stake = max(0.0, float(amount or 0.0))
    if odds <= 0 or stake <= 0:
        return 0.0
    if economy.max_payout_race > 0:
        odds = min(odds, economy.max_payout_race / stake)
    return round(math.floor(odds * 100) / 100, 2)


def calculate_potential_payout(amount, raw_odds, settings=None):
    effective_odds = get_effective_bet_odds(raw_odds, amount, settings=settings)
    return round(float(amount or 0.0) * effective_odds, 2)


def cap_bet_payout(payout_amount, settings=None):
    economy = settings or get_economy_settings()
    payout = round(float(payout_amount or 0.0), 2)
    if economy.max_payout_race <= 0:
        return payout
    return round(min(payout, economy.max_payout_race), 2)


def get_merged_race_themes(reward_multiplier_overrides=None):
    from helpers.config import DEFAULT_RACE_THEMES

    current_themes = _load_json_config('race_themes', {})
    overrides = reward_multiplier_overrides if isinstance(reward_multiplier_overrides, dict) else {}
    merged = {}
    for day_idx in range(7):
        key = str(day_idx)
        merged[key] = {
            **DEFAULT_RACE_THEMES.get(key, {}),
            **(current_themes.get(key, {}) if isinstance(current_themes, dict) else {}),
        }
        if key in overrides:
            merged[key]['reward_multiplier'] = _coerce_int(
                overrides.get(key),
                merged[key].get('reward_multiplier', 1),
                minimum=1,
                maximum=10,
            )
    return merged


def build_day_theme_rows(reward_multiplier_overrides=None):
    themes = get_merged_race_themes(reward_multiplier_overrides=reward_multiplier_overrides)
    rows = []
    for day_idx in range(7):
        key = str(day_idx)
        rows.append({
            'day': day_idx,
            'key': key,
            'label': JOURS_FR[day_idx],
            'theme_name': themes.get(key, {}).get('name', ''),
            'reward_multiplier': float(themes.get(key, {}).get('reward_multiplier', 1) or 1),
        })
    return rows


def build_day_reward_multipliers_from_form(form, fallback=None):
    base = {}
    for row in build_day_theme_rows():
        key = row['key']
        base[key] = row['reward_multiplier']
    if isinstance(fallback, dict):
        base.update({str(key): value for key, value in fallback.items()})
    for day_idx in range(7):
        key = str(day_idx)
        base[key] = _coerce_int(
            form.get(f'day_multiplier_{day_idx}', base.get(key, 1)),
            base.get(key, 1),
            minimum=1,
            maximum=10,
        )
    return base


def save_day_reward_multipliers(reward_multiplier_overrides):
    from helpers.config import invalidate_config_cache

    current_themes = get_merged_race_themes()
    for day_idx in range(7):
        key = str(day_idx)
        current_themes[key]['reward_multiplier'] = _coerce_int(
            reward_multiplier_overrides.get(key),
            current_themes[key].get('reward_multiplier', 1),
            minimum=1,
            maximum=10,
        )
    payload = {
        key: current_themes[key]
        for key in sorted(current_themes.keys(), key=int)
    }
    entry = GameConfig.query.filter_by(key='race_themes').first()
    value = _serialize_json(payload)
    if entry:
        entry.value = value
    else:
        db.session.add(GameConfig(key='race_themes', value=value))
    db.session.commit()
    invalidate_config_cache()


def _build_schedule_summary(reward_multiplier_overrides=None):
    from services.game_settings_service import get_game_settings

    settings = get_game_settings()
    themes = get_merged_race_themes(reward_multiplier_overrides=reward_multiplier_overrides)
    day_slots = []
    slot_multipliers = []
    weighted_multiplier_total = 0.0
    total_slots = 0
    for day_idx in range(7):
        key = str(day_idx)
        slot_count = len(settings.schedule_dict.get(key, []))
        reward_multiplier = float(themes.get(key, {}).get('reward_multiplier', 1) or 1)
        day_slots.append({
            'weekday': day_idx,
            'day_name': JOURS_FR[day_idx],
            'slot_count': slot_count,
            'reward_multiplier': reward_multiplier,
            'theme_name': themes.get(key, {}).get('name', ''),
        })
        slot_multipliers.extend([reward_multiplier] * slot_count)
        weighted_multiplier_total += slot_count * reward_multiplier
        total_slots += slot_count
    return {
        'day_slots': day_slots,
        'slot_multipliers': slot_multipliers,
        'weekly_slots': total_slots,
        'avg_reward_multiplier': round((weighted_multiplier_total / total_slots), 2) if total_slots else 0.0,
    }


def build_live_economy_snapshot(settings=None, reward_multiplier_overrides=None):
    from helpers.game_data import get_cereals_dict

    economy = settings or get_economy_settings()
    schedule_summary = _build_schedule_summary(reward_multiplier_overrides=reward_multiplier_overrides)
    alive_pig_rows = (
        db.session.query(Pig.user_id, func.count(Pig.id))
        .filter(Pig.is_alive == True)
        .group_by(Pig.user_id)
        .all()
    )
    alive_pig_counts = [int(count or 0) for _, count in alive_pig_rows]
    user_count = User.query.count()
    total_balance = float(db.session.query(func.coalesce(func.sum(User.balance), 0.0)).scalar() or 0.0)
    avg_balance = float(db.session.query(func.coalesce(func.avg(User.balance), 0.0)).scalar() or 0.0)
    finished_race_count = Race.query.filter_by(status='finished').count()
    open_race_count = Race.query.filter(Race.status.in_(['open', 'upcoming'])).count()
    field_sizes = [
        int(size or 0)
        for (size,) in (
            db.session.query(func.count(Participant.id))
            .join(Race, Participant.race_id == Race.id)
            .filter(Race.status == 'finished')
            .group_by(Participant.race_id)
            .all()
        )
    ]
    avg_field_size = round(sum(field_sizes) / len(field_sizes), 1) if field_sizes else float(MAX_PARTICIPANTS_PER_RACE)

    cutoff = datetime.utcnow() - timedelta(days=30)
    recent_bets = Bet.query.filter(Bet.placed_at >= cutoff)
    recent_bets_count = recent_bets.count()
    recent_avg_stake = float(
        db.session.query(func.coalesce(func.avg(Bet.amount), 0.0))
        .filter(Bet.placed_at >= cutoff)
        .scalar() or 0.0
    )
    recent_bets_per_user_per_week = 0.0
    if user_count:
        recent_bets_per_user_per_week = round((recent_bets_count / max(1, user_count)) / (30 / 7), 2)

    recent_tx_rows = (
        db.session.query(
            BalanceTransaction.reason_code,
            func.count(BalanceTransaction.id),
            func.coalesce(func.sum(BalanceTransaction.amount), 0.0),
        )
        .filter(BalanceTransaction.created_at >= cutoff)
        .group_by(BalanceTransaction.reason_code)
        .order_by(func.abs(func.coalesce(func.sum(BalanceTransaction.amount), 0.0)).desc())
        .limit(8)
        .all()
    )

    cereals = list(get_cereals_dict().values())
    cereal_costs = [float(cereal.get('cost') or 0.0) for cereal in cereals if cereal.get('cost') is not None]
    cheapest_cereal = None
    if cereals:
        cheapest_cereal = min(cereals, key=lambda cereal: float(cereal.get('cost') or 0.0))

    adoption_costs = []
    for active_count in range(MAX_PIG_SLOTS):
        adoption_costs.append({
            'from_active_count': active_count,
            'to_active_count': active_count + 1,
            'cost': get_adoption_cost_for_active_count(active_count, economy),
        })

    return {
        'users': user_count,
        'alive_pigs': sum(alive_pig_counts),
        'alive_pig_counts': alive_pig_counts,
        'avg_alive_pigs_per_user': round((sum(alive_pig_counts) / len(alive_pig_counts)), 2) if alive_pig_counts else 0.0,
        'total_balance': round(total_balance, 2),
        'avg_balance': round(avg_balance, 2),
        'finished_races': finished_race_count,
        'open_races': open_race_count,
        'avg_field_size': max(2, int(round(avg_field_size))),
        'recent_avg_stake': round(recent_avg_stake, 2),
        'recent_bets_count': recent_bets_count,
        'recent_bets_per_user_per_week': min(economy.weekly_bacon_tickets, max(0.0, recent_bets_per_user_per_week)),
        'recent_transactions': [
            {'reason_code': code, 'count': int(count or 0), 'amount': round(float(amount or 0.0), 2)}
            for code, count, amount in recent_tx_rows
        ],
        'cheapest_cereal': cheapest_cereal,
        'average_cereal_cost': round(sum(cereal_costs) / len(cereal_costs), 2) if cereal_costs else 0.0,
        'adoption_costs': adoption_costs,
        'weekly_capacity': schedule_summary['weekly_slots'] * MAX_PARTICIPANTS_PER_RACE,
        **schedule_summary,
    }


def get_default_simulation_inputs(snapshot, settings=None):
    economy = settings or get_economy_settings()
    suggested_stake = snapshot['recent_avg_stake'] or max(
        economy.min_bet_race,
        min(economy.max_bet_race, economy.min_bet_race * 2),
    )
    return SimulationInputs(
        active_users=max(1, snapshot['users'] or 1),
        pigs_per_user=max(1, min(MAX_PIG_SLOTS, int(round(snapshot['avg_alive_pigs_per_user'] or 1)) or 1)),
        active_days_per_week=7,
        races_per_pig_per_week=float(min(economy.weekly_race_quota, 3)),
        strategy='spread',
        avg_stake=round(min(economy.max_bet_race, max(economy.min_bet_race, suggested_stake)), 2),
        tickets_used_per_user=min(
            economy.weekly_bacon_tickets,
            max(0.0, snapshot['recent_bets_per_user_per_week']),
        ),
        bet_type='win',
        projection_weeks=12,
        field_size=max(2, min(MAX_PARTICIPANTS_PER_RACE, snapshot['avg_field_size'] or MAX_PARTICIPANTS_PER_RACE)),
    )


def build_simulation_inputs_from_form(form, snapshot, settings=None):
    defaults = get_default_simulation_inputs(snapshot, settings=settings)
    economy = settings or get_economy_settings()
    bet_type = form.get('sim_bet_type', defaults.bet_type)
    if bet_type not in DEFAULT_BET_TYPES:
        bet_type = defaults.bet_type
    strategy = form.get('sim_strategy', defaults.strategy)
    if strategy not in SIMULATION_STRATEGIES:
        strategy = defaults.strategy
    return SimulationInputs(
        active_users=_coerce_int(form.get('sim_active_users', defaults.active_users), defaults.active_users, minimum=1, maximum=5000),
        pigs_per_user=_coerce_int(form.get('sim_pigs_per_user', defaults.pigs_per_user), defaults.pigs_per_user, minimum=1, maximum=MAX_PIG_SLOTS),
        active_days_per_week=_coerce_int(form.get('sim_active_days', defaults.active_days_per_week), defaults.active_days_per_week, minimum=0, maximum=7),
        races_per_pig_per_week=_coerce_float(form.get('sim_races_per_pig', defaults.races_per_pig_per_week), defaults.races_per_pig_per_week, minimum=0.0, maximum=20.0),
        strategy=strategy,
        avg_stake=_coerce_float(form.get('sim_avg_stake', defaults.avg_stake), defaults.avg_stake, minimum=economy.min_bet_race, maximum=economy.max_bet_race),
        tickets_used_per_user=_coerce_float(form.get('sim_tickets_per_user', defaults.tickets_used_per_user), defaults.tickets_used_per_user, minimum=0.0, maximum=economy.weekly_bacon_tickets),
        bet_type=bet_type,
        projection_weeks=_coerce_int(form.get('sim_projection_weeks', defaults.projection_weeks), defaults.projection_weeks, minimum=1, maximum=52),
        field_size=_coerce_int(form.get('sim_field_size', defaults.field_size), defaults.field_size, minimum=2, maximum=MAX_PARTICIPANTS_PER_RACE),
    )


def _evenly_spaced_indices(total_count, wanted_count):
    if total_count <= 0 or wanted_count <= 0:
        return []
    if wanted_count >= total_count:
        return list(range(total_count))
    if wanted_count == 1:
        return [0]
    used = set()
    indices = []
    for step in range(wanted_count):
        raw_idx = round((step * (total_count - 1)) / (wanted_count - 1))
        idx = int(raw_idx)
        while idx in used and idx < total_count - 1:
            idx += 1
        while idx in used and idx > 0:
            idx -= 1
        if idx in used:
            continue
        used.add(idx)
        indices.append(idx)
    return sorted(indices)


def _select_spread_multipliers(target_count, day_slots):
    active_days = [day for day in day_slots if day['slot_count'] > 0]
    if target_count <= 0 or not active_days:
        return []
    if target_count <= len(active_days):
        return [active_days[idx]['reward_multiplier'] for idx in _evenly_spaced_indices(len(active_days), target_count)]
    selected = [day['reward_multiplier'] for day in active_days]
    leftovers = []
    for day in active_days:
        leftovers.extend([day['reward_multiplier']] * max(0, day['slot_count'] - 1))
    leftovers.sort(reverse=True)
    selected.extend(leftovers[:max(0, target_count - len(active_days))])
    return selected


def _select_focus_multipliers(target_count, slot_multipliers):
    if target_count <= 0 or not slot_multipliers:
        return []
    return sorted(slot_multipliers, reverse=True)[:target_count]


def _get_multiplier_total(races_per_pig, strategy, snapshot):
    whole_races = int(math.floor(max(0.0, races_per_pig)))
    fractional_race = max(0.0, races_per_pig) - whole_races
    required_count = whole_races + (1 if fractional_race > 0 else 0)
    if strategy == 'focus_friday':
        selected = _select_focus_multipliers(required_count, snapshot['slot_multipliers'])
    else:
        selected = _select_spread_multipliers(required_count, snapshot['day_slots'])
    total = sum(selected[:whole_races])
    if fractional_race > 0 and len(selected) > whole_races:
        total += selected[whole_races] * fractional_race
    return round(total, 3)


def _calculate_equal_field_ticket_metrics(bet_key, field_size, amount, settings):
    if bet_key not in settings.bet_types or field_size <= 0:
        return None
    bet_config = settings.bet_types[bet_key]
    selection_count = int(bet_config.get('selection_count', 1))
    if field_size < selection_count:
        return None
    probability = 1.0
    remaining_field = field_size
    for _ in range(selection_count):
        probability *= 1 / remaining_field
        remaining_field -= 1
    multiplier = 1.0
    if not bet_config.get('order_matters', True):
        multiplier *= math.factorial(selection_count)
        top_n = int(bet_config.get('top_n', selection_count))
        if top_n > selection_count:
            multiplier *= math.comb(top_n, selection_count)
    final_prob = min(probability * multiplier, 0.99)
    if final_prob <= 0:
        return None
    raw_odds = max(1.1, math.floor(((1 / final_prob) / bet_config['house_edge']) * 10) / 10)
    effective_odds = get_effective_bet_odds(raw_odds, amount, settings=settings)
    expected_return_pct = round(((final_prob * effective_odds) - 1.0) * 100, 1)
    return {
        'probability': final_prob,
        'raw_odds': raw_odds,
        'effective_odds': effective_odds,
        'expected_return_pct': expected_return_pct,
        'payout': round(amount * effective_odds, 2),
    }


def build_bet_type_analysis(settings=None, field_size=None):
    economy = settings or get_economy_settings()
    snapshot = build_live_economy_snapshot(economy)
    field = field_size or snapshot['avg_field_size']
    rows = []
    for bet_key, bet_meta in economy.bet_types.items():
        min_metrics = _calculate_equal_field_ticket_metrics(bet_key, field, economy.min_bet_race, economy)
        max_metrics = _calculate_equal_field_ticket_metrics(bet_key, field, economy.max_bet_race, economy)
        if not min_metrics:
            continue
        rows.append({
            'key': bet_key,
            'label': bet_meta['label'],
            'icon': bet_meta['icon'],
            'selection_count': int(bet_meta.get('selection_count', 1)),
            'house_edge': bet_meta['house_edge'],
            'odds': min_metrics['raw_odds'],
            'effective_odds_for_min': min_metrics['effective_odds'],
            'expected_return_pct': min_metrics['expected_return_pct'],
            'min_payout': min_metrics['payout'],
            'max_payout': max_metrics['payout'] if max_metrics else 0.0,
            'is_capped_on_max': bool(max_metrics and economy.max_payout_race > 0 and max_metrics['effective_odds'] < max_metrics['raw_odds']),
        })
    return rows


def _simulate_profile(pig_count, active_users, races_per_pig, active_days, strategy, avg_stake, tickets_per_user, bet_type, field_size, snapshot, settings):
    total_pigs = max(0, pig_count * active_users)
    desired_entries = total_pigs * max(0.0, races_per_pig)
    capacity = snapshot['weekly_capacity']
    capacity_scale = min(1.0, (capacity / desired_entries)) if desired_entries > 0 else 0.0
    effective_races_per_pig = max(0.0, races_per_pig) * capacity_scale
    expected_base_race_reward = settings.race_appearance_reward
    for position in ECONOMY_POSITION_KEYS:
        if field_size >= position:
            expected_base_race_reward += settings.race_position_rewards.get(position, 0.0) / field_size
    multiplier_total = _get_multiplier_total(effective_races_per_pig, strategy, snapshot)
    race_reward_per_pig = round(expected_base_race_reward * multiplier_total, 2)
    race_reward_per_user = round(race_reward_per_pig * pig_count, 2)
    cheapest_cereal_cost = float((snapshot['cheapest_cereal'] or {}).get('cost') or 0.0)
    feed_multiplier = get_feeding_cost_multiplier_for_count(pig_count, settings=settings)
    feed_cost_per_user = round(cheapest_cereal_cost * active_days * pig_count * feed_multiplier, 2)
    login_reward_per_user = round(active_days * settings.daily_login_reward, 2)
    ticket_metrics = _calculate_equal_field_ticket_metrics(bet_type, field_size, avg_stake, settings)
    betting_delta_per_user = 0.0
    if ticket_metrics and tickets_per_user > 0:
        betting_delta_per_user = round(tickets_per_user * avg_stake * (ticket_metrics['probability'] * ticket_metrics['effective_odds'] - 1.0), 2)
    net_per_user = round(login_reward_per_user + race_reward_per_user + betting_delta_per_user - feed_cost_per_user, 2)
    return {
        'pig_count': pig_count,
        'active_users': active_users,
        'active_days_per_week': active_days,
        'races_per_pig_requested': round(races_per_pig, 2),
        'races_per_pig_effective': round(effective_races_per_pig, 2),
        'capacity_usage_pct': round((desired_entries / capacity) * 100, 1) if capacity else 0.0,
        'field_size': field_size,
        'login_reward_per_user': login_reward_per_user,
        'race_reward_per_user': race_reward_per_user,
        'feed_cost_per_user': feed_cost_per_user,
        'betting_delta_per_user': betting_delta_per_user,
        'net_per_user': net_per_user,
        'total_weekly_delta': round(net_per_user * active_users, 2),
        'projected_circulation': round(snapshot['total_balance'], 2),
    }


def simulate_custom_scenario(inputs, settings=None, snapshot=None):
    economy = settings or get_economy_settings()
    live_snapshot = snapshot or build_live_economy_snapshot(economy)
    result = _simulate_profile(
        pig_count=inputs.pigs_per_user,
        active_users=inputs.active_users,
        races_per_pig=min(inputs.races_per_pig_per_week, economy.weekly_race_quota),
        active_days=inputs.active_days_per_week,
        strategy=inputs.strategy,
        avg_stake=inputs.avg_stake,
        tickets_per_user=min(inputs.tickets_used_per_user, economy.weekly_bacon_tickets),
        bet_type=inputs.bet_type,
        field_size=inputs.field_size,
        snapshot=live_snapshot,
        settings=economy,
    )
    result['projection_weeks'] = inputs.projection_weeks
    result['projected_circulation'] = round(
        live_snapshot['total_balance'] + (result['total_weekly_delta'] * inputs.projection_weeks),
        2,
    )
    return result


def build_profile_matrix(settings=None, snapshot=None):
    economy = settings or get_economy_settings()
    live_snapshot = snapshot or build_live_economy_snapshot(economy)
    rows = []
    for pig_count in range(1, MAX_PIG_SLOTS + 1):
        spread = _simulate_profile(
            pig_count=pig_count,
            active_users=1,
            races_per_pig=min(3, economy.weekly_race_quota),
            active_days=7,
            strategy='spread',
            avg_stake=economy.min_bet_race,
            tickets_per_user=0.0,
            bet_type='win',
            field_size=live_snapshot['avg_field_size'],
            snapshot=live_snapshot,
            settings=economy,
        )
        focus = _simulate_profile(
            pig_count=pig_count,
            active_users=1,
            races_per_pig=min(3, economy.weekly_race_quota),
            active_days=7,
            strategy='focus_friday',
            avg_stake=economy.min_bet_race,
            tickets_per_user=0.0,
            bet_type='win',
            field_size=live_snapshot['avg_field_size'],
            snapshot=live_snapshot,
            settings=economy,
        )
        adoption_cost = get_adoption_cost_for_active_count(pig_count - 1, economy) if pig_count > 1 else 0.0
        marginal_gain = round(focus['net_per_user'] - rows[-1]['focus_net'] if rows else focus['net_per_user'], 2)
        payback_weeks = round(adoption_cost / marginal_gain, 1) if pig_count > 1 and marginal_gain > 0 else None
        rows.append({
            'pig_count': pig_count,
            'spread_net': spread['net_per_user'],
            'focus_net': focus['net_per_user'],
            'adoption_cost': adoption_cost,
            'marginal_gain': marginal_gain if pig_count > 1 else None,
            'payback_weeks': payback_weeks,
        })
    return rows


def build_distribution_scenarios(settings=None, snapshot=None):
    economy = settings or get_economy_settings()
    live_snapshot = snapshot or build_live_economy_snapshot(economy)
    pig_counts = live_snapshot['alive_pig_counts']
    scenarios = []
    if not pig_counts:
        return scenarios

    live_tickets_per_user = min(economy.weekly_bacon_tickets, max(0.0, live_snapshot['recent_bets_per_user_per_week']))
    live_avg_stake = min(
        economy.max_bet_race,
        max(economy.min_bet_race, live_snapshot['recent_avg_stake'] or economy.min_bet_race),
    )

    for strategy in ('spread', 'focus_friday'):
        total_weekly_delta = 0.0
        total_login = 0.0
        total_race = 0.0
        total_feed = 0.0
        total_bets = 0.0
        for pig_count in pig_counts:
            result = _simulate_profile(
                pig_count=pig_count,
                active_users=1,
                races_per_pig=min(3, economy.weekly_race_quota),
                active_days=7,
                strategy=strategy,
                avg_stake=live_avg_stake,
                tickets_per_user=live_tickets_per_user,
                bet_type='win',
                field_size=live_snapshot['avg_field_size'],
                snapshot=live_snapshot,
                settings=economy,
            )
            total_weekly_delta += result['net_per_user']
            total_login += result['login_reward_per_user']
            total_race += result['race_reward_per_user']
            total_feed += result['feed_cost_per_user']
            total_bets += result['betting_delta_per_user']
        scenarios.append({
            'strategy': strategy,
            'label': SIMULATION_STRATEGIES[strategy],
            'users': len(pig_counts),
            'total_weekly_delta': round(total_weekly_delta, 2),
            'projected_4_weeks': round(live_snapshot['total_balance'] + (total_weekly_delta * 4), 2),
            'projected_12_weeks': round(live_snapshot['total_balance'] + (total_weekly_delta * 12), 2),
            'login_total': round(total_login, 2),
            'race_total': round(total_race, 2),
            'feed_total': round(total_feed, 2),
            'bet_total': round(total_bets, 2),
        })
    return scenarios


def build_admin_economy_context(settings=None, simulation_inputs=None, reward_multiplier_overrides=None):
    economy = settings or get_economy_settings()
    snapshot = build_live_economy_snapshot(economy, reward_multiplier_overrides=reward_multiplier_overrides)
    inputs = simulation_inputs or get_default_simulation_inputs(snapshot, settings=economy)
    custom_simulation = simulate_custom_scenario(inputs, settings=economy, snapshot=snapshot)
    circulation_delta_pct = 0.0
    if snapshot['total_balance'] > 0:
        circulation_delta_pct = round(
            ((custom_simulation['projected_circulation'] - snapshot['total_balance']) / snapshot['total_balance']) * 100,
            1,
        )
    custom_simulation['circulation_delta_pct'] = circulation_delta_pct
    return {
        'settings': economy,
        'snapshot': snapshot,
        'simulation_inputs': inputs,
        'custom_simulation': custom_simulation,
        'distribution_scenarios': build_distribution_scenarios(economy, snapshot=snapshot),
        'profile_rows': build_profile_matrix(economy, snapshot=snapshot),
        'bet_analysis_rows': build_bet_type_analysis(economy, field_size=inputs.field_size),
        'day_theme_rows': build_day_theme_rows(reward_multiplier_overrides=reward_multiplier_overrides),
        'strategy_choices': SIMULATION_STRATEGIES,
    }
