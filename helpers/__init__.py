"""helpers package — light compatibility layer.

Le runtime du projet importe désormais directement les sous-modules
(`helpers.config`, `helpers.race`, `helpers.game_data`, etc.).
Ce fichier ne ré-exporte plus que les helpers réellement définis dans le
package `helpers/`, afin d'éviter que `helpers` masque aussi des services.

Sous-modules disponibles :

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
    get_hangman_words,
    get_all_cereals_dict,
    get_all_trainings_dict,
    get_all_school_lessons_dict,
    get_all_hangman_words,
    invalidate_game_data_cache,
)

from helpers.market_helpers import (
    get_market_unlock_progress,
    get_market_lock_reason,
)

__all__ = [
    'get_config',
    'set_config',
    'init_default_config',
    'invalidate_config_cache',
    'supports_row_level_locking',
    'apply_row_lock',
    'get_cooldown_remaining',
    'format_duration_short',
    'get_seconds_until',
    'get_first_injured_pig',
    'check_vet_deadlines',
    'send_to_abattoir',
    'retire_pig_old_age',
    'get_dead_pigs_abattoir',
    'get_legendary_pigs',
    'refresh_race_betting_lines',
    'get_user_active_pigs',
    'ensure_next_race',
    'ensure_race_for_slot',
    'run_race_if_needed',
    'get_race_history_entries',
    'get_cereals_dict',
    'get_trainings_dict',
    'get_school_lessons_dict',
    'get_hangman_words',
    'get_all_cereals_dict',
    'get_all_trainings_dict',
    'get_all_school_lessons_dict',
    'get_all_hangman_words',
    'invalidate_game_data_cache',
    'get_market_unlock_progress',
    'get_market_lock_reason',
]
