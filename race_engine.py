import random
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Optional

from data import (
    RACE_MAX_TURNS,
    RACE_BASE_SPEED_VIT_MULT, RACE_BASE_SPEED_CONSTANT, RACE_MIN_FINAL_SPEED,
    RACE_STRATEGY_NEUTRAL, RACE_STRATEGY_SPEED_FACTOR,
    RACE_STRATEGY_FATIGUE_BASE, RACE_STRATEGY_FATIGUE_DIVISOR,
    RACE_FATIGUE_SPEED_PENALTY_FLOOR, RACE_FATIGUE_SPEED_PENALTY_DIVISOR,
    RACE_ECONOMY_THRESHOLD, RACE_ECONOMY_FATIGUE_RECOVERY,
    RACE_MONTEE_VIT_MULT, RACE_MONTEE_FORCE_MULT, RACE_MONTEE_TERRAIN_MOD,
    RACE_DESCENTE_TERRAIN_MOD, RACE_DESCENTE_STUMBLE_AGI_REF,
    RACE_DESCENTE_STUMBLE_AGI_DIV, RACE_DESCENTE_STUMBLE_CHANCE_DIV,
    RACE_STUMBLE_SPEED_MULT,
    RACE_VIRAGE_VIT_MULT, RACE_VIRAGE_AGI_MULT,
    RACE_VIRAGE_TERRAIN_MOD, RACE_BOUE_TERRAIN_MOD,
    RACE_DRAFT_MIN_DIST, RACE_DRAFT_MAX_DIST,
    RACE_DRAFT_BASE_CHANCE, RACE_DRAFT_STRATEGY_FACTOR, RACE_DRAFT_SPEED_BONUS,
    RACE_VARIANCE_MIN, RACE_VARIANCE_MAX,
)


@dataclass
class RaceParticipant:
    """Représentation typée d'un cochon en course.

    Utilisée en interne par CourseManager à la place d'un dictionnaire brut.
    Les attributs de stats sont en lecture seule pendant la course ; seuls
    distance, fatigue, has_draft, is_finished, finish_time et stumbled
    sont mutés par le moteur.
    """
    id: int
    name: str
    emoji: str
    # Stats de course (copiées depuis le modèle Pig ou un dict)
    vitesse: float = 10.0
    endurance: float = 10.0
    force: float = 10.0
    agilite: float = 10.0
    intelligence: float = 10.0
    moral: float = 10.0
    strategy: int = 50
    freshness: float = 100.0
    is_happy: bool = False
    speed_bonus_multiplier: float = 1.0
    # État mutable pendant la simulation
    distance: float = 0.0
    fatigue: float = 0.0
    has_draft: bool = False
    is_finished: bool = False
    finish_time: Optional[int] = None
    stumbled: bool = False

    @classmethod
    def from_source(cls, source) -> 'RaceParticipant':
        """Construit un RaceParticipant depuis un objet SQLAlchemy (Pig/Participant)
        ou un dictionnaire brut. Gère les deux cas de manière transparente."""
        def _get(key, default=10):
            if hasattr(source, key):
                return getattr(source, key)
            if isinstance(source, dict):
                return source.get(key, default)
            return default

        return cls(
            id=_get('id', 0),
            name=_get('name', 'Inconnu'),
            emoji=_get('emoji', '🐷'),
            vitesse=float(_get('vitesse', 10)),
            endurance=float(_get('endurance', 10)),
            force=float(_get('force', 10)),
            agilite=float(_get('agilite', 10)),
            intelligence=float(_get('intelligence', 10)),
            moral=float(_get('moral', 10)),
            strategy=int(_get('strategy', 50)),
            freshness=float(_get('freshness', 100.0)),
            is_happy=bool(_get('is_happy', float(_get('freshness', 100.0)) > 90.0)),
            speed_bonus_multiplier=float(_get('speed_bonus_multiplier', 1.0)),
        )


class CourseManager:
    """
    Simulateur de course de cochons 'Derby des Groins'
    Inspiré par le système tactique de 'Flamme Rouge'.

    Toutes les constantes d'équilibrage sont définies dans data.py
    (préfixe RACE_*) pour faciliter le tuning.
    Les participants sont des instances de RaceParticipant (dataclass).
    """

    def __init__(self, participants, segments):
        """
        :param participants: Liste d'objets (Pig, Participant) ou dicts.
        :param segments: Liste de dicts {'type': 'PLAT', 'length': 100}
        """
        self.participants: list[RaceParticipant] = [
            RaceParticipant.from_source(p) for p in participants
        ]
        self.segments = segments
        self.total_length = sum(s['length'] for s in segments)
        self.history: list[dict] = []
        self.current_turn: int = 0

    def run(self):
        """Lance la simulation complète."""
        while not all(p.is_finished for p in self.participants) and self.current_turn < RACE_MAX_TURNS:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()

        return self.history

    def simulate_turn(self):
        for p in self.participants:
            if p.is_finished:
                continue

            # Find current segment
            temp_dist = 0
            current_seg = self.segments[-1]
            for seg in self.segments:
                temp_dist += seg['length']
                if p.distance < temp_dist:
                    current_seg = seg
                    break

            progression = self.calculate_progression(p, current_seg)
            p.distance += progression

            if p.distance >= self.total_length:
                p.is_finished = True
                p.distance = self.total_length
                p.finish_time = self.current_turn

        # Calculate Aspiration (Drafting) for next turn
        sorted_pigs = sorted(self.participants, key=lambda x: x.distance, reverse=True)
        for i in range(len(sorted_pigs)):
            sorted_pigs[i].has_draft = False
            if i > 0:
                dist_diff = sorted_pigs[i-1].distance - sorted_pigs[i].distance
                if RACE_DRAFT_MIN_DIST < dist_diff < RACE_DRAFT_MAX_DIST:
                    draft_chance = RACE_DRAFT_BASE_CHANCE + (100 - sorted_pigs[i].strategy) * RACE_DRAFT_STRATEGY_FACTOR
                    if random.random() < draft_chance:
                        sorted_pigs[i].has_draft = True

    def calculate_progression(self, p: RaceParticipant, segment: dict) -> float:
        vit = p.vitesse
        end = p.endurance
        frc = p.force
        agi = p.agilite
        strat = p.strategy
        chance = (p.intelligence + p.moral) / 2.0

        # 1. Strategy Impact
        strat_speed_mod = 1.0 + (strat - RACE_STRATEGY_NEUTRAL) * RACE_STRATEGY_SPEED_FACTOR
        fatigue_gain = RACE_STRATEGY_FATIGUE_BASE + (strat / RACE_STRATEGY_FATIGUE_DIVISOR)

        # 2. Fatigue Malus
        speed_penalty = 1.0
        if p.fatigue > end:
            excess = p.fatigue - end
            speed_penalty = max(RACE_FATIGUE_SPEED_PENALTY_FLOOR, 1.0 - (excess / RACE_FATIGUE_SPEED_PENALTY_DIVISOR))

        # 3. Base Speed Calculation
        base_speed = (vit * RACE_BASE_SPEED_VIT_MULT) + RACE_BASE_SPEED_CONSTANT

        # 4. Terrain Adaptation
        terrain_mod = 1.0
        stumble_roll = False

        if segment['type'] == 'MONTEE':
            base_speed = (vit * RACE_MONTEE_VIT_MULT + frc * RACE_MONTEE_FORCE_MULT) + RACE_BASE_SPEED_CONSTANT
            terrain_mod = RACE_MONTEE_TERRAIN_MOD
        elif segment['type'] == 'DESCENTE':
            terrain_mod = RACE_DESCENTE_TERRAIN_MOD
            risk = max(0, (RACE_DESCENTE_STUMBLE_AGI_REF - agi) / RACE_DESCENTE_STUMBLE_AGI_DIV) - (chance / RACE_DESCENTE_STUMBLE_CHANCE_DIV)
            if random.random() < risk:
                stumble_roll = True
        elif segment['type'] in ['VIRAGE', 'BOUE']:
            base_speed = (vit * RACE_VIRAGE_VIT_MULT + agi * RACE_VIRAGE_AGI_MULT) + RACE_BASE_SPEED_CONSTANT
            terrain_mod = RACE_BOUE_TERRAIN_MOD if segment['type'] == 'BOUE' else RACE_VIRAGE_TERRAIN_MOD

        # 5. Final Speed for this turn
        freshness_factor = 0.9 + (max(0.0, min(100.0, p.freshness)) / 1000.0)
        final_speed = base_speed * strat_speed_mod * speed_penalty * terrain_mod * freshness_factor * p.speed_bonus_multiplier

        # 6. Apply stumble
        if stumble_roll:
            final_speed *= RACE_STUMBLE_SPEED_MULT
            p.stumbled = True
        else:
            p.stumbled = False

        # 7. Drafting Bonus
        if p.has_draft and not p.is_finished:
            final_speed += RACE_DRAFT_SPEED_BONUS

        # 8. Accumulate Fatigue
        if strat < RACE_ECONOMY_THRESHOLD:
            p.fatigue = max(0.0, p.fatigue - RACE_ECONOMY_FATIGUE_RECOVERY)
        else:
            p.fatigue += fatigue_gain

        # Variance
        final_speed *= random.uniform(RACE_VARIANCE_MIN, RACE_VARIANCE_MAX)

        return max(RACE_MIN_FINAL_SPEED, final_speed)

    def record_history(self):
        turn_data = {
            'turn': self.current_turn,
            'pigs': [
                {
                    'id': p.id,
                    'name': p.name,
                    'distance': round(p.distance, 2),
                    'fatigue': round(p.fatigue, 1),
                    'is_finished': p.is_finished,
                    'stumbled': p.stumbled,
                    'has_draft': p.has_draft,
                    'is_happy': p.is_happy,
                }
                for p in self.participants
            ],
        }
        self.history.append(turn_data)

    def to_json(self):
        return json.dumps(self.history)
