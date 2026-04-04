import json
import random
from dataclasses import dataclass, field
from typing import Optional

from data import (
    RACE_ATTACK_FATIGUE_EXPONENT, RACE_ATTACK_THRESHOLD, RACE_BASE_SPEED_CONSTANT,
    RACE_BOUE_AGI_MULT, RACE_BOUE_SPEED_CAP, RACE_BOUE_TERRAIN_MOD,
    RACE_DRAFT_BONUS_MAX, RACE_DRAFT_BONUS_MIN, RACE_DRAFT_MAX_DIST,
    RACE_DRAFT_MIN_DIST, RACE_DRAFT_NO_FATIGUE_BONUS, RACE_ENDURANCE_FATIGUE_DIVISOR,
    RACE_FATIGUE_HEADWIND_PENALTY, RACE_FATIGUE_SPEED_PENALTY_DIVISOR,
    RACE_FATIGUE_SPEED_PENALTY_FLOOR, RACE_MAX_TURNS, RACE_MIN_FINAL_SPEED,
    RACE_MONTEE_FORCE_MULT, RACE_MONTEE_SPEED_MULT, RACE_MONTEE_TERRAIN_MOD,
    RACE_NEUTRAL_MAX, RACE_RECENT_RACE_PENALTY_FLOOR, RACE_SEGMENT_SPEED_CAP,
    RACE_STUMBLE_BASE_CHANCE_DESCENTE, RACE_STUMBLE_BASE_CHANCE_VIRAGE,
    RACE_STUMBLE_SPEED_MULT, RACE_STRATEGY_ATTACK_MAX_MULT,
    RACE_STRATEGY_ECONOMY_MIN_MULT, RACE_STRATEGY_ECONOMY_RECOVERY,
    RACE_STRATEGY_NEUTRAL_FATIGUE, RACE_VARIANCE_MAX, RACE_VARIANCE_MIN,
    RACE_VIRAGE_AGI_MULT, RACE_VIRAGE_SPEED_CAP, RACE_VIRAGE_TERRAIN_MOD, 
    RACE_DESCENTE_AGI_RISK_REDUCTION, RACE_DESCENTE_SPEED_MULT, RACE_DESCENTE_TERRAIN_MOD,
)

DEFAULT_STRATEGY_PROFILE = {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}

# Paramètres immuables pour garantir les 5 tours et 50 secondes
SIMULATION_DURATION_SECONDS = 50
TARGET_SNAPSHOTS_PER_SECOND = 10 
FIXED_TOTAL_RACE_DISTANCE = 3000.0 # 5 tours de 600m
TARGET_TOTAL_TURNS = 500

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
    recent_race_penalty_multiplier: float = 1.0
    distance: float = 0.0
    fatigue: float = 0.0
    has_draft: bool = False
    is_finished: bool = False
    finish_time: Optional[int] = None
    current_speed: float = 0.0
    visual_event: Optional[str] = None

    @classmethod
    def from_source(cls, source) -> 'RaceParticipant':
        def _get(k, d=10):
            if hasattr(source, k): return getattr(source, k)
            if isinstance(source, dict): return source.get(k, d)
            return d
        sp = _get('strategy_profile', DEFAULT_STRATEGY_PROFILE)
        if isinstance(sp, str):
            try: sp = json.loads(sp)
            except: sp = DEFAULT_STRATEGY_PROFILE
        return cls(
            id=int(_get('id', 0)), name=_get('name', 'Inconnu'), emoji=_get('emoji', '🐷'),
            vitesse=float(_get('vitesse', 10)), endurance=float(_get('endurance', 10)),
            force=float(_get('force', 10)), agilite=float(_get('agilite', 10)),
            intelligence=float(_get('intelligence', 10)), moral=float(_get('moral', 10)),
            strategy=int(_get('strategy', 50)), strategy_profile=sp,
            freshness=float(_get('freshness', 100.0)),
            recent_race_penalty_multiplier=float(_get('recent_race_penalty_multiplier', 1.0) or 1.0)
        )

class CourseManager:
    def __init__(self, participants, segments, rng: Optional[random.Random] = None):
        self.participants: list[RaceParticipant] = [RaceParticipant.from_source(p) for p in participants]
        self.history: list[dict] = []
        self.current_turn: int = 0
        self.rng = rng or random.Random()

    def run(self):
        # On force la simulation à durer exactement TARGET_TOTAL_TURNS pour l'animation
        while self.current_turn < TARGET_TOTAL_TURNS:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()
        return self.history

    def simulate_turn(self):
        for p in self.participants:
            if p.is_finished:
                p.current_speed = 0.0; continue
            
            # Vitesse de base pour atteindre ~3000m en 500 tours
            # 3000 / 500 = 6m par tour en moyenne
            base_speed = (p.vitesse * 0.15 + p.endurance * 0.05 + 4.5)
            
            strategy_mult = 0.9 + (p.strategy / 100.0) * 0.2
            variance = self.rng.uniform(0.98, 1.02)
            
            final_speed = base_speed * strategy_mult * variance
            if p.has_draft: final_speed += 0.2
            
            p.current_speed = round(final_speed, 3)
            p.distance = min(FIXED_TOTAL_RACE_DISTANCE, p.distance + final_speed)
            
            if p.distance >= FIXED_TOTAL_RACE_DISTANCE:
                p.is_finished = True
                p.finish_time = self.current_turn

        self._apply_drafting()

    def _apply_drafting(self):
        sorted_pigs = sorted(self.participants, key=lambda p: p.distance, reverse=True)
        for i in range(1, len(sorted_pigs)):
            front, chaser = sorted_pigs[i-1], sorted_pigs[i]
            gap = front.distance - chaser.distance
            chaser.has_draft = (1.0 <= gap <= 5.0)

    def record_history(self):
        self.history.append({
            'turn': self.current_turn,
            'pigs': [{
                'id': p.id, 'name': p.name, 'distance': round(p.distance, 2),
                'is_finished': p.is_finished, 'has_draft': p.has_draft
            } for p in self.participants],
        })

    def to_json(self):
        final_ranking = sorted(self.participants, key=lambda x: (x.finish_time or 9999, -x.distance))
        return json.dumps({
            'turns': self.history,
            'final_ranking_ids': [p.id for p in final_ranking],
            'total_race_distance': FIXED_TOTAL_RACE_DISTANCE
        })
