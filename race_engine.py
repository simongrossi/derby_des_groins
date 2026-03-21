import random
import json
import math

class CourseManager:
    """
    Simulateur de course de cochons 'Derby des Groins'
    Inspiré par le système tactique de 'Flamme Rouge'.
    """

    def __init__(self, participants, segments):
        """
        :param participants: Liste d'objets ou dicts contenant les stats des cochons.
        Chaque participant doit avoir id, name, emoji, vitesse, endurance, force, agilite, intelligence, moral, strategy.
        :param segments: Liste de dicts {'type': 'PLAT', 'length': 100}
        """
        self.participants = []
        for p in participants:
            # Map stats from DB model or dict
            self.participants.append({
                'id': p.id if hasattr(p, 'id') else p.get('id'),
                'name': p.name if hasattr(p, 'name') else p.get('name'),
                'emoji': p.emoji if hasattr(p, 'emoji') else p.get('emoji'),
                'vitesse': p.vitesse if hasattr(p, 'vitesse') else p.get('vitesse', 10),
                'endurance': p.endurance if hasattr(p, 'endurance') else p.get('endurance', 10),
                'force': p.force if hasattr(p, 'force') else p.get('force', 10),
                'agilite': p.agilite if hasattr(p, 'agilite') else p.get('agilite', 10),
                'intelligence': p.intelligence if hasattr(p, 'intelligence') else p.get('intelligence', 10),
                'moral': p.moral if hasattr(p, 'moral') else p.get('moral', 10),
                'strategy': p.strategy if hasattr(p, 'strategy') else p.get('strategy', 50),
                'distance': 0.0,
                'fatigue': 0.0,
                'has_draft': False,
                'is_finished': False,
                'finish_time': None,
                'stumbled': False, # For descent events
            })
        
        self.segments = segments
        self.total_length = sum(s['length'] for s in segments)
        self.history = []
        self.current_turn = 0

    def run(self):
        """Lance la simulation complète."""
        while not all(p['is_finished'] for p in self.participants) and self.current_turn < 500:
            self.current_turn += 1
            self.simulate_turn()
            self.record_history()
        
        return self.history

    def simulate_turn(self):
        # Determine current segment for each pig
        for p in self.participants:
            if p['is_finished']:
                continue
            
            # Find current segment
            temp_dist = 0
            current_seg = self.segments[-1]
            for seg in self.segments:
                temp_dist += seg['length']
                if p['distance'] < temp_dist:
                    current_seg = seg
                    break
            
            progression = self.calculate_progression(p, current_seg)
            p['distance'] += progression
            
            if p['distance'] >= self.total_length:
                p['is_finished'] = True
                p['distance'] = self.total_length
                p['finish_time'] = self.current_turn

        # Calculate Aspiration (Drafting) for next turn
        # Sorting by distance desc
        sorted_pigs = sorted(self.participants, key=lambda x: x['distance'], reverse=True)
        for i in range(len(sorted_pigs)):
            sorted_pigs[i]['has_draft'] = False # Reset
            if i > 0: # Not the leader
                # If close to the pig ahead (X = 3 units)
                dist_diff = sorted_pigs[i-1]['distance'] - sorted_pigs[i]['distance']
                if 0.5 < dist_diff < 4.0:
                    # Strategy affects drafting: Economy increases chance
                    draft_chance = 0.7 + (100 - sorted_pigs[i]['strategy']) * 0.003
                    if random.random() < draft_chance:
                        sorted_pigs[i]['has_draft'] = True

    def calculate_progression(self, p, segment):
        # Base stats
        vit = p['vitesse']
        end = p['endurance']
        frc = p['force']
        agi = p['agilite']
        strat = p['strategy']
        # Chance proxy: Average of intelligence and moral
        chance = (p['intelligence'] + p['moral']) / 2.0

        # 1. Strategy Impact
        # High attack (100) = +25% base speed, +100% fatigue gain, -20% agi
        # Economy (0) = -15% base speed, -50% fatigue gain (or slight recovery), +Drafting
        strat_speed_mod = 1.0 + (strat - 50) * 0.005 # 50 is neutral (1.0)
        fatigue_gain = 1.0 + (strat / 50.0) # 50 = 2.0, 100 = 3.0, 0 = 1.0
        
        # 2. Fatigue Malus
        # If fatigue > endurance, speed drops prop to excess
        speed_penalty = 1.0
        if p['fatigue'] > end:
            excess = p['fatigue'] - end
            speed_penalty = max(0.4, 1.0 - (excess / 100.0))
        
        # 3. Base Speed Calculation
        base_speed = (vit * 0.2) + 2.0 # Raw speed value around 4-6
        
        # 4. Terrain Adaptation
        terrain_mod = 1.0
        stumble_roll = False
        
        if segment['type'] == 'MONTEE':
            # Force replaces 50% of vitesse impact
            base_speed = (vit * 0.1 + frc * 0.1) + 2.0
            terrain_mod = 0.8 # Slower in hills
        elif segment['type'] == 'DESCENTE':
            terrain_mod = 1.4
            # Risk of stumbling if low agi
            risk = max(0, (40 - agi) / 200.0) - (chance / 500.0)
            if random.random() < risk:
                stumble_roll = True
        elif segment['type'] in ['VIRAGE', 'BOUE']:
            # Agilité is predominant
            base_speed = (vit * 0.05 + agi * 0.15) + 2.0
            terrain_mod = 0.7 if segment['type'] == 'BOUE' else 0.9

        # 5. Final Speed for this turn
        final_speed = base_speed * strat_speed_mod * speed_penalty * terrain_mod
        
        # 6. Apply stumble
        if stumble_roll:
            final_speed *= 0.3
            p['stumbled'] = True
        else:
            p['stumbled'] = False

        # 7. Drafting Bonus
        if p['has_draft'] and not p['is_finished']:
            final_speed += 0.8 # Nerfed slipstream boost
        
        # 8. Accumulate Fatigue
        # Economy (strat < 30) recovers a bit of fatigue
        if strat < 25:
            p['fatigue'] = max(0.0, p['fatigue'] - 0.1)
        else:
            p['fatigue'] += fatigue_gain
            
        # Variance
        final_speed *= random.uniform(0.95, 1.05)
        
        return max(0.5, final_speed)

    def record_history(self):
        turn_data = {
            'turn': self.current_turn,
            'pigs': []
        }
        for p in self.participants:
            turn_data['pigs'].append({
                'id': p['id'],
                'name': p['name'],
                'distance': round(p['distance'], 2),
                'fatigue': round(p['fatigue'], 1),
                'is_finished': p['is_finished'],
                'stumbled': p['stumbled'],
                'has_draft': p['has_draft']
            })
        self.history.append(turn_data)

    def to_json(self):
        return json.dumps(self.history)
