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

# Matchup rating — used only for the "Pronostics" indicator on the duel page.
# These weights describe how much each stat contributes to a global combat
# rating. They MUST sum to 1.0 (invariant covered by a unit test).
COMBAT_RATING_WEIGHTS = {
    'force':        0.35,
    'weight_kg':    0.20,
    'agilite':      0.20,
    'vitesse':      0.15,
    'moral':        0.05,
    'intelligence': 0.05,
}

# Normalisation cap per stat (value above which we flatten to 1.0).
COMBAT_RATING_STAT_CAPS = {
    'force':        100.0,
    'weight_kg':    200.0,
    'agilite':      100.0,
    'vitesse':      100.0,
    'moral':        100.0,
    'intelligence': 100.0,
}

# Thresholds for the gap-level label (in percentage points of p1_pct - p2_pct).
MATCHUP_LEVEL_THRESHOLDS = [
    (8.0,  'even'),
    (18.0, 'slight'),
    (30.0, 'marked'),
]  # anything above 30 → 'huge'


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


def compute_combat_rating(pig: PigState) -> float:
    """Return a 0–100 score describing the pig's overall combat strength.

    Unlike `_power()` (restricted to clash arbitration), this blends all the
    pertinent stats so the UI can present a fair "combat rating". Never used
    for gameplay resolution, only for display."""
    score = 0.0
    for stat_key, weight in COMBAT_RATING_WEIGHTS.items():
        value = float(getattr(pig, stat_key, 0.0) or 0.0)
        cap = COMBAT_RATING_STAT_CAPS[stat_key]
        normalized = _clamp(value / cap if cap else 0.0, 0.0, 1.0)
        score += normalized * weight * 100.0
    return _clamp(score, 0.0, 100.0)


def _level_for_gap(gap: float) -> str:
    for threshold, level in MATCHUP_LEVEL_THRESHOLDS:
        if gap < threshold:
            return level
    return 'huge'


def compute_matchup_odds(pig1: PigState, pig2: PigState) -> dict:
    """Return a dict describing the matchup for the "Pronostics" UI block.

    Keys returned:
        p1_rating / p2_rating : raw ratings 0–100
        p1_pct / p2_pct       : normalized to sum to 100
        gap                   : abs difference in percentage points
        level                 : 'even' | 'slight' | 'marked' | 'huge'
        favorite              : 'p1' | 'p2' | None (None iff p1_pct == p2_pct)
        stats                 : list of per-stat comparison dicts for the UI
    """
    r1 = compute_combat_rating(pig1)
    r2 = compute_combat_rating(pig2)
    total = r1 + r2 or 1.0
    p1_pct = round(r1 / total * 100.0, 1)
    p2_pct = round(100.0 - p1_pct, 1)
    gap = round(abs(p1_pct - p2_pct), 1)
    level = _level_for_gap(gap)

    if p1_pct > p2_pct:
        favorite = 'p1'
    elif p2_pct > p1_pct:
        favorite = 'p2'
    else:
        favorite = None

    stats_block = [
        {'key': 'force',        'label': 'Force',        'p1': pig1.force,        'p2': pig2.force,        'max': COMBAT_RATING_STAT_CAPS['force']},
        {'key': 'agilite',      'label': 'Agilité',      'p1': pig1.agilite,      'p2': pig2.agilite,      'max': COMBAT_RATING_STAT_CAPS['agilite']},
        {'key': 'vitesse',      'label': 'Vitesse',      'p1': pig1.vitesse,      'p2': pig2.vitesse,      'max': COMBAT_RATING_STAT_CAPS['vitesse']},
        {'key': 'weight_kg',    'label': 'Poids',        'p1': pig1.weight_kg,    'p2': pig2.weight_kg,    'max': COMBAT_RATING_STAT_CAPS['weight_kg']},
        {'key': 'moral',        'label': 'Moral',        'p1': pig1.moral,        'p2': pig2.moral,        'max': COMBAT_RATING_STAT_CAPS['moral']},
        {'key': 'intelligence', 'label': 'Intelligence', 'p1': pig1.intelligence, 'p2': pig2.intelligence, 'max': COMBAT_RATING_STAT_CAPS['intelligence']},
    ]

    return {
        'p1_rating': round(r1, 1),
        'p2_rating': round(r2, 1),
        'p1_pct': p1_pct,
        'p2_pct': p2_pct,
        'gap': gap,
        'level': level,
        'favorite': favorite,
        'stats': stats_block,
    }


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


class _RoundContext:
    """Carries per-round card flags across the 3 pairs. Also routes all
    push / endurance mutations so card effects (Patine, Miroir, Vol d'énergie)
    can intercept them at the right moment."""

    def __init__(self, p1: PigState, p2: PigState):
        self.p1 = p1
        self.p2 = p2
        # None means inactive. Otherwise the slot index (1-based) from which
        # the effect is active — lets "Patine played at slot 3" only protect slot 3.
        self.p1_immune_from = None   # Patine (no incoming push)
        self.p2_immune_from = None
        self.p1_mirror_from = None   # Miroir (50% of incoming push reflected)
        self.p2_mirror_from = None
        self.p1_vol_from = None      # Vol d'énergie (50% of opp's endurance costs)
        self.p2_vol_from = None
        self.current_slot = 0
        self.event_effects: list[str] = []

    def _pig(self, who: str) -> PigState:
        return self.p1 if who == 'p1' else self.p2

    def _opp(self, who: str) -> str:
        return 'p2' if who == 'p1' else 'p1'

    def _flag_active(self, attr: str) -> bool:
        slot = getattr(self, attr)
        return slot is not None and self.current_slot >= slot

    def _raw_push(self, who: str, distance: float):
        pig = self._pig(who)
        pig.position = _clamp(pig.position + distance, POSITION_MIN, POSITION_MAX)

    def push(self, who: str, distance: float, incoming: bool = True):
        """Push `who` by `distance` (positive = toward its own back edge).

        `incoming=True` means the push comes from the opponent (subject to
        Patine/Miroir). `incoming=False` is a self-slide (whiffed charge) and
        is never reduced by defensive cards."""
        if distance == 0:
            return
        if not incoming or distance < 0:
            self._raw_push(who, distance)
            return
        if self._flag_active(f'{who}_immune_from'):
            self.event_effects.append(f'patine_{who}_absorbs')
            return
        if self._flag_active(f'{who}_mirror_from'):
            half = distance * 0.5
            self._raw_push(who, half)
            self._raw_push(self._opp(who), half)
            self.event_effects.append(f'mirror_{who}_reflects')
            return
        self._raw_push(who, distance)

    def apply_endurance(self, who: str, delta: float):
        pig = self._pig(who)
        before = pig.endurance
        pig.endurance = _clamp(pig.endurance + delta, ENDURANCE_MIN, ENDURANCE_MAX)
        actual = pig.endurance - before
        if actual < 0:
            opp = self._opp(who)
            if self._flag_active(f'{opp}_vol_from'):
                opp_pig = self._pig(opp)
                recovered = min(50.0, abs(actual) * 0.5)
                opp_pig.endurance = _clamp(opp_pig.endurance + recovered, ENDURANCE_MIN, ENDURANCE_MAX)
                self.event_effects.append(f'vol_{opp}_steals')


def _resolve_pair(
    p1: PigState, a1: str,
    p2: PigState, a2: str,
    rng: random.Random,
    ctx: '_RoundContext | None' = None,
) -> dict:
    """Mutates p1/p2 and returns a structured event describing this pair.

    If `ctx` is provided, all mutations are routed through it so round-scoped
    card effects can intercept them."""
    if ctx is None:
        ctx = _RoundContext(p1, p2)  # legacy path, no flags

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
        ctx.apply_endurance('p1', ENDURANCE_DELTA[a1])
    if a2 in ENDURANCE_DELTA:
        ctx.apply_endurance('p2', ENDURANCE_DELTA[a2])

    outcome = _combine(a1, a2, rng, ctx, event)
    event['outcome'] = outcome
    if ctx.event_effects:
        event['card_effects'] = list(ctx.event_effects)
        ctx.event_effects.clear()

    event['p1_endurance_after'] = p1.endurance
    event['p2_endurance_after'] = p2.endurance
    event['p1_position_after'] = p1.position
    event['p2_position_after'] = p2.position
    return event


def _combine(a1: str, a2: str, rng: random.Random, ctx: _RoundContext, event: dict) -> str:
    p1, p2 = ctx.p1, ctx.p2
    pair = (a1, a2)

    if pair == ('charge', 'charge'):
        power1 = _power(p1)
        power2 = _power(p2)
        event['p1_power'] = power1
        event['p2_power'] = power2
        diff = power1 - power2
        if diff > 0:
            ctx.push('p2', diff / 8.0)
            return 'clash_p1_wins'
        if diff < 0:
            ctx.push('p1', abs(diff) / 8.0)
            return 'clash_p2_wins'
        return 'clash_tie'

    if pair == ('charge', 'ancrage'):
        ctx.apply_endurance('p1', -SPLAT_ENDURANCE_PENALTY)
        return 'p1_splat_on_ancrage'

    if pair == ('ancrage', 'charge'):
        ctx.apply_endurance('p2', -SPLAT_ENDURANCE_PENALTY)
        return 'p2_splat_on_ancrage'

    if pair == ('charge', 'esquive'):
        chance = _esquive_success_chance(p2)
        roll = rng.random()
        event['p2_esquive_chance'] = chance
        event['p2_esquive_roll'] = roll
        if roll < chance:
            ctx.push('p1', _slide_back_distance(p1), incoming=False)
            return 'p1_whiffs_p2_dodges'
        ctx.push('p2', _charge_distance(p1))
        return 'p1_lands_despite_esquive'

    if pair == ('esquive', 'charge'):
        chance = _esquive_success_chance(p1)
        roll = rng.random()
        event['p1_esquive_chance'] = chance
        event['p1_esquive_roll'] = roll
        if roll < chance:
            ctx.push('p2', _slide_back_distance(p2), incoming=False)
            return 'p2_whiffs_p1_dodges'
        ctx.push('p1', _charge_distance(p2))
        return 'p2_lands_despite_esquive'

    if pair == ('charge', 'repos'):
        ctx.push('p2', _charge_distance(p1) * CRIT_REST_MULTIPLIER)
        return 'p1_crit_on_rest'

    if pair == ('repos', 'charge'):
        ctx.push('p1', _charge_distance(p2) * CRIT_REST_MULTIPLIER)
        return 'p2_crit_on_rest'

    if pair == ('charge', 'null'):
        ctx.push('p2', _charge_distance(p1))
        return 'p1_charges_essouffle'

    if pair == ('null', 'charge'):
        ctx.push('p1', _charge_distance(p2))
        return 'p2_charges_essouffle'

    return 'no_contact'


def resolve_round(
    pig1: PigState,
    pig2: PigState,
    actions_p1: list[str],
    actions_p2: list[str],
    *,
    cards_p1: list[str | None] | None = None,
    cards_p2: list[str | None] | None = None,
    round_number: int = 1,
    rng: random.Random | None = None,
) -> tuple[PigState, PigState, list[dict]]:
    """Run the 3 action pairs of one round. Does NOT mutate the inputs.

    cards_pN is an optional list of length 3 where each entry is either None
    or a card id (from services.octogroin_cards.CARDS). At most one non-None
    entry per side is allowed (validated at service layer)."""

    if len(actions_p1) != 3 or len(actions_p2) != 3:
        raise ValueError("Chaque joueur doit programmer exactement 3 actions.")

    cards_p1 = list(cards_p1 or [None, None, None])
    cards_p2 = list(cards_p2 or [None, None, None])
    if len(cards_p1) != 3 or len(cards_p2) != 3:
        raise ValueError("cards_pN doit contenir 3 éléments (ou None).")

    allowed = set(ACTIONS)
    for a1, a2, c1, c2 in zip(actions_p1, actions_p2, cards_p1, cards_p2):
        if c1 is None and a1 not in allowed:
            raise ValueError(f"Action inconnue: {a1!r}.")
        if c2 is None and a2 not in allowed:
            raise ValueError(f"Action inconnue: {a2!r}.")

    # Max 1 card per side per round.
    if sum(1 for c in cards_p1 if c is not None) > 1:
        raise ValueError("Un seul atout par manche maximum (P1).")
    if sum(1 for c in cards_p2 if c is not None) > 1:
        raise ValueError("Un seul atout par manche maximum (P2).")

    from services.octogroin_cards import CARDS

    for c1, c2 in zip(cards_p1, cards_p2):
        if c1 is not None and c1 not in CARDS:
            raise ValueError(f"Carte inconnue: {c1!r}.")
        if c2 is not None and c2 not in CARDS:
            raise ValueError(f"Carte inconnue: {c2!r}.")

    rng = rng or random.Random()
    p1 = replace(pig1)
    p2 = replace(pig2)
    ctx = _RoundContext(p1, p2)

    # Cancellation pre-pass: contre_atout cancels opponent's first atout.
    p1_card_slot, p1_card = _find_card_slot(cards_p1)
    p2_card_slot, p2_card = _find_card_slot(cards_p2)
    cancelled_side: str | None = None

    if p1_card == 'contre_atout' and p2_card and CARDS[p2_card]['kind'] == 'atout':
        cards_p2[p2_card_slot] = None  # opponent's atout fizzles
        cancelled_side = 'p2'
    elif p2_card == 'contre_atout' and p1_card and CARDS[p1_card]['kind'] == 'atout':
        cards_p1[p1_card_slot] = None
        cancelled_side = 'p1'

    # Apply round-scoped flags from the remaining cards. Activation slot = where
    # the card is played (so Patine at slot 3 only covers slot 3, at slot 1
    # covers the whole round).
    _apply_round_flags(ctx, 'p1', cards_p1)
    _apply_round_flags(ctx, 'p2', cards_p2)

    events: list[dict] = []
    for step_idx in range(3):
        ctx.current_slot = step_idx + 1

        c1 = cards_p1[step_idx]
        c2 = cards_p2[step_idx]
        a1 = actions_p1[step_idx]
        a2 = actions_p2[step_idx]

        # When a player plays a card this slot, the action programmed is ignored.
        # The card's effect replaces the action.
        effective_a1 = _card_to_pseudo_action(c1) if c1 else a1
        effective_a2 = _card_to_pseudo_action(c2) if c2 else a2

        # Instant card effects: applied BEFORE the pair resolves, no combat.
        pre_notes = []
        if c1 == 'second_souffle':
            ctx.apply_endurance('p1', +40.0)
            pre_notes.append('second_souffle_p1')
        if c2 == 'second_souffle':
            ctx.apply_endurance('p2', +40.0)
            pre_notes.append('second_souffle_p2')
        if c1 == 'grognement':
            ctx.apply_endurance('p2', -25.0)
            pre_notes.append('grognement_p1_on_p2')
        if c2 == 'grognement':
            ctx.apply_endurance('p1', -25.0)
            pre_notes.append('grognement_p2_on_p1')

        event = _resolve_pair(p1, effective_a1, p2, effective_a2, rng, ctx=ctx)

        # Card-specific slot effects layered on top of the pair resolution:
        if c1 == 'berserk' and a2 in ('null', None):
            # no-op here; handled by effective_a1 below
            pass

        # Apply slot-scoped cards that modify the pair outcome:
        event = _apply_slot_card_effects(event, p1, p2, c1, c2, ctx, rng)

        # Record which cards were played this slot for the replay UI.
        if c1:
            event['p1_card'] = c1
        if c2:
            event['p2_card'] = c2
        if pre_notes:
            event.setdefault('card_effects', []).extend(pre_notes)
        if cancelled_side and step_idx == 0:
            event.setdefault('card_effects', []).append(f'contre_atout_cancels_{cancelled_side}')

        event['round'] = round_number
        event['step'] = step_idx + 1
        events.append(event)

        if p1.position >= POSITION_MAX or p2.position >= POSITION_MAX:
            break

    return p1, p2, events


def _find_card_slot(cards: list[str | None]) -> tuple[int, str | None]:
    for i, c in enumerate(cards):
        if c is not None:
            return i, c
    return -1, None


def _apply_round_flags(ctx: _RoundContext, who: str, cards: list[str | None]):
    slot_idx, card = _find_card_slot(cards)
    if card is None:
        return
    activation_slot = slot_idx + 1  # 1-based
    if card == 'patine':
        setattr(ctx, f'{who}_immune_from', activation_slot)
    elif card == 'miroir':
        setattr(ctx, f'{who}_mirror_from', activation_slot)
    elif card == 'vol_energie':
        setattr(ctx, f'{who}_vol_from', activation_slot)


def _card_to_pseudo_action(card_id: str) -> str:
    """Map a card played at a slot to the engine's pseudo-action for that slot."""
    # Slot-scoped atouts that behave like modified regular actions:
    if card_id == 'berserk':
        return 'charge'       # handled as charge, push doubled in post-pass
    if card_id == 'coup_bas':
        return 'charge'       # handled as charge, ignore ancrage in post-pass
    if card_id == 'feinte':
        return 'esquive'      # 100% success handled in post-pass
    if card_id == 'taurus':
        return 'ancrage'      # -50 splat handled in post-pass
    # All other cards (second_souffle, grognement, contre_atout, patine,
    # miroir, vol_energie) don't engage combat on the slot they're played —
    # they're either instant or round-scoped.
    return 'null'


def _apply_slot_card_effects(event: dict, p1: PigState, p2: PigState,
                             c1: str | None, c2: str | None,
                             ctx: _RoundContext, rng: random.Random) -> dict:
    """Post-resolution adjustments for slot-scoped atouts."""
    notes = event.setdefault('card_effects', [])

    # Berserk: double the push produced by the carrier's charge this pair.
    # We already resolved as a normal charge; we apply an extra push equal to
    # the base charge distance.
    if c1 == 'berserk' and event.get('outcome') in (
        'clash_p1_wins', 'p1_lands_despite_esquive', 'p1_crit_on_rest', 'p1_charges_essouffle'
    ):
        ctx.push('p2', _charge_distance(p1))
        notes.append('berserk_p1_extra_push')
    if c2 == 'berserk' and event.get('outcome') in (
        'clash_p2_wins', 'p2_lands_despite_esquive', 'p2_crit_on_rest', 'p2_charges_essouffle'
    ):
        ctx.push('p1', _charge_distance(p2))
        notes.append('berserk_p2_extra_push')

    # Coup bas: if we just splatted on opponent's ancrage, undo the splat and
    # instead perform a normal charge that lands.
    if c1 == 'coup_bas' and event.get('outcome') == 'p1_splat_on_ancrage':
        # Refund the splat penalty (-30 extra) and push opponent.
        ctx.apply_endurance('p1', +SPLAT_ENDURANCE_PENALTY)
        ctx.push('p2', _charge_distance(p1))
        event['outcome'] = 'p1_coup_bas_bypass'
        notes.append('coup_bas_p1_ignores_ancrage')
    if c2 == 'coup_bas' and event.get('outcome') == 'p2_splat_on_ancrage':
        ctx.apply_endurance('p2', +SPLAT_ENDURANCE_PENALTY)
        ctx.push('p1', _charge_distance(p2))
        event['outcome'] = 'p2_coup_bas_bypass'
        notes.append('coup_bas_p2_ignores_ancrage')

    # Feinte parfaite: esquive auto-succeeds. If the engine already resolved
    # the esquive as successful, nothing to do. If it resolved as a miss,
    # reverse the outcome.
    if c1 == 'feinte' and event.get('outcome') == 'p2_lands_despite_esquive':
        # Undo the push on p1, apply the whiff push on p2.
        ctx.push('p1', -_charge_distance(p2), incoming=False)  # undo p1's push
        ctx.push('p2', _slide_back_distance(p2), incoming=False)
        event['outcome'] = 'p2_whiffs_p1_dodges'
        notes.append('feinte_p1_forced_dodge')
    if c2 == 'feinte' and event.get('outcome') == 'p1_lands_despite_esquive':
        ctx.push('p2', -_charge_distance(p1), incoming=False)
        ctx.push('p1', _slide_back_distance(p1), incoming=False)
        event['outcome'] = 'p1_whiffs_p2_dodges'
        notes.append('feinte_p2_forced_dodge')

    # Taurus: supercharged ancrage. Base splat is -30; Taurus adds -20 more (-50 total).
    if c1 == 'taurus' and event.get('outcome') == 'p2_splat_on_ancrage':
        ctx.apply_endurance('p2', -20.0)
        notes.append('taurus_p1_extra_splat')
    if c2 == 'taurus' and event.get('outcome') == 'p1_splat_on_ancrage':
        ctx.apply_endurance('p1', -20.0)
        notes.append('taurus_p2_extra_splat')

    if not notes:
        event.pop('card_effects', None)
    return event


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
