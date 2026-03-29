"""helpers package — backward-compatible re-exports.

Tous les imports existants ``from helpers import X`` continuent de fonctionner.
Le code est desormais decoupe en sous-modules thematiques :

    helpers/config.py        — get_config, set_config, init_default_config
    helpers/db.py            — supports_row_level_locking, apply_row_lock
    helpers/time_helpers.py  — get_cooldown_remaining, format_duration_short, get_seconds_until
    helpers/veterinary.py    — check_vet_deadlines, send_to_abattoir, retire_pig_old_age, ...
    helpers/race.py          — ensure_next_race, run_race_if_needed, ...
    helpers/game_data.py     — get_cereals_dict, get_trainings_dict, ...
    helpers/market_helpers.py— get_market_unlock_progress, get_market_lock_reason
"""

# ── Sub-modules ──────────────────────────────────────────────────────────────

from helpers.config import (
    get_config,
    set_config,
    init_default_config,
    invalidate_config_cache,
)

from helpers.db import (
    supports_row_level_locking,
    apply_row_lock,
)

from helpers.time_helpers import (
    get_cooldown_remaining,
    format_duration_short,
    get_seconds_until,
)

from helpers.veterinary import (
    get_first_injured_pig,
    check_vet_deadlines,
    send_to_abattoir,
    retire_pig_old_age,
    get_dead_pigs_abattoir,
    get_legendary_pigs,
)

from helpers.race import (
    refresh_race_betting_lines,
    get_user_active_pigs,
    ensure_next_race,
    ensure_race_for_slot,
    run_race_if_needed,
    get_race_history_entries,
)

from helpers.game_data import (
    get_cereals_dict,
    get_trainings_dict,
    get_school_lessons_dict,
    get_all_cereals_dict,
    get_all_trainings_dict,
    get_all_school_lessons_dict,
    invalidate_game_data_cache,
)

from helpers.market_helpers import (
    get_market_unlock_progress,
    get_market_lock_reason,
)

# ── Services re-exports ─────────────────────────────────────────────────────

from services.finance_service import (
    adjust_user_balance,
    credit_user_balance,
    debit_user_balance,
    maybe_grant_emergency_relief,
    record_balance_transaction,
    release_pig_challenge_slot,
    reserve_pig_challenge_slot,
)

from services.market_service import (
    get_bourse_cereals,
    get_bourse_grid_data,
    get_bourse_movement_points,
    get_grain_market,
    get_grain_grid_pos,
    get_grain_surcharge,
    get_market_close_time,
    get_next_market_time,
    get_prix_moyen_groin,
    get_all_grain_surcharges,
    is_grain_blocked,
    is_market_open,
    move_bourse_cursor,
    resolve_auctions,
    update_vitrine,
    generate_auction_pig,
    resolve_market_history,
)

from services.pig_service import (
    adjust_pig_weight,
    apply_origin_bonus,
    build_unique_pig_name,
    calculate_pig_power,
    calculate_target_weight_kg,
    can_retire_into_heritage,
    check_level_up,
    clamp_pig_weight,
    create_offspring,
    create_preloaded_admin_pigs,
    generate_weight_kg_for_profile,
    get_active_listing_count,
    get_adoption_cost,
    get_feeding_cost_multiplier,
    get_freshness_bonus,
    get_lineage_label,
    get_max_pig_slots,
    get_pig_heritage_value,
    get_pig_performance_flags,
    get_pig_slot_count,
    get_weight_profile,
    get_weight_stat,
    is_pig_name_taken,
    normalize_pig_name,
    reset_snack_share_limit_if_needed,
    retire_pig_into_heritage,
    update_pig_state,
    xp_for_level,
)

from services.race_service import (
    build_course_schedule,
    calculate_bet_odds,
    calculate_ordered_finish_probability,
    count_pig_weekly_course_commitments,
    format_bet_label,
    generate_course_segments,
    get_bet_selection_ids,
    get_course_theme,
    get_next_race_time,
    get_pig_dashboard_status,
    get_pig_last_race_datetime,
    get_planned_pig_ids_for_slot,
    get_race_ready_pigs,
    get_upcoming_course_slots,
    get_user_weekly_bet_count,
    get_week_window,
    normalize_bet_type,
    parse_selection_ids,
    populate_race_participants,
    serialize_selection_ids,
    build_weighted_finish_order,
)
