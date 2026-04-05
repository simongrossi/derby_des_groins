import json
import random
from dataclasses import dataclass, field
from typing import Optional

from config.race_engine_defaults import (
    RACE_BASE_SPEED_CONSTANT, RACE_VARIANCE_MAX, RACE_VARIANCE_MIN,
    RACE_STRATEGY_ECONOMY_MIN_MULT, RACE_STRATEGY_ATTACK_MAX_MULT,
    RACE_MONTEE_TERRAIN_MOD, RACE_DESCENTE_TERRAIN_MOD, RACE_VIRAGE_TERRAIN_MOD,
    RACE_BOUE_TERRAIN_MOD, RACE_STUMBLE_SPEED_MULT
)

DEFAULT_STRATEGY_PROFILE = {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}

# Paramètres pour garantir les 5 tours et 50 secondes avec une haute précision
SIMULATION_DURATION_SECONDS = 50
TARGET_SNAPSHOTS_PER_SECOND = 10 
FIXED_TOTAL_RACE_DISTANCE = 3000.0 # 5 tours de 600m
TARGET_TOTAL_TURNS = 500

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
    is_finished: bool = False
    finish_time: Optional[int] = None
    stumbled_cooldown: int = 0
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
        self.segments: list[Segment] = [Segment(type=s.get('type', 'PLAT'), length=float(s.get('length', 0))) for s in segments]
        # On force la distance totale si elle diffère de la constante pour rester synchrone avec le front
        self.total_length = sum(s.length for s in self.segments) or FIXED_TOTAL_RACE_DISTANCE
        self.history: list[dict] = []
        self.current_turn: int = 0
        self.rng = rng or random.Random()

    def run(self):
        # On simule jusqu'à 500 tours fixes
        while self.current_turn < TARGET_TOTAL_TURNS:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()
        return self.history

    def simulate_turn(self):
        for p in self.participants:
            if p.is_finished:
                p.current_speed = 0.0; p.visual_event = 'finished'; continue

            # 1. Identification du segment actuel (pour 3000m / 5 tours)
            dist_in_track = p.distance % 600.0 
            curr_seg = next((s for s in self.segments if dist_in_track < s.length), self.segments[0])
            
            # 2. Vitesse de base (ajustée pour 500 tours)
            # Moyenne attendue: 6m par tour.
            base_speed = (p.vitesse * 0.12 + p.endurance * 0.04 + 4.6)
            
            # 3. Multiplicateurs
            # Stratégie (0.9 à 1.1)
            strategy_mult = 0.9 + (p.strategy / 100.0) * 0.2
            # Fatigue malus (réduction jusqu'à -30%)
            fatigue_malus = max(0.7, 1.0 - (p.fatigue / 400.0))
            # Terrain
            terrain_mult = 1.0
            stumble_chance = 0.0
            if curr_seg.type == 'MONTEE': terrain_mult = RACE_MONTEE_TERRAIN_MOD
            elif curr_seg.type == 'DESCENTE': terrain_mult = RACE_DESCENTE_TERRAIN_MOD; stumble_chance = 0.02
            elif curr_seg.type == 'VIRAGE': terrain_mult = RACE_VIRAGE_TERRAIN_MOD; stumble_chance = 0.015
            elif curr_seg.type == 'BOUE': terrain_mult = RACE_BOUE_TERRAIN_MOD
            
            # 4. Calcul final
            variance = self.rng.uniform(RACE_VARIANCE_MIN, RACE_VARIANCE_MAX)
            final_speed = (
                base_speed
                * strategy_mult
                * fatigue_malus
                * terrain_mult
                * variance
                * max(0.0, p.recent_race_penalty_multiplier)
            )
            
            # Gestion Trébuchement
            if p.stumbled_cooldown > 0:
                final_speed *= RACE_STUMBLE_SPEED_MULT
                p.stumbled_cooldown -= 1
            elif stumble_chance > 0 and self.rng.random() < (stumble_chance * (1.5 - p.agilite/100.0)):
                p.stumbled_cooldown = 10 # 1 seconde de ralentissement
                p.visual_event = 'stumble'
            
            if p.has_draft: final_speed += 0.2
            
            p.current_speed = round(final_speed, 3)
            p.distance = min(self.total_length, p.distance + final_speed)
            
            if p.distance >= self.total_length:
                p.is_finished = True; p.finish_time = self.current_turn
            
            # Accumulation fatigue (par tour)
            p.fatigue += (p.strategy / 150.0) * (1.2 - p.endurance/100.0)
            
            # Events visuels
            if not p.visual_event or p.visual_event != 'stumble':
                p.visual_event = None
                if p.has_draft: p.visual_event = 'drafting'
                elif p.strategy >= 80: p.visual_event = 'sprint'
                elif p.fatigue > 150: p.visual_event = 'tired'

        self._apply_drafting()

    def _apply_drafting(self):
        sorted_pigs = sorted(self.participants, key=lambda p: p.distance, reverse=True)
        for i in range(1, len(sorted_pigs)):
            front, chaser = sorted_pigs[i-1], sorted_pigs[i]
            gap = front.distance - chaser.distance
            # Aspiration entre 1m et 4m
            chaser.has_draft = (1.0 <= gap <= 4.0)

    def record_history(self):
        self.history.append({
            'turn': self.current_turn,
            'pigs': [{
                'id': p.id, 'name': p.name, 'distance': round(p.distance, 2),
                'vitesse_actuelle': round(p.current_speed, 3),
                'fatigue': round(p.fatigue, 3),
                'is_finished': p.is_finished, 'has_draft': p.has_draft,
                'visual_event': p.visual_event
            } for p in self.participants],
        })

    def to_json(self):
        final_ranking = sorted(self.participants, key=lambda x: (x.finish_time or 9999, -x.distance))
        return json.dumps({
            'track_profile': 'PLAT',
            'segments': [{'type': s.type, 'length': s.length} for s in self.segments],
            'turns': self.history,
            'final_ranking_ids': [p.id for p in final_ranking],
            'total_race_distance': self.total_length
        })
