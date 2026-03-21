import json
import random
from dataclasses import dataclass, field
from typing import Optional

from data import (
    RACE_ATTACK_FATIGUE_EXPONENT,
    RACE_ATTACK_THRESHOLD,
    RACE_BASE_SPEED_CONSTANT,
    RACE_BOUE_AGI_MULT,
    RACE_BOUE_SPEED_CAP,
    RACE_BOUE_TERRAIN_MOD,
    RACE_DRAFT_BONUS_MAX,
    RACE_DRAFT_BONUS_MIN,
    RACE_DRAFT_MAX_DIST,
    RACE_DRAFT_MIN_DIST,
    RACE_DRAFT_NO_FATIGUE_BONUS,
    RACE_ENDURANCE_FATIGUE_DIVISOR,
    RACE_FATIGUE_HEADWIND_PENALTY,
    RACE_FATIGUE_SPEED_PENALTY_DIVISOR,
    RACE_FATIGUE_SPEED_PENALTY_FLOOR,
    RACE_MAX_TURNS,
    RACE_MIN_FINAL_SPEED,
    RACE_MONTEE_FORCE_MULT,
    RACE_MONTEE_SPEED_MULT,
    RACE_MONTEE_TERRAIN_MOD,
    RACE_NEUTRAL_MAX,
    RACE_RECENT_RACE_PENALTY_FLOOR,
    RACE_SEGMENT_SPEED_CAP,
    RACE_STUMBLE_BASE_CHANCE_DESCENTE,
    RACE_STUMBLE_BASE_CHANCE_VIRAGE,
    RACE_STUMBLE_SPEED_MULT,
    RACE_STRATEGY_ATTACK_MAX_MULT,
    RACE_STRATEGY_ECONOMY_MIN_MULT,
    RACE_STRATEGY_ECONOMY_RECOVERY,
    RACE_STRATEGY_NEUTRAL_FATIGUE,
    RACE_VARIANCE_MAX,
    RACE_VARIANCE_MIN,
    RACE_VIRAGE_AGI_MULT,
    RACE_VIRAGE_SPEED_CAP,
    RACE_VIRAGE_TERRAIN_MOD,
    RACE_DESCENTE_AGI_RISK_REDUCTION,
    RACE_DESCENTE_SPEED_MULT,
    RACE_DESCENTE_TERRAIN_MOD,
)

DEFAULT_STRATEGY_PROFILE = {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}


@dataclass(frozen=True)
class Segment:
    type: str
    length: float


@dataclass
class RaceParticipant:
    id: int
    name: str
    emoji: str
    vitesse: float = 10.0
    endurance: float = 10.0
    force: float = 10.0
    agilite: float = 10.0
    intelligence: float = 10.0
    moral: float = 10.0
    strategy: int = 50
    strategy_profile: dict = field(default_factory=lambda: DEFAULT_STRATEGY_PROFILE.copy())
    freshness: float = 100.0
    is_happy: bool = False
    speed_bonus_multiplier: float = 1.0
    recent_race_penalty_multiplier: float = 1.0
    distance: float = 0.0
    fatigue: float = 0.0
    has_draft: bool = False
    draft_bonus: float = 0.0
    skip_fatigue_this_turn: bool = False
    is_finished: bool = False
    finish_time: Optional[int] = None
    stumbled: bool = False
    current_speed: float = 0.0
    current_segment_type: str = 'PLAT'
    current_phase: str = 'phase_1'
    visual_event: Optional[str] = None

    @classmethod
    def from_source(cls, source) -> 'RaceParticipant':
        def _get(key, default=10):
            if hasattr(source, key):
                return getattr(source, key)
            if isinstance(source, dict):
                return source.get(key, default)
            return default

        strategy_profile = _get('strategy_profile', DEFAULT_STRATEGY_PROFILE)
        if isinstance(strategy_profile, str):
            try:
                strategy_profile = json.loads(strategy_profile)
            except (TypeError, ValueError):
                strategy_profile = DEFAULT_STRATEGY_PROFILE

        strategy_profile = {
            'phase_1': int(strategy_profile.get('phase_1', DEFAULT_STRATEGY_PROFILE['phase_1'])),
            'phase_2': int(strategy_profile.get('phase_2', DEFAULT_STRATEGY_PROFILE['phase_2'])),
            'phase_3': int(strategy_profile.get('phase_3', DEFAULT_STRATEGY_PROFILE['phase_3'])),
        }

        recent_penalty = float(_get('recent_race_penalty_multiplier', 1.0) or 1.0)
        recent_penalty = max(RACE_RECENT_RACE_PENALTY_FLOOR, min(1.0, recent_penalty))

        return cls(
            id=int(_get('id', 0)),
            name=_get('name', 'Inconnu'),
            emoji=_get('emoji', '🐷'),
            vitesse=float(_get('vitesse', 10)),
            endurance=float(_get('endurance', 10)),
            force=float(_get('force', 10)),
            agilite=float(_get('agilite', 10)),
            intelligence=float(_get('intelligence', 10)),
            moral=float(_get('moral', 10)),
            strategy=int(_get('strategy', 50)),
            strategy_profile=strategy_profile,
            freshness=float(_get('freshness', 100.0)),
            is_happy=bool(_get('is_happy', float(_get('freshness', 100.0)) > 90.0)),
            speed_bonus_multiplier=float(_get('speed_bonus_multiplier', 1.0)),
            recent_race_penalty_multiplier=recent_penalty,
        )


class CourseManager:
    def __init__(self, participants, segments, rng: Optional[random.Random] = None):
        self.participants: list[RaceParticipant] = [RaceParticipant.from_source(p) for p in participants]
        self.segments: list[Segment] = [Segment(type=s.get('type', 'PLAT'), length=float(s.get('length', 0))) for s in segments]
        self.total_length = sum(segment.length for segment in self.segments)
        self.history: list[dict] = []
        self.current_turn: int = 0
        self.rng = rng or random.Random()
        self.track_profile = self._compute_track_profile()

    def _compute_track_profile(self) -> str:
        terrain_lengths = {}
        for segment in self.segments:
            terrain_lengths[segment.type] = terrain_lengths.get(segment.type, 0.0) + segment.length
        filtered = {key: value for key, value in terrain_lengths.items() if key != 'PLAT'}
        profile_source = filtered or terrain_lengths or {'PLAT': 0.0}
        return max(profile_source, key=profile_source.get)

    def _locate_segment(self, distance: float) -> tuple[int, Segment]:
        covered = 0.0
        for index, segment in enumerate(self.segments):
            covered += segment.length
            if distance < covered:
                return index, segment
        return len(self.segments) - 1, self.segments[-1]

    def _resolve_phase_strategy(self, participant: RaceParticipant) -> tuple[str, int]:
        progress_ratio = 0.0 if self.total_length <= 0 else participant.distance / self.total_length
        if progress_ratio < 1 / 3:
            phase_key = 'phase_1'
        elif progress_ratio < 2 / 3:
            phase_key = 'phase_2'
        else:
            phase_key = 'phase_3'
        strategy_value = int(participant.strategy_profile.get(phase_key, participant.strategy))
        return phase_key, max(0, min(100, strategy_value))

    def _strategy_speed_multiplier(self, strategy: int) -> float:
        if strategy <= 30:
            ratio = strategy / 30.0 if strategy else 0.0
            return RACE_STRATEGY_ECONOMY_MIN_MULT + ((1.0 - RACE_STRATEGY_ECONOMY_MIN_MULT) * ratio)
        if strategy <= RACE_NEUTRAL_MAX:
            return 0.97 + (((strategy - 30) / max(1, RACE_NEUTRAL_MAX - 30)) * 0.03)
        ratio = (strategy - RACE_NEUTRAL_MAX) / max(1, 100 - RACE_NEUTRAL_MAX)
        return 1.0 + ((RACE_STRATEGY_ATTACK_MAX_MULT - 1.0) * ratio)

    def _fatigue_delta(self, participant: RaceParticipant, strategy: int) -> float:
        if participant.skip_fatigue_this_turn:
            return -RACE_DRAFT_NO_FATIGUE_BONUS
        if strategy <= 30:
            recovery_scale = (30 - strategy) / 30.0
            return -(RACE_STRATEGY_ECONOMY_RECOVERY * max(0.2, recovery_scale))
        if strategy <= RACE_NEUTRAL_MAX:
            return RACE_STRATEGY_NEUTRAL_FATIGUE + (strategy - 30) / 80.0
        attack_ratio = (strategy - RACE_NEUTRAL_MAX) / max(1, 100 - RACE_NEUTRAL_MAX)
        return RACE_STRATEGY_NEUTRAL_FATIGUE + (attack_ratio ** RACE_ATTACK_FATIGUE_EXPONENT) * 8.0

    def _fatigue_speed_penalty(self, participant: RaceParticipant) -> float:
        endurance_buffer = participant.endurance * RACE_ENDURANCE_FATIGUE_DIVISOR
        if participant.fatigue <= endurance_buffer:
            return 1.0
        excess = participant.fatigue - endurance_buffer
        return max(
            RACE_FATIGUE_SPEED_PENALTY_FLOOR,
            1.0 - (excess / RACE_FATIGUE_SPEED_PENALTY_DIVISOR),
        )

    def _segment_speed_profile(self, participant: RaceParticipant, segment: Segment) -> tuple[float, float, float, float]:
        terrain_mod = 1.0
        speed_cap = RACE_SEGMENT_SPEED_CAP
        stumble_chance = 0.0

        if segment.type == 'MONTEE':
            base_speed = (
                participant.vitesse * RACE_MONTEE_SPEED_MULT
                + participant.force * RACE_MONTEE_FORCE_MULT
                + RACE_BASE_SPEED_CONSTANT
            )
            terrain_mod = RACE_MONTEE_TERRAIN_MOD
        elif segment.type == 'DESCENTE':
            base_speed = (
                participant.vitesse * RACE_DESCENTE_SPEED_MULT
                + participant.agilite * 0.35
                + RACE_BASE_SPEED_CONSTANT
            )
            terrain_mod = RACE_DESCENTE_TERRAIN_MOD
            stumble_chance = max(
                0.0,
                RACE_STUMBLE_BASE_CHANCE_DESCENTE - (participant.agilite / RACE_DESCENTE_AGI_RISK_REDUCTION),
            )
        elif segment.type == 'VIRAGE':
            base_speed = (
                participant.vitesse * 0.35
                + participant.agilite * RACE_VIRAGE_AGI_MULT
                + participant.intelligence * 0.12
                + RACE_BASE_SPEED_CONSTANT
            )
            terrain_mod = RACE_VIRAGE_TERRAIN_MOD
            speed_cap = RACE_VIRAGE_SPEED_CAP
            stumble_chance = max(0.0, RACE_STUMBLE_BASE_CHANCE_VIRAGE - (participant.agilite / 220.0))
        elif segment.type == 'BOUE':
            base_speed = (
                participant.force * 0.45
                + participant.agilite * RACE_BOUE_AGI_MULT
                + participant.vitesse * 0.20
                + RACE_BASE_SPEED_CONSTANT
            )
            terrain_mod = RACE_BOUE_TERRAIN_MOD
            speed_cap = RACE_BOUE_SPEED_CAP
        else:
            base_speed = participant.vitesse * 0.75 + participant.endurance * 0.20 + RACE_BASE_SPEED_CONSTANT

        return base_speed, terrain_mod, min(0.45, stumble_chance), speed_cap

    def _leading_participant(self) -> Optional[RaceParticipant]:
        active = [participant for participant in self.participants if not participant.is_finished]
        return max(active, key=lambda participant: participant.distance, default=None)

    def _apply_drafting_for_next_turn(self):
        sorted_pigs = sorted(self.participants, key=lambda participant: participant.distance, reverse=True)
        leader = sorted_pigs[0] if sorted_pigs else None
        for participant in sorted_pigs:
            participant.has_draft = False
            participant.draft_bonus = 0.0
            participant.skip_fatigue_this_turn = False

        for index in range(1, len(sorted_pigs)):
            front = sorted_pigs[index - 1]
            chaser = sorted_pigs[index]
            distance_gap = front.distance - chaser.distance
            if RACE_DRAFT_MIN_DIST <= distance_gap <= RACE_DRAFT_MAX_DIST:
                closeness_ratio = 1.0 - ((distance_gap - RACE_DRAFT_MIN_DIST) / max(0.01, RACE_DRAFT_MAX_DIST - RACE_DRAFT_MIN_DIST))
                chaser.has_draft = True
                chaser.draft_bonus = RACE_DRAFT_BONUS_MIN + ((RACE_DRAFT_BONUS_MAX - RACE_DRAFT_BONUS_MIN) * closeness_ratio)
                chaser.skip_fatigue_this_turn = True

        if leader and not leader.is_finished:
            leader.fatigue += RACE_FATIGUE_HEADWIND_PENALTY

    def run(self):
        while not all(participant.is_finished for participant in self.participants) and self.current_turn < RACE_MAX_TURNS:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()
        return self.history

    def simulate_turn(self):
        for participant in self.participants:
            if participant.is_finished:
                participant.current_speed = 0.0
                participant.visual_event = 'finished'
                continue

            phase_key, strategy_value = self._resolve_phase_strategy(participant)
            participant.current_phase = phase_key
            participant.strategy = strategy_value
            _, segment = self._locate_segment(participant.distance)
            participant.current_segment_type = segment.type

            base_speed, terrain_mod, stumble_chance, speed_cap = self._segment_speed_profile(participant, segment)
            strategy_mult = self._strategy_speed_multiplier(strategy_value)
            fatigue_penalty = self._fatigue_speed_penalty(participant)
            freshness_factor = 0.88 + (max(0.0, min(100.0, participant.freshness)) / 833.0)
            variance = self.rng.uniform(RACE_VARIANCE_MIN, RACE_VARIANCE_MAX)

            final_speed = (
                base_speed
                * strategy_mult
                * terrain_mod
                * fatigue_penalty
                * freshness_factor
                * participant.speed_bonus_multiplier
                * participant.recent_race_penalty_multiplier
                * variance
            )

            if participant.has_draft:
                final_speed += participant.draft_bonus

            participant.stumbled = False
            if segment.type in {'DESCENTE', 'VIRAGE'} and self.rng.random() < stumble_chance:
                final_speed *= RACE_STUMBLE_SPEED_MULT
                participant.stumbled = True

            final_speed = max(RACE_MIN_FINAL_SPEED, min(speed_cap, final_speed))
            participant.current_speed = round(final_speed, 3)
            participant.distance = min(self.total_length, participant.distance + final_speed)

            fatigue_delta = self._fatigue_delta(participant, strategy_value)
            participant.fatigue = max(0.0, participant.fatigue + fatigue_delta)

            if participant.distance >= self.total_length:
                participant.is_finished = True
                participant.finish_time = self.current_turn

            participant.visual_event = None
            if participant.stumbled:
                participant.visual_event = 'stumble'
            elif participant.has_draft:
                participant.visual_event = 'drafting'
            elif strategy_value >= RACE_ATTACK_THRESHOLD:
                participant.visual_event = 'sprint'
            elif participant.fatigue > participant.endurance * RACE_ENDURANCE_FATIGUE_DIVISOR:
                participant.visual_event = 'tired'

        self._apply_drafting_for_next_turn()

    def record_history(self):
        self.history.append({
            'turn': self.current_turn,
            'pigs': [
                {
                    'id': participant.id,
                    'name': participant.name,
                    'distance': round(participant.distance, 2),
                    'vitesse_actuelle': round(participant.current_speed, 2),
                    'fatigue': round(participant.fatigue, 2),
                    'strategy': participant.strategy,
                    'phase': participant.current_phase,
                    'segment_type': participant.current_segment_type,
                    'is_finished': participant.is_finished,
                    'has_draft': participant.has_draft,
                    'stumbled': participant.stumbled,
                    'visual_event': participant.visual_event,
                }
                for participant in self.participants
            ],
        })

    def to_json(self):
        return json.dumps({
            'track_profile': self.track_profile,
            'segments': [{'type': segment.type, 'length': segment.length} for segment in self.segments],
            'turns': self.history,
        })
