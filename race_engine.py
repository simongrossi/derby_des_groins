import json
import random
from dataclasses import dataclass, field
from typing import Optional

from services.race_engine_service import RaceEngineSettings

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
        self.segments: list[Segment] = [Segment(type=s.get('type', 'PLAT'), length=float(s.get('length', 0))) for s in segments]
        self.total_length = sum(segment.length for segment in self.segments)
        self.history: list[dict] = []
        self.current_turn: int = 0
        self.rng = rng or random.Random()
        self._engine = RaceEngineSettings.load()

    def run(self):
        # Pour une course de 50 secondes avec un affichage a 0.5s par tour, on vise environ 100 tours.
        # On ajuste donc la vitesse de simulation pour que 3000m soient parcourus en ~100 tours.
        while not all(p.is_finished for p in self.participants) and self.current_turn < self._engine.max_turns:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()
        return self.history

    def simulate_turn(self):
        for p in self.participants:
            if p.is_finished:
                p.current_speed = 0.0; p.visual_event = 'finished'; continue

            # Vitesse moyenne cible : 3000m / 100 tours = 30m/tour
            # On booste les stats de base pour atteindre cette moyenne
            base_speed = (p.vitesse * 1.5 + p.endurance * 0.5 + self._engine.base_speed_constant + 15)
            
            # Application des multiplicateurs classiques
            strategy_mult = 0.8 + (p.strategy / 100.0) * 0.4 # 0.8 a 1.2
            freshness_factor = 0.9 + (p.freshness / 1000.0)
            variance = self.rng.uniform(0.95, 1.05)
            
            final_speed = base_speed * strategy_mult * freshness_factor * variance
            if p.has_draft: final_speed += 2.0
            
            p.current_speed = round(final_speed, 3)
            p.distance = min(self.total_length, p.distance + final_speed)
            
            if p.distance >= self.total_length:
                p.is_finished = True; p.finish_time = self.current_turn
            
            # Gestion fatigue simplifiee pour 100 tours
            p.fatigue += (p.strategy / 50.0)
            
            # Events visuels
            p.visual_event = None
            if p.has_draft: p.visual_event = 'drafting'
            elif p.strategy >= 70: p.visual_event = 'sprint'
            elif p.fatigue > 80: p.visual_event = 'tired'

        self._apply_drafting()

    def _apply_drafting(self):
        sorted_pigs = sorted(self.participants, key=lambda p: p.distance, reverse=True)
        for i in range(1, len(sorted_pigs)):
            front, chaser = sorted_pigs[i-1], sorted_pigs[i]
            gap = front.distance - chaser.distance
            chaser.has_draft = (5.0 <= gap <= 25.0)

    def record_history(self):
        self.history.append({
            'turn': self.current_turn,
            'pigs': [{
                'id': p.id, 'name': p.name, 'distance': round(p.distance, 2),
                'vitesse_actuelle': round(p.current_speed, 2), 'fatigue': round(p.fatigue, 2),
                'strategy': p.strategy, 'is_finished': p.is_finished,
                'has_draft': p.has_draft, 'visual_event': p.visual_event,
            } for p in self.participants],
        })

    def to_json(self):
        return json.dumps({
            'track_profile': 'PLAT',
            'segments': [{'type': s.type, 'length': s.length} for s in self.segments],
            'turns': self.history,
        })
