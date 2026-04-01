from datetime import datetime, timedelta, time
from sqlalchemy import func, or_, update
import random
import math
from zoneinfo import ZoneInfo

from extensions import db
from models import (
    GameConfig, User, Pig, Race, Participant, Bet,
    BalanceTransaction, CoursePlan, Auction, GrainMarket,
    CerealItem, TrainingItem, SchoolLessonItem,
)
from data import (
    PIGS, PIG_ORIGINS, PIG_EMOJIS, PIG_NAME_PREFIXES, PIG_NAME_SUFFIXES, PRELOADED_PIG_NAMES,
    RARITIES, CHARCUTERIE, CHARCUTERIE_PREMIUM, EPITAPHS, BET_TYPES,
    EMERGENCY_RELIEF_THRESHOLD, EMERGENCY_RELIEF_AMOUNT, EMERGENCY_RELIEF_HOURS,
    SECOND_PIG_COST, REPLACEMENT_PIG_COST, MAX_PIG_SLOTS, BREEDING_COST,
    RETIREMENT_HERITAGE_MIN_WINS, FEEDING_PRESSURE_PER_PIG,
    DEFAULT_PIG_WEIGHT_KG, MIN_PIG_WEIGHT_KG, MAX_PIG_WEIGHT_KG,
    MIN_INJURY_RISK, MAX_INJURY_RISK, VET_RESPONSE_MINUTES,
    RACE_APPEARANCE_REWARD, RACE_POSITION_REWARDS,
    WEEKLY_RACE_QUOTA, JOURS_FR, IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
    MAX_WEIGHT_PERFORMANCE_MALUS, FRESHNESS_BONUS_HOURS, FRESHNESS_MORAL_BONUS,
    PIG_COURSE_SEGMENT_TYPES,
    BOURSE_GRID_SIZE, BOURSE_GRID_VALUES, BOURSE_DEFAULT_POS,
    BOURSE_BLOCK_MIN, BOURSE_BLOCK_MAX, BOURSE_SURCHARGE_FACTOR,
    BOURSE_MOVEMENT_DIVISOR, BOURSE_MIN_MOVEMENT,
    BOURSE_GRAIN_LAYOUT, CEREALS,
)
from race_engine import CourseManager
from services.finance_service import credit_user_balance


# ─── HELPERS CONFIG ─────────────────────────────────────────────────────────

def get_config(key, default=''):
    c = GameConfig.query.filter_by(key=key).first()
    return c.value if c else default

def set_config(key, value):
    c = GameConfig.query.filter_by(key=key).first()
    if c:
        c.value = str(value)
    else:
        db.session.add(GameConfig(key=key, value=str(value)))
    db.session.commit()

def init_default_config():
    defaults = {
        'race_hour': '14',
        'race_minute': '00',
        'market_day': '4',
        'market_hour': '13',
        'market_minute': '45',
        'market_duration': '120',
        'min_real_participants': '2',
        'empty_race_mode': 'fill',
        'truffe_daily_limit': '1',
        'bets_per_race_limit': '1',
    }
    for k, v in defaults.items():
        if not GameConfig.query.filter_by(key=k).first():
            db.session.add(GameConfig(key=k, value=v))
    db.session.commit()


# ─── HELPERS COCHON ─────────────────────────────────────────────────────────
 
PARIS_TZ = ZoneInfo('Europe/Paris')
WEEKEND_TRUCE_START = time(18, 0)
WEEKEND_TRUCE_END = time(8, 0)

def get_freshness_bonus(pig):
    if not pig or not pig.last_fed_at:
        return {'active': False, 'multiplier': 1.0, 'bonus_percent': 0.0, 'hours_remaining': 0.0}
    elapsed_hours = max(0.0, (datetime.utcnow() - pig.last_fed_at).total_seconds() / 3600.0)
    active = elapsed_hours < FRESHNESS_BONUS_HOURS
    remaining = max(0.0, FRESHNESS_BONUS_HOURS - elapsed_hours)
    return {
        'active': active,
        'multiplier': round(1.0 + FRESHNESS_MORAL_BONUS, 3) if active else 1.0,
        'bonus_percent': round(FRESHNESS_MORAL_BONUS * 100, 1) if active else 0.0,
        'hours_remaining': round(remaining, 2),
    }

def get_weight_profile(pig):
    current_weight = clamp_pig_weight(pig.weight_kg or DEFAULT_PIG_WEIGHT_KG)
    ideal_weight = calculate_target_weight_kg(pig)
    tolerance = round(10.0 + (pig.endurance * 0.08) + (pig.force * 0.04), 1)
    delta = round(current_weight - ideal_weight, 1)
    abs_delta = abs(delta)
    race_factor = max(0.82, min(1.06, 1.06 - ((abs_delta / max(tolerance * 2.2, 1.0)) * 0.24)))
    injury_factor = 1.0 + min(0.35, abs_delta / max(tolerance * 3.5, 1.0))

    force_mod = 1.0
    agilite_mod = 1.0
    if delta > 0:
        ratio = delta / max(tolerance, 1.0)
        force_mod = 1.0 + min(0.35, ratio * 0.12)
        agilite_mod = 1.0 - min(0.75, ratio * 0.25)
    elif delta < 0:
        ratio = abs(delta) / max(tolerance, 1.0)
        force_mod = 1.0 - min(0.25, ratio * 0.08)
        agilite_mod = 1.0 + min(0.15, ratio * 0.05)

    if abs_delta <= tolerance * 0.4:
        status, status_label, note = 'ideal', 'Zone ideale', "Ton cochon est dans son poids de forme."
    elif delta > tolerance:
        status, status_label, note = 'heavy', 'Trop lourd', "Impact strategique : bulldozer (Force+) mais perd souplesse (Agilite-)."
    elif delta < -tolerance:
        status, status_label, note = 'light', 'Trop leger', "Impact strategique : vif (Agilite+) mais manque d'impact (Force-)."
    else:
        status, status_label, note = 'warning', 'A surveiller', "Le poids reste jouable, ajustement possible."

    return {
        'current_weight': current_weight, 'ideal_weight': ideal_weight,
        'min_weight': round(ideal_weight - tolerance, 1), 'max_weight': round(ideal_weight + tolerance, 1),
        'delta': delta, 'status': status, 'status_label': status_label, 'note': note,
        'race_factor': round(race_factor, 3), 'race_percent': round((race_factor - 1.0) * 100, 1),
        'injury_factor': round(injury_factor, 3), 'score_pct': max(8, min(100, int((race_factor / 1.06) * 100))),
        'force_mod': round(force_mod, 2), 'agilite_mod': round(agilite_mod, 2),
    }

def calculate_pig_power(pig):
    profile = get_weight_profile(pig)
    freshness = get_freshness_bonus(pig)
    effective_force = pig.force * profile['force_mod']
    effective_vitesse = pig.vitesse
    effective_agilite = pig.agilite * profile['agilite_mod']
    if (pig.hunger or 0) < 10:
        effective_force *= 0.7
    effective_moral = pig.moral * freshness['multiplier']
    stats = [effective_vitesse, pig.endurance, effective_agilite, effective_force, pig.intelligence, effective_moral]
    stat_score = sum(math.sqrt(max(0.0, stat) / 100.0) * 100 for stat in stats) / len(stats)
    condition_factor = 0.8 + (((pig.energy + pig.hunger + pig.happiness) / 3.0) / 100.0) * 0.4
    return round(stat_score * condition_factor * profile['race_factor'], 2)

def clamp_pig_weight(weight):
    return round(min(MAX_PIG_WEIGHT_KG, max(MIN_PIG_WEIGHT_KG, weight)), 1)

def calculate_target_weight_kg(source, level=None):
    force = float(getattr(source, 'force', 10.0))
    endurance = float(getattr(source, 'endurance', 10.0))
    agilite = float(getattr(source, 'agilite', 10.0))
    vitesse = float(getattr(source, 'vitesse', 10.0))
    level = max(1, int(level or getattr(source, 'level', 1)))
    target = 108.0 + (force * 0.22) + (endurance * 0.16) - (agilite * 0.10) - (vitesse * 0.05) + ((level - 1) * 0.35)
    return round(min(140.0, max(95.0, target)), 1)

def generate_weight_kg_for_profile(source, level=None):
    ideal = calculate_target_weight_kg(source, level=level)
    return clamp_pig_weight(random.uniform(ideal - 7.0, ideal + 7.0))

def update_pig_state(pig):
    now = datetime.utcnow()
    if not pig.last_updated: pig.last_updated = now; return
    hours = min(24, (now - pig.last_updated).total_seconds() / 3600)
    if hours < 0.01: return
    pig.hunger = max(0, pig.hunger - hours * 2)
    if pig.hunger > 30: pig.energy = min(100, pig.energy + hours * 5)
    else: pig.energy = max(0, pig.energy - hours * 1)
    pig.last_updated = now
    db.session.commit()

def generate_course_segments(length=3000):
    """Genere des segments pour une distance totale de 3000m (correspondant a 5 tours de 600m)."""
    segments = []
    current_dist = 0
    while current_dist < length:
        seg_type = random.choice(PIG_COURSE_SEGMENT_TYPES)
        seg_len = random.randint(150, 400)
        actual_len = min(seg_len, length - current_dist)
        segments.append({'type': seg_type, 'length': actual_len})
        current_dist += actual_len
    return segments

def get_user_active_pigs(user):
    pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    if not pigs:
        if Pig.query.filter_by(user_id=user.id).count() > 0: return []
        origin = random.choice(PIG_ORIGINS)
        pig = Pig(user_id=user.id, name=build_unique_pig_name(f"Cochon de {user.username}"), emoji='🐷', origin_country=origin['country'], origin_flag=origin['flag'], lineage_name=f"Maison {user.username}")
        base_val = getattr(pig, origin['bonus_stat']) or 10.0
        setattr(pig, origin['bonus_stat'], base_val + origin['bonus'])
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig); db.session.commit()
        return [pig]
    return pigs

def get_first_injured_pig(user_id):
    if not user_id: return None
    return Pig.query.filter_by(user_id=user_id, is_alive=True, is_injured=True).order_by(Pig.vet_deadline.asc(), Pig.id.asc()).first()

def check_vet_deadlines():
    now = datetime.utcnow()
    injured_pigs = Pig.query.filter_by(is_injured=True, is_alive=True).all()
    for pig in injured_pigs:
        if pig.vet_deadline and now > pig.vet_deadline: pig.kill(cause='blessure')

def populate_race_participants(race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=True):
    if not race or race.status != 'open': return []
    if not allow_rebuild_if_bets and Bet.query.filter_by(race_id=race.id).count() > 0:
        return Participant.query.filter_by(race_id=race.id).all()
    max_p = 8
    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.is_injured == False, Pig.energy > 20, Pig.hunger > 20).all()
    for p in fit_pigs: update_pig_state(p)
    fit_pigs = [p for p in fit_pigs if not p.is_injured and p.energy > 20 and p.hunger > 20]
    fit_pigs.sort(key=lambda p: calculate_pig_power(p), reverse=True)
    if respect_course_plans:
        plans = CoursePlan.query.filter(CoursePlan.scheduled_at == race.scheduled_at).order_by(CoursePlan.created_at.asc()).all()
        planned_ids = [pl.pig_id for pl in plans]
        planned_order = {pid: i for i, pid in enumerate(planned_ids)}
        fit_pigs.sort(key=lambda p: (0 if p.id in planned_order else 1, planned_order.get(p.id, 999), -calculate_pig_power(p)))
    fit_pigs = fit_pigs[:max_p]
    Participant.query.filter_by(race_id=race.id).delete(synchronize_session=False)
    db.session.flush()
    parts, powers = [], []
    for pig in fit_pigs:
        pow_val = calculate_pig_power(pig); powers.append(pow_val)
        owner = User.query.get(pig.user_id)
        plan = CoursePlan.query.filter_by(pig_id=pig.id, scheduled_at=race.scheduled_at).first()
        participant = Participant(race_id=race.id, name=pig.name, emoji=pig.emoji, pig_id=pig.id, owner_name=owner.username if owner else None, strategy=plan.strategy if plan else 50, odds=0, win_probability=0)
        db.session.add(participant); parts.append(participant)
    npc_c = min(max_p - len(fit_pigs), len(PIGS))
    if npc_c > 0:
        avg_p = sum(powers) / len(powers) if powers else 34.0
        for npc in random.sample(PIGS, npc_c):
            p_val = random.uniform(avg_p * 0.9, avg_p * 1.1); powers.append(p_val)
            participant = Participant(race_id=race.id, name=npc['name'], emoji=npc['emoji'], pig_id=None, owner_name=None, odds=0, win_probability=0)
            db.session.add(participant); parts.append(participant)
    total_p = sum(powers) if powers else 1
    for i, p in enumerate(parts): p.win_probability = powers[i] / total_p
    db.session.flush()
    p_by_id = {p.id: p for p in parts}
    for p in parts:
        prob = p.win_probability or 0.0
        p.odds = max(1.1, math.floor(((1/prob)/0.85)*10)/10) if prob > 0 else 10.0
    if commit: db.session.commit()
    return parts

def run_race_if_needed():
    now = datetime.now()
    due_races = Race.query.filter(Race.status == 'open', Race.scheduled_at <= now).all()
    for race in due_races:
        participants = Participant.query.filter_by(race_id=race.id).all()
        if not participants: continue
        pigs_for_sim = []
        for p in participants:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if pig: pig.strategy = p.strategy; pigs_for_sim.append(pig)
            else:
                p_odds = float(p.odds or 10.0)
                pigs_for_sim.append({'id': p.id, 'name': p.name, 'emoji': p.emoji, 'vitesse': 25 + (1.0/p_odds)*80, 'endurance': 35, 'force': 30, 'agilite': 30, 'intelligence': 30, 'moral': 50, 'strategy': 50})
        
        # Course sur 3000m (5 tours de 600m)
        segments = generate_course_segments(3000)
        manager = CourseManager(pigs_for_sim, segments)
        manager.run()
        race.replay_json = manager.to_json()
        final_pigs = sorted(manager.participants, key=lambda x: (x.finish_time or 9999, -x.distance))
        p_by_id = {p.id: p for p in participants}
        order = [p_by_id[fp.id] for fp in final_pigs if fp.id in p_by_id]
        for i, p in enumerate(order):
            p.finish_position = i + 1
            # Récompense pour les 3 premiers (proprietaires reels)
            reward = RACE_POSITION_REWARDS.get(p.finish_position, 0)
            if p.pig_id and reward > 0:
                pig = Pig.query.get(p.pig_id)
                if pig and pig.user_id:
                    credit_user_balance(
                        pig.user_id, reward,
                        reason_code='race_reward',
                        reason_label=f'Prime de course ({p.finish_position}e place)',
                        details=f'Place {p.finish_position} sur la course #{race.id} pour {p.name}',
                        reference_type='race', reference_id=race.id
                    )
        race.winner_name = order[0].name; race.winner_odds = order[0].odds; race.finished_at = now; race.status = 'finished'
        db.session.commit()
    if due_races: ensure_next_race()

def ensure_next_race():
    race_h, race_m = int(get_config('race_hour', '14')), int(get_config('race_minute', '00'))
    now = datetime.now()
    next_time = now.replace(hour=race_h, minute=race_m, second=0, microsecond=0)
    if now >= next_time: next_time += timedelta(days=1)
    existing = Race.query.filter(Race.scheduled_at == next_time, Race.status.in_(['upcoming', 'open'])).first()
    if existing:
        populate_race_participants(existing); return existing
    race = Race(scheduled_at=next_time, status='open')
    db.session.add(race); db.session.flush()
    populate_race_participants(race); return race

def build_course_schedule(user, pigs, days=30):
    slots = [get_next_race_time() + timedelta(days=i) for i in range(days)]
    races = Race.query.filter(Race.scheduled_at >= slots[0], Race.scheduled_at <= slots[-1], Race.status.in_(['open', 'upcoming'])).all()
    r_by_s = {r.scheduled_at: r for r in races}
    schedule = []
    for s_time in slots:
        r = r_by_s.get(s_time)
        parts = Participant.query.filter_by(race_id=r.id).all() if r else []
        schedule.append({'slot': s_time, 'slot_key': s_time.strftime('%Y-%m-%dT%H:%M:%S'), 'day_name': JOURS_FR[s_time.weekday()], 'theme': get_course_theme(s_time), 'race': r, 'participants': parts, 'is_next': s_time == slots[0]})
    return schedule

def get_next_race_time():
    h, m = int(get_config('race_hour', '14')), int(get_config('race_minute', '00'))
    now = datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=1)

def get_course_theme(slot_time):
    return {'emoji': '🥓', 'name': 'Trot du Jambon', 'tag': 'Classique', 'description': 'Course quotidienne.', 'accent': 'pink', 'focus_stat': 'vitesse', 'reward_multiplier': 1}

def build_unique_pig_name(name, fallback_prefix='Cochon'):
    cand = ' '.join((name or '').split())[:80] or fallback_prefix
    if not Pig.query.filter(func.lower(Pig.name) == cand.lower()).first(): return cand
    s = 2
    while True:
        res = f"{cand} {s}"
        if not Pig.query.filter(func.lower(Pig.name) == res.lower()).first(): return res
        s += 1

def count_pig_weekly_course_commitments(pig_id, anchor_dt, exclude_scheduled_at=None):
    ws = (anchor_dt - timedelta(days=anchor_dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    we = ws + timedelta(days=7)
    c1 = CoursePlan.query.filter(CoursePlan.pig_id == pig_id, CoursePlan.scheduled_at >= ws, CoursePlan.scheduled_at < we).count()
    c2 = db.session.query(func.count(Participant.id)).join(Race).filter(Participant.pig_id == pig_id, Race.scheduled_at >= ws, Race.scheduled_at < we, Race.status.in_(['open', 'finished'])).scalar() or 0
    return c1 + c2

def get_cooldown_remaining(last_at, mins):
    if not last_at: return 0
    return max(0, int(mins * 60 - (datetime.utcnow() - last_at).total_seconds()))

def get_seconds_until(dt):
    if not dt: return 0
    return max(0, int((dt - datetime.utcnow()).total_seconds()))

def get_prix_moyen_groin(): return 42.0
def is_market_open(): return True
def get_next_market_time(): return datetime.now() + timedelta(hours=1)
