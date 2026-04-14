"""Pure resolution engine for the Octogroin mud-fighting duel.

A "round" is a group of 3 simultaneous action pairs. The engine is a pure
function: it reads two `PigState` snapshots + two action lists, returns the
updated snapshots + a list of events describing what happened. It does not
touch the DB — the service layer calls it, then persists the result.

Semantics of `position` (both pigs):
    - Each pig tracks independently how far it has been pushed toward its own
      back edge. Range [0, 100]. Start at 0 (centre).
    - A pig reaching 100 is "knocked out of the flaque".
    - Pushing the opponent => opponent's position goes UP.
    - Sliding yourself back (whiffed charge after a good dodge) => your own
      position goes UP.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Any

ACTIONS = ('charge', 'ancrage', 'esquive', 'repos')

ENDURANCE_DELTA = {
    'charge': -20.0,
    'ancrage': -10.0,
    'esquive': -15.0,
    'repos': +25.0,
}

POSITION_MIN = 0.0
POSITION_MAX = 100.0
ENDURANCE_MIN = 0.0
ENDURANCE_MAX = 100.0

SPLAT_ENDURANCE_PENALTY = 30.0  # attacker smashes into an Ancrage
CRIT_REST_MULTIPLIER = 1.5  # Charge on a Repos is a crit


@dataclass
class PigState:
    force: float
    weight_kg: float
    agilite: float
    intelligence: float
    moral: float
    vitesse: float
    position: float
    endurance: float

    def to_dict(self) -> dict:
        return {
            'force': self.force,
            'weight_kg': self.weight_kg,
            'agilite': self.agilite,
            'intelligence': self.intelligence,
            'moral': self.moral,
            'vitesse': self.vitesse,
            'position': self.position,
            'endurance': self.endurance,
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _power(pig: PigState) -> float:
    """Brute-force score used to arbitrate a Charge vs Charge clash."""
    return pig.force * (1.0 + pig.weight_kg / 200.0) + pig.vitesse * 0.5


def _esquive_success_chance(defender: PigState) -> float:
    # agility 0 -> 20%, agility 100 -> 95%, linear in between.
    chance = defender.agilite / 100.0
    return _clamp(chance, 0.2, 0.95)


def _apply_endurance(pig: PigState, delta: float) -> float:
    """Apply an endurance delta (negative = cost). Returns the clamped new value."""
    pig.endurance = _clamp(pig.endurance + delta, ENDURANCE_MIN, ENDURANCE_MAX)
    return pig.endurance


def _push_opponent(defender: PigState, distance: float) -> float:
    defender.position = _clamp(defender.position + distance, POSITION_MIN, POSITION_MAX)
    return defender.position


def _charge_distance(attacker: PigState) -> float:
    """Base push distance produced by a successful Charge."""
    return max(0.0, attacker.force) / 4.0


def _slide_back_distance(attacker: PigState) -> float:
    """How far the attacker slides toward its own edge on a whiffed Charge."""
    return max(0.0, attacker.force) / 3.0


def _resolve_pair(
    p1: PigState, a1: str,
    p2: PigState, a2: str,
    rng: random.Random,
) -> dict:
    """Mutates p1/p2 and returns a structured event describing this pair."""
    event: dict[str, Any] = {
        'p1_action_requested': a1,
        'p2_action_requested': a2,
        'p1_endurance_before': p1.endurance,
        'p2_endurance_before': p2.endurance,
        'p1_position_before': p1.position,
        'p2_position_before': p2.position,
        'p1_essouffle': False,
        'p2_essouffle': False,
    }

    # Essoufflé: 0 endurance => action fails (becomes 'null')
    if p1.endurance <= ENDURANCE_MIN:
        a1 = 'null'
        event['p1_essouffle'] = True
    if p2.endurance <= ENDURANCE_MIN:
        a2 = 'null'
        event['p2_essouffle'] = True

    event['p1_action'] = a1
    event['p2_action'] = a2

    # Apply endurance deltas first (costs / recovery) for non-null actions
    if a1 in ENDURANCE_DELTA:
        _apply_endurance(p1, ENDURANCE_DELTA[a1])
    if a2 in ENDURANCE_DELTA:
        _apply_endurance(p2, ENDURANCE_DELTA[a2])

    outcome = _combine(a1, a2, p1, p2, rng, event)
    event['outcome'] = outcome

    event['p1_endurance_after'] = p1.endurance
    event['p2_endurance_after'] = p2.endurance
    event['p1_position_after'] = p1.position
    event['p2_position_after'] = p2.position
    return event


def _combine(a1: str, a2: str, p1: PigState, p2: PigState, rng: random.Random, event: dict) -> str:
    pair = (a1, a2)

    if pair == ('charge', 'charge'):
        power1 = _power(p1)
        power2 = _power(p2)
        event['p1_power'] = power1
        event['p2_power'] = power2
        diff = power1 - power2
        if diff > 0:
            _push_opponent(p2, diff / 8.0)
            return 'clash_p1_wins'
        if diff < 0:
            _push_opponent(p1, abs(diff) / 8.0)
            return 'clash_p2_wins'
        return 'clash_tie'

    if pair == ('charge', 'ancrage'):
        _apply_endurance(p1, -SPLAT_ENDURANCE_PENALTY)
        return 'p1_splat_on_ancrage'

    if pair == ('ancrage', 'charge'):
        _apply_endurance(p2, -SPLAT_ENDURANCE_PENALTY)
        return 'p2_splat_on_ancrage'

    if pair == ('charge', 'esquive'):
        chance = _esquive_success_chance(p2)
        roll = rng.random()
        event['p2_esquive_chance'] = chance
        event['p2_esquive_roll'] = roll
        if roll < chance:
            _push_opponent(p1, _slide_back_distance(p1))
            return 'p1_whiffs_p2_dodges'
        _push_opponent(p2, _charge_distance(p1))
        return 'p1_lands_despite_esquive'

    if pair == ('esquive', 'charge'):
        chance = _esquive_success_chance(p1)
        roll = rng.random()
        event['p1_esquive_chance'] = chance
        event['p1_esquive_roll'] = roll
        if roll < chance:
            _push_opponent(p2, _slide_back_distance(p2))
            return 'p2_whiffs_p1_dodges'
        _push_opponent(p1, _charge_distance(p2))
        return 'p2_lands_despite_esquive'

    if pair == ('charge', 'repos'):
        _push_opponent(p2, _charge_distance(p1) * CRIT_REST_MULTIPLIER)
        return 'p1_crit_on_rest'

    if pair == ('repos', 'charge'):
        _push_opponent(p1, _charge_distance(p2) * CRIT_REST_MULTIPLIER)
        return 'p2_crit_on_rest'

    if pair == ('charge', 'null'):
        _push_opponent(p2, _charge_distance(p1))
        return 'p1_charges_essouffle'

    if pair == ('null', 'charge'):
        _push_opponent(p1, _charge_distance(p2))
        return 'p2_charges_essouffle'

    return 'no_contact'


def resolve_round(
    pig1: PigState,
    pig2: PigState,
    actions_p1: list[str],
    actions_p2: list[str],
    *,
    round_number: int = 1,
    rng: random.Random | None = None,
) -> tuple[PigState, PigState, list[dict]]:
    """Run the 3 action pairs of one round. Does NOT mutate the inputs.

    Returns (pig1_after, pig2_after, events) where events is a list of dicts
    ready to be appended to `duel.replay_json`."""

    if len(actions_p1) != 3 or len(actions_p2) != 3:
        raise ValueError("Chaque joueur doit programmer exactement 3 actions.")
    allowed = set(ACTIONS)
    if not all(a in allowed for a in actions_p1) or not all(a in allowed for a in actions_p2):
        raise ValueError("Action inconnue.")

    rng = rng or random.Random()
    p1 = replace(pig1)
    p2 = replace(pig2)

    events: list[dict] = []
    for step_idx, (a1, a2) in enumerate(zip(actions_p1, actions_p2), start=1):
        event = _resolve_pair(p1, a1, p2, a2, rng)
        event['round'] = round_number
        event['step'] = step_idx
        events.append(event)

        # If someone is knocked out mid-round, remaining steps are skipped.
        if p1.position >= POSITION_MAX or p2.position >= POSITION_MAX:
            break

    return p1, p2, events


MAX_ROUNDS = 5


def evaluate_end_of_duel(pig1: PigState, pig2: PigState, round_number: int) -> dict:
    """Decide whether the duel ends and who wins. Returns a dict with:
        - ended: bool
        - winner: 'p1', 'p2', 'draw', or None
        - reason: 'knockout_p1', 'knockout_p2', 'double_knockout',
                  'territorial_p1', 'territorial_p2', 'draw', or None
    """
    out1 = pig1.position >= POSITION_MAX
    out2 = pig2.position >= POSITION_MAX

    if out1 and out2:
        # Simultaneous double-knockout — tiebreak on whoever is LESS far gone,
        # fallback on remaining endurance.
        if pig1.position < pig2.position:
            return {'ended': True, 'winner': 'p1', 'reason': 'double_knockout_p1_closer'}
        if pig2.position < pig1.position:
            return {'ended': True, 'winner': 'p2', 'reason': 'double_knockout_p2_closer'}
        if pig1.endurance > pig2.endurance:
            return {'ended': True, 'winner': 'p1', 'reason': 'double_knockout_endurance'}
        if pig2.endurance > pig1.endurance:
            return {'ended': True, 'winner': 'p2', 'reason': 'double_knockout_endurance'}
        return {'ended': True, 'winner': 'draw', 'reason': 'double_knockout_tie'}

    if out1:
        return {'ended': True, 'winner': 'p2', 'reason': 'knockout_p1'}
    if out2:
        return {'ended': True, 'winner': 'p1', 'reason': 'knockout_p2'}

    if round_number >= MAX_ROUNDS:
        # Territorial advantage: whoever has been pushed back less wins.
        if pig1.position < pig2.position:
            return {'ended': True, 'winner': 'p1', 'reason': 'territorial_p1'}
        if pig2.position < pig1.position:
            return {'ended': True, 'winner': 'p2', 'reason': 'territorial_p2'}
        return {'ended': True, 'winner': 'draw', 'reason': 'draw'}

    return {'ended': False, 'winner': None, 'reason': None}
