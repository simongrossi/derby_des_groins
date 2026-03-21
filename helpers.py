from datetime import datetime
from sqlalchemy import func, or_, update
import random
import math

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
from utils.time_utils import calculate_weekend_truce_hours


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
        'empty_race_mode': 'fill',  # 'fill' or 'cancel'
    }
    for k, v in defaults.items():
        if not GameConfig.query.filter_by(key=k).first():
            db.session.add(GameConfig(key=k, value=v))
    db.session.commit()


# ─── HELPERS COCHON ─────────────────────────────────────────────────────────
 
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

def get_pig_performance_flags(pig):
    weight_profile = get_weight_profile(pig)
    ideal_weight = max(1.0, weight_profile['ideal_weight'])
    deviation_ratio = abs(weight_profile['current_weight'] - ideal_weight) / ideal_weight
    return {
        'hungry_penalty': (pig.hunger or 0) < 10,
        'weight_penalty': deviation_ratio > IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO,
        'weight_status': weight_profile['status'],
    }

def reset_snack_share_limit_if_needed(user, now=None):
    if not user:
        return
    current_time = now or datetime.utcnow()
    if not user.snack_share_reset_at or user.snack_share_reset_at.date() != current_time.date():
        user.snack_shares_today = 0
        user.snack_share_reset_at = current_time

def clamp_pig_weight(weight):
    return round(min(MAX_PIG_WEIGHT_KG, max(MIN_PIG_WEIGHT_KG, weight)), 1)

def get_weight_stat(source, stat_name, default=10.0):
    if isinstance(source, dict):
        value = source.get(stat_name, default)
    else:
        value = getattr(source, stat_name, default)
    return float(default if value is None else value)

def calculate_target_weight_kg(source, level=None):
    force = get_weight_stat(source, 'force')
    endurance = get_weight_stat(source, 'endurance')
    agilite = get_weight_stat(source, 'agilite')
    vitesse = get_weight_stat(source, 'vitesse')
    if level is None:
        level = source.get('level', 1) if isinstance(source, dict) else getattr(source, 'level', 1)
    level = max(1, int(level or 1))

    target = (
        108.0
        + (force * 0.22)
        + (endurance * 0.16)
        - (agilite * 0.10)
        - (vitesse * 0.05)
        + ((level - 1) * 0.35)
    )
    return round(min(140.0, max(95.0, target)), 1)

def generate_weight_kg_for_profile(source, level=None):
    ideal = calculate_target_weight_kg(source, level=level)
    return clamp_pig_weight(random.uniform(ideal - 7.0, ideal + 7.0))

def adjust_pig_weight(pig, delta):
    pig.weight_kg = clamp_pig_weight((pig.weight_kg or DEFAULT_PIG_WEIGHT_KG) + delta)
    return pig.weight_kg

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
        # Trop lourd: +Force, -Agilité
        ratio = delta / max(tolerance, 1.0)
        force_mod = 1.0 + min(0.35, ratio * 0.12)
        agilite_mod = 1.0 - min(0.75, ratio * 0.25)
    elif delta < 0:
        # Trop léger: -Force, +Agilité
        ratio = abs(delta) / max(tolerance, 1.0)
        force_mod = 1.0 - min(0.25, ratio * 0.08)
        agilite_mod = 1.0 + min(0.15, ratio * 0.05)

    if abs_delta <= tolerance * 0.4:
        status = 'ideal'
        status_label = 'Zone ideale'
        note = "Ton cochon est dans son poids de forme. Il transforme mieux ses stats en vitesse utile."
    elif delta > tolerance:
        status = 'heavy'
        status_label = 'Trop lourd'
        note = "Impact strategique : Il devient un bulldozer (Force+) mais perd toute souplesse (Agilite-)."
    elif delta < -tolerance:
        status = 'light'
        status_label = 'Trop leger'
        note = "Impact strategique : Il est tres vif (Agilite+) mais manque d'impact face aux autres (Force-)."
    else:
        status = 'warning'
        status_label = 'A surveiller'
        note = "Le poids reste jouable, mais un petit ajustement peut encore aider en course."

    return {
        'current_weight': current_weight,
        'ideal_weight': ideal_weight,
        'min_weight': round(ideal_weight - tolerance, 1),
        'max_weight': round(ideal_weight + tolerance, 1),
        'delta': delta,
        'status': status,
        'status_label': status_label,
        'note': note,
        'race_factor': round(race_factor, 3),
        'race_percent': round((race_factor - 1.0) * 100, 1),
        'injury_factor': round(injury_factor, 3),
        'score_pct': max(8, min(100, int((race_factor / 1.06) * 100))),
        'force_mod': round(force_mod, 2),
        'agilite_mod': round(agilite_mod, 2),
    }

def calculate_pig_power(pig):
    profile = get_weight_profile(pig)
    freshness = get_freshness_bonus(pig)
    effective_force = pig.force * profile['force_mod']
    effective_endurance = pig.endurance
    effective_vitesse = pig.vitesse
    effective_agilite = pig.agilite * profile['agilite_mod']

    if (pig.hunger or 0) < 10:
        effective_force *= 0.7
        effective_endurance *= 0.7

    ideal_weight = max(1.0, profile['ideal_weight'])
    deviation_ratio = abs(profile['current_weight'] - ideal_weight) / ideal_weight
    if deviation_ratio > IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO:
        excess_ratio = deviation_ratio - IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO
        penalty = min(MAX_WEIGHT_PERFORMANCE_MALUS, excess_ratio / IDEAL_WEIGHT_MALUS_THRESHOLD_RATIO * 0.2)
        modifier = 1.0 - penalty
        effective_vitesse *= modifier
        effective_agilite *= modifier

    effective_moral = pig.moral * freshness['multiplier']

    stats = [
        effective_vitesse,
        effective_endurance,
        effective_agilite,
        effective_force,
        pig.intelligence,
        effective_moral,
    ]
    stat_score = sum(math.sqrt(max(0.0, stat) / 100.0) * 100 for stat in stats) / len(stats)
    condition_factor = 0.8 + (((pig.energy + pig.hunger + pig.happiness) / 3.0) / 100.0) * 0.4
    weight_factor = profile['race_factor']
    return round(stat_score * condition_factor * weight_factor, 2)

def xp_for_level(level):
    return int(100 * (level ** 1.5))

def check_level_up(pig):
    while pig.xp >= xp_for_level(pig.level + 1):
        pig.level += 1
        pig.happiness = min(100, pig.happiness + 10)

def update_pig_state(pig):
    now = datetime.utcnow()
    if not pig.last_updated:
        pig.last_updated = now
        return
    elapsed_hours = (now - pig.last_updated).total_seconds() / 3600
    if elapsed_hours < 0.01:
        return
    truce_hours = calculate_weekend_truce_hours(pig.last_updated, now)
    hours = max(0.0, elapsed_hours - truce_hours)
    hours = min(hours, 24)
    if hours < 0.01:
        pig.last_updated = now
        db.session.commit()
        return
    pig.hunger = max(0, pig.hunger - hours * 2)
    if pig.hunger > 30:
        pig.energy = min(100, pig.energy + hours * 5)
    else:
        pig.energy = max(0, pig.energy - hours * 1)
    if pig.hunger < 15:
        pig.happiness = max(0, pig.happiness - hours * 3)
    elif pig.hunger < 30:
        pig.happiness = max(0, pig.happiness - hours * 1)
    elif pig.happiness < 60:
        pig.happiness = min(60, pig.happiness + hours * 0.3)
    current_weight = pig.weight_kg or DEFAULT_PIG_WEIGHT_KG
    if pig.hunger < 25:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.25)
    elif pig.hunger > 75 and pig.energy < 45:
        pig.weight_kg = clamp_pig_weight(current_weight + hours * 0.18)
    elif pig.energy > 80 and pig.hunger < 60:
        pig.weight_kg = clamp_pig_weight(current_weight - hours * 0.08)
    pig.last_updated = now
    db.session.commit()

def get_cooldown_remaining(last_action, minutes):
    if not last_action:
        return 0
    elapsed = (datetime.utcnow() - last_action).total_seconds()
    return max(0, int(minutes * 60 - elapsed))

def format_duration_short(total_seconds):
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    if minutes and seconds:
        return f"{minutes}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"

def get_seconds_until(deadline):
    if not deadline:
        return 0
    return max(0, int((deadline - datetime.utcnow()).total_seconds()))

def get_active_listing_count(user):
    return Auction.query.filter_by(seller_id=user.id, status='active').count()

def get_pig_slot_count(user):
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    return active_pigs + get_active_listing_count(user)

def get_max_pig_slots(user=None):
    return MAX_PIG_SLOTS

def get_adoption_cost(user):
    slot_count = get_pig_slot_count(user)
    if slot_count >= get_max_pig_slots(user):
        return None
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    if active_count == 0:
        return REPLACEMENT_PIG_COST
    return SECOND_PIG_COST + max(0, active_count - 1) * 15.0

def get_feeding_cost_multiplier(user):
    active_count = Pig.query.filter_by(user_id=user.id, is_alive=True).count()
    if active_count <= 1:
        return 1.0
    return round(1.0 + ((active_count - 1) * FEEDING_PRESSURE_PER_PIG), 2)

def get_lineage_label(pig):
    return pig.lineage_name or pig.name

def get_pig_heritage_value(pig):
    wins = pig.races_won or 0
    level = pig.level or 1
    rarity_bonus = {'commun': 0.0, 'rare': 0.5, 'epique': 1.0, 'legendaire': 2.0}.get(pig.rarity or 'commun', 0.0)
    return round((wins * 0.6) + max(0, level - 1) * 0.08 + (pig.lineage_boost or 0.0) + rarity_bonus, 2)

def can_retire_into_heritage(pig):
    return bool(pig and pig.is_alive and not pig.retired_into_heritage and ((pig.races_won or 0) >= RETIREMENT_HERITAGE_MIN_WINS or (pig.rarity == 'legendaire')))

def retire_pig_into_heritage(user, pig):
    if not can_retire_into_heritage(pig):
        return 0.0
    bonus = max(1.0, round(get_pig_heritage_value(pig) * 0.35, 2))
    user.barn_heritage_bonus = round((user.barn_heritage_bonus or 0.0) + bonus, 2)
    pig.retired_into_heritage = True
    pig.lineage_boost = round((pig.lineage_boost or 0.0) + bonus, 2)
    lineage_name = get_lineage_label(pig)
    related_pigs = Pig.query.filter(
        Pig.user_id == user.id,
        Pig.is_alive == True,
        Pig.id != pig.id,
        Pig.lineage_name == lineage_name,
    ).all()
    for descendant in related_pigs:
        descendant.lineage_boost = round((descendant.lineage_boost or 0.0) + bonus, 2)
        descendant.moral = min(100, (descendant.moral or 0.0) + min(4.0, bonus * 0.4))
    pig.retire()
    pig.death_cause = 'retraite_honoree'
    pig.epitaph = f"{pig.name} entre au haras des legends. Sa lignee inspire toute la porcherie (+{bonus:.1f} heritage)."
    db.session.commit()
    return bonus

def create_offspring(user, parent_a, parent_b, name=None):
    lineage_name = parent_a.lineage_name or parent_b.lineage_name or f"Maison {user.username}"
    barn_bonus = user.barn_heritage_bonus or 0.0
    child = Pig(
        user_id=user.id,
        name=build_unique_pig_name(name or f"Porcelet {lineage_name}", fallback_prefix='Porcelet'),
        emoji=random.choice(PIG_EMOJIS),
        rarity=parent_a.rarity if parent_a.rarity == parent_b.rarity else random.choice([parent_a.rarity, parent_b.rarity, 'commun']),
        origin_country=random.choice([parent_a.origin_country, parent_b.origin_country]),
        origin_flag=random.choice([parent_a.origin_flag, parent_b.origin_flag]),
        lineage_name=lineage_name,
        generation=max(parent_a.generation or 1, parent_b.generation or 1) + 1,
        sire_id=parent_a.id,
        dam_id=parent_b.id,
        lineage_boost=round(((parent_a.lineage_boost or 0.0) + (parent_b.lineage_boost or 0.0)) * 0.35 + (barn_bonus * 0.25), 2),
    )
    for stat in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']:
        base = (getattr(parent_a, stat, 10.0) + getattr(parent_b, stat, 10.0)) / 2
        inherited = base * 0.82 + random.uniform(-2.5, 2.5) + child.lineage_boost
        setattr(child, stat, round(min(100, max(8, inherited)), 1))
    child.energy = 78
    child.hunger = 70
    child.happiness = min(100, round(72 + (barn_bonus * 0.4), 1))
    child.weight_kg = generate_weight_kg_for_profile(child, level=child.level)
    return child

def get_market_unlock_progress(user):
    total_races = sum(p.races_entered for p in Pig.query.filter_by(user_id=user.id).all())
    account_age_hours = ((datetime.utcnow() - user.created_at).total_seconds() / 3600) if user.created_at else 0
    unlocked = account_age_hours >= 24 or total_races >= 3
    return unlocked, total_races, account_age_hours

def get_market_lock_reason(user):
    unlocked, total_races, account_age_hours = get_market_unlock_progress(user)
    if unlocked:
        return None
    remaining_races = max(0, 3 - total_races)
    remaining_hours = max(0, int(math.ceil(24 - account_age_hours)))
    return f"Le marché se débloque après 3 courses disputées ou 24h d'ancienneté. Il te reste {remaining_races} course(s) ou environ {remaining_hours}h."

def apply_origin_bonus(pig, origin):
    base_value = getattr(pig, origin['bonus_stat']) or 10.0
    setattr(pig, origin['bonus_stat'], base_value + origin['bonus'])
 
def normalize_pig_name(name):
    return ' '.join((name or '').split()).casefold()


def is_pig_name_taken(name, exclude_pig_id=None):
    normalized = normalize_pig_name(name)
    if not normalized:
        return False
    pigs = Pig.query
    if exclude_pig_id is not None:
        pigs = pigs.filter(Pig.id != exclude_pig_id)
    return any(normalize_pig_name(pig.name) == normalized for pig in pigs.all())


def build_unique_pig_name(base_name, fallback_prefix='Cochon'):
    candidate = ' '.join((base_name or '').split())[:80]
    if not candidate:
        candidate = fallback_prefix
    if not is_pig_name_taken(candidate):
        return candidate
    suffix = 2
    while True:
        suffix_label = f' {suffix}'
        trimmed = candidate[:max(1, 80 - len(suffix_label))].rstrip()
        unique_name = f'{trimmed}{suffix_label}'
        if not is_pig_name_taken(unique_name):
            return unique_name
        suffix += 1


def create_preloaded_admin_pigs(admin_user):
    if not admin_user:
        return 0
    created = 0
    for index, pig_name in enumerate(PRELOADED_PIG_NAMES):
        if is_pig_name_taken(pig_name):
            continue
        origin = PIG_ORIGINS[index % len(PIG_ORIGINS)]
        pig = Pig(
            user_id=admin_user.id,
            name=pig_name,
            emoji=PIG_EMOJIS[index % len(PIG_EMOJIS)],
            origin_country=origin['country'],
            origin_flag=origin['flag'],
            lineage_name='Maison Admin',
        )
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        created += 1
    return created

def supports_row_level_locking():
    try:
        return db.engine.dialect.name != 'sqlite'
    except Exception:
        return False

def apply_row_lock(query):
    if supports_row_level_locking():
        return query.with_for_update()
    return query


# ─── HELPERS BALANCE ────────────────────────────────────────────────────────

def record_balance_transaction(user_id, amount, balance_before, balance_after,
                               reason_code='adjustment', reason_label='Mouvement BitGroins',
                               details=None, reference_type=None, reference_id=None):
    tx = BalanceTransaction(
        user_id=user_id,
        amount=round(amount, 2),
        balance_before=None if balance_before is None else round(balance_before, 2),
        balance_after=None if balance_after is None else round(balance_after, 2),
        reason_code=reason_code or 'adjustment',
        reason_label=reason_label or 'Mouvement BitGroins',
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(tx)
    return tx

def adjust_user_balance(user_id, delta, minimum_balance=None,
                        reason_code='adjustment', reason_label='Mouvement BitGroins',
                        details=None, reference_type=None, reference_id=None):
    delta = round(float(delta or 0.0), 2)
    if delta == 0:
        return True

    stmt = update(User).where(User.id == user_id)
    if minimum_balance is not None:
        stmt = stmt.where(User.balance >= minimum_balance)
    stmt = stmt.values(balance=func.round(User.balance + delta, 2)).returning(User.balance)

    row = db.session.execute(stmt).first()
    if not row:
        db.session.rollback()
        return False
    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - delta, 2)
    record_balance_transaction(
        user_id=user_id,
        amount=delta,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return True

def debit_user_balance(user_id, amount, reason_code='debit', reason_label='Débit BitGroins',
                       details=None, reference_type=None, reference_id=None):
    if amount <= 0:
        return False
    return adjust_user_balance(
        user_id,
        -amount,
        minimum_balance=amount,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )

def credit_user_balance(user_id, amount, reason_code='credit', reason_label='Crédit BitGroins',
                        details=None, reference_type=None, reference_id=None):
    if amount <= 0:
        return True
    return adjust_user_balance(
        user_id,
        amount,
        reason_code=reason_code,
        reason_label=reason_label,
        details=details,
        reference_type=reference_type,
        reference_id=reference_id,
    )

def reserve_pig_challenge_slot(pig_id, wager):
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager <= 0)
        .values(challenge_mort_wager=wager)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return False
    return True

def release_pig_challenge_slot(pig_id):
    pig = Pig.query.get(pig_id)
    if not pig or pig.challenge_mort_wager <= 0:
        return 0.0

    current_wager = round(pig.challenge_mort_wager or 0.0, 2)
    refund = round(current_wager * 0.5, 2)
    result = db.session.execute(
        update(Pig)
        .where(Pig.id == pig_id, Pig.is_alive == True, Pig.challenge_mort_wager == current_wager)
        .values(challenge_mort_wager=0.0)
    )
    if result.rowcount != 1:
        db.session.rollback()
        return 0.0
    return refund

def maybe_grant_emergency_relief(user):
    if not user:
        return 0.0

    now = datetime.utcnow()
    cooldown_limit = now - timedelta(hours=EMERGENCY_RELIEF_HOURS)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.balance < EMERGENCY_RELIEF_THRESHOLD,
            or_(User.last_relief_at.is_(None), User.last_relief_at <= cooldown_limit),
        )
        .values(
            balance=func.round(User.balance + EMERGENCY_RELIEF_AMOUNT, 2),
            last_relief_at=now,
        )
        .returning(User.balance)
    )
    row = result.first()
    if not row:
        db.session.rollback()
        return 0.0

    balance_after = round(float(row[0] or 0.0), 2)
    balance_before = round(balance_after - EMERGENCY_RELIEF_AMOUNT, 2)
    record_balance_transaction(
        user_id=user.id,
        amount=EMERGENCY_RELIEF_AMOUNT,
        balance_before=balance_before,
        balance_after=balance_after,
        reason_code='emergency_relief',
        reason_label="Prime d'urgence",
        details="Filet de sécurité automatique pour éviter un blocage à 0 🪙.",
        reference_type='system',
        reference_id=user.id,
    )

    db.session.commit()
    return EMERGENCY_RELIEF_AMOUNT


# ─── HELPERS BETTING ────────────────────────────────────────────────────────

def normalize_bet_type(bet_type):
    if bet_type in BET_TYPES:
        return bet_type
    return 'win'

def serialize_selection_ids(selection_ids):
    return ",".join(str(int(selection_id)) for selection_id in selection_ids)

def parse_selection_ids(raw_selection):
    if not raw_selection:
        return []
    selection_ids = []
    for raw_part in str(raw_selection).split(','):
        part = raw_part.strip()
        if not part:
            continue
        if not part.isdigit():
            return []
        selection_ids.append(int(part))
    return selection_ids

def format_bet_label(participants):
    return " -> ".join(participant.name for participant in participants)

def calculate_ordered_finish_probability(participants_by_id, ordered_ids):
    remaining_probabilities = {
        participant_id: max(participant.win_probability or 0.0, 0.0)
        for participant_id, participant in participants_by_id.items()
    }
    remaining_total = sum(remaining_probabilities.values())
    if remaining_total <= 0:
        return 0.0

    combined_probability = 1.0
    for participant_id in ordered_ids:
        current_probability = remaining_probabilities.get(participant_id)
        if current_probability is None or current_probability <= 0 or remaining_total <= 0:
            return 0.0
        combined_probability *= current_probability / remaining_total
        remaining_total -= current_probability
        del remaining_probabilities[participant_id]

    return combined_probability

def calculate_bet_odds(participants_by_id, ordered_ids, bet_type):
    bet_config = BET_TYPES[normalize_bet_type(bet_type)]
    probability = calculate_ordered_finish_probability(participants_by_id, ordered_ids)
    if probability <= 0:
        return 0.0
    raw_odds = (1 / probability) / bet_config['house_edge']
    return max(1.1, math.floor(raw_odds * 10) / 10)

def build_weighted_finish_order(participants):
    remaining = list(participants)
    finish_order = []
    while remaining:
        weights = [max(participant.win_probability or 0.0, 0.000001) for participant in remaining]
        chosen = random.choices(remaining, weights=weights, k=1)[0]
        finish_order.append(chosen)
        remaining.remove(chosen)
    return finish_order

def generate_course_segments(length=1200):
    segments = []
    current_dist = 0
    while current_dist < length:
        seg_type = random.choice(PIG_COURSE_SEGMENT_TYPES)
        seg_len = random.randint(150, 400)
        actual_len = min(seg_len, length - current_dist)
        segments.append({'type': seg_type, 'length': actual_len})
        current_dist += actual_len
    return segments

def get_bet_selection_ids(bet, participants_by_id):
    selection_ids = parse_selection_ids(getattr(bet, 'selection_order', None))
    if selection_ids:
        return selection_ids
    matching_participant = next((participant for participant in participants_by_id.values() if participant.name == bet.pig_name), None)
    if matching_participant:
        return [matching_participant.id]
    return []

def get_week_window(anchor_dt):
    week_start = (anchor_dt - timedelta(days=anchor_dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return week_start, week_start + timedelta(days=7)

def get_user_weekly_bet_count(user, anchor_dt=None):
    if not user:
        return 0
    anchor_dt = anchor_dt or datetime.now()
    week_start, week_end = get_week_window(anchor_dt)
    return Bet.query.filter(
        Bet.user_id == user.id,
        Bet.placed_at >= week_start,
        Bet.placed_at < week_end,
    ).count()


# ─── HELPERS COURSE PLANNING ───────────────────────────────────────────────

def count_pig_weekly_course_commitments(pig_id, anchor_dt, exclude_scheduled_at=None):
    week_start, week_end = get_week_window(anchor_dt)
    planned_query = CoursePlan.query.filter(
        CoursePlan.pig_id == pig_id,
        CoursePlan.scheduled_at >= week_start,
        CoursePlan.scheduled_at < week_end,
    )
    if exclude_scheduled_at is not None:
        planned_query = planned_query.filter(CoursePlan.scheduled_at != exclude_scheduled_at)
    planned_count = planned_query.count()

    actual_query = (
        db.session.query(func.count(Participant.id))
        .join(Race, Participant.race_id == Race.id)
        .filter(
            Participant.pig_id == pig_id,
            Race.scheduled_at >= week_start,
            Race.scheduled_at < week_end,
            Race.status.in_(['open', 'finished']),
        )
    )
    if exclude_scheduled_at is not None:
        actual_query = actual_query.filter(Race.scheduled_at != exclude_scheduled_at)
    actual_count = actual_query.scalar() or 0
    return int(planned_count + actual_count)

def get_course_theme(slot_time):
    weekday = slot_time.weekday()
    if weekday == 0:
        return {
            'emoji': '🌧️',
            'name': 'Lundi de la Pataugeoire',
            'tag': 'Boue + Force',
            'description': "Boue lourde, appuis glissants et contacts rugueux : les cochons puissants y gagnent un vrai avantage.",
            'accent': 'amber',
            'focus_stat': 'force',
            'focus_label': 'Force favorisee',
            'reward_multiplier': 1,
            'event_label': 'Theme quotidien',
            'planning_hint': 'Ideal pour tes profils costauds qui aiment pousser dans la gadoue.',
        }
    if weekday == 2:
        return {
            'emoji': '🏃',
            'name': 'Mercredi Marathon',
            'tag': 'Longue distance',
            'description': "Le rail s'etire, le tempo use les reserves et seuls les cochons endurants gardent leur allure jusqu'au bout.",
            'accent': 'cyan',
            'focus_stat': 'endurance',
            'focus_label': 'Endurance favorisee',
            'reward_multiplier': 1,
            'event_label': 'Theme quotidien',
            'planning_hint': 'A reserver a tes moteurs les plus constants pour securiser la semaine.',
        }
    if weekday == 4:
        return {
            'emoji': '🏆',
            'name': 'Grand Prix du Vendredi',
            'tag': 'Recompenses x3',
            'description': "Le grand rendez-vous asynchrone de la semaine : plus de prestige, plus de pression et des primes d'elevage triplees.",
            'accent': 'red',
            'focus_stat': 'moral',
            'focus_label': 'Prestige maximal',
            'reward_multiplier': 3,
            'event_label': 'Evenement majeur',
            'planning_hint': 'Garde au moins un top cochon disponible pour ce pic de rentabilite.',
        }
    if weekday in (1, 3):
        return {
            'emoji': '🥓',
            'name': 'Trot du Jambon',
            'tag': 'Classique equilibre',
            'description': "Le format le plus fiable pour remplir ton quota sans surprise majeure.",
            'accent': 'pink',
            'focus_stat': 'polyvalence',
            'focus_label': 'Stats equilibrees',
            'reward_multiplier': 1,
            'event_label': 'Routine rentable',
            'planning_hint': 'Parfait pour caser un cochon regulier entre deux gros rendez-vous.',
        }
    return {
        'emoji': '🌿',
        'name': 'Derby des Bauges Calmes',
        'tag': 'Repos ou event',
        'description': "Un creneau souple pour finir ton quota, tester des doublures ou garder du jus pour vendredi.",
        'accent': 'emerald',
        'focus_stat': 'rotation',
        "focus_label": "Gestion d'effectif",
        'reward_multiplier': 1,
        'event_label': 'Souplesse',
        'planning_hint': 'Utilise-le pour lisser la fatigue et terminer ta semaine en 5 minutes.',
    }

def get_upcoming_course_slots(days=30):
    first_slot = get_next_race_time()
    return [first_slot + timedelta(days=offset) for offset in range(days)]

def get_race_ready_pigs():
    fit_pigs = Pig.query.filter(
        Pig.is_alive == True,
        Pig.is_injured == False,
        Pig.energy > 20,
        Pig.hunger > 20,
    ).all()
    for pig in fit_pigs:
        update_pig_state(pig)
    fit_pigs = [pig for pig in fit_pigs if not pig.is_injured and pig.energy > 20 and pig.hunger > 20]
    fit_pigs.sort(key=lambda pig: calculate_pig_power(pig), reverse=True)
    return fit_pigs

def get_pig_last_race_datetime(pig):
    if not pig:
        return None
    return (
        db.session.query(func.max(Race.scheduled_at))
        .join(Participant, Participant.race_id == Race.id)
        .filter(Participant.pig_id == pig.id, Race.status == 'finished')
        .scalar()
    )

def get_pig_dashboard_status(pig):
    if not pig:
        return None
    last_race_at = get_pig_last_race_datetime(pig)
    reference_dt = last_race_at or pig.created_at or datetime.utcnow()
    rest_days = max(0, (datetime.now() - reference_dt).days)
    fatigue_pct = max(0, min(100, int(round(100 - (pig.energy or 0)))))
    health_base = ((pig.energy or 0) * 0.4) + ((pig.hunger or 0) * 0.25) + ((pig.happiness or 0) * 0.35)
    if pig.is_injured:
        health_base -= 35
    health_pct = max(0, min(100, int(round(health_base))))

    if rest_days >= 5:
        rest_label = 'Frais comme un Porcelet'
        rest_note = "Long repos accumule. Excellent signal pour un retour qui claque."
    elif rest_days >= 2:
        rest_label = 'Repos utile'
        rest_note = "Le cochon recharge tranquillement ses batteries avant sa prochaine sortie."
    else:
        rest_label = 'Rythme soutenu'
        rest_note = "Mieux vaut surveiller les enchainements de courses et la fatigue."

    return {
        'health_pct': health_pct,
        'fatigue_pct': fatigue_pct,
        'rest_days': rest_days,
        'last_race_at': last_race_at,
        'rest_label': rest_label,
        'rest_note': rest_note,
    }

def get_planned_pig_ids_for_slot(scheduled_at):
    plans = (
        CoursePlan.query
        .filter(CoursePlan.scheduled_at == scheduled_at)
        .order_by(CoursePlan.created_at.asc(), CoursePlan.id.asc())
        .all()
    )
    return [plan.pig_id for plan in plans]

def populate_race_participants(race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=True):
    if not race or race.status != 'open':
        return []

    if not allow_rebuild_if_bets and Bet.query.filter_by(race_id=race.id).count() > 0:
        return Participant.query.filter_by(race_id=race.id).all()

    max_participants = 8
    fit_pigs = get_race_ready_pigs()

    if respect_course_plans:
        planned_ids = get_planned_pig_ids_for_slot(race.scheduled_at)
        if planned_ids:
            planned_order = {pig_id: index for index, pig_id in enumerate(planned_ids)}
            fit_pigs.sort(
                key=lambda pig: (
                    0 if pig.id in planned_order else 1,
                    planned_order.get(pig.id, 999),
                    -calculate_pig_power(pig),
                )
            )

    fit_pigs = fit_pigs[:max_participants]
    Participant.query.filter_by(race_id=race.id).delete(synchronize_session=False)
    db.session.flush()

    participants_list = []
    all_powers = []
    player_powers = []

    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        player_powers.append(power)
        all_powers.append(power)
        owner = User.query.get(pig.user_id)
        plan = CoursePlan.query.filter_by(pig_id=pig.id, scheduled_at=race.scheduled_at).first()
        strategy = plan.strategy if plan else 50
        participant = Participant(
            race_id=race.id,
            name=pig.name,
            emoji=pig.emoji,
            pig_id=pig.id,
            owner_name=owner.username if owner else None,
            strategy=strategy,
            odds=0,
            win_probability=0,
        )
        db.session.add(participant)
        participants_list.append(participant)

    player_names = {pig.name for pig in fit_pigs}
    available_npcs = [npc for npc in PIGS if npc['name'] not in player_names]
    npc_count = min(max_participants - len(fit_pigs), len(available_npcs))
    if npc_count > 0:
        avg_player_power = sum(player_powers) / len(player_powers) if player_powers else 34.0
        npc_min_power = max(22.0, avg_player_power * 0.9)
        npc_max_power = max(npc_min_power + 2.0, avg_player_power * 1.1)
        for npc in random.sample(available_npcs, npc_count):
            npc_power = random.uniform(npc_min_power, npc_max_power)
            all_powers.append(npc_power)
            participant = Participant(
                race_id=race.id,
                name=npc['name'],
                emoji=npc['emoji'],
                pig_id=None,
                owner_name=None,
                odds=0,
                win_probability=0,
            )
            db.session.add(participant)
            participants_list.append(participant)

    total_power = sum(all_powers) if all_powers else 1
    for index, participant in enumerate(participants_list):
        participant.win_probability = all_powers[index] / total_power
    db.session.flush()
    participants_by_id = {participant.id: participant for participant in participants_list}
    for participant in participants_list:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')

    if commit:
        db.session.commit()
    return participants_list

def build_course_schedule(user, pigs, days=30):
    now = datetime.now()
    slots = get_upcoming_course_slots(days)
    if not slots:
        return []

    slot_start = slots[0]
    slot_end = slots[-1] + timedelta(seconds=1)

    races = (
        Race.query
        .filter(Race.scheduled_at >= slot_start, Race.scheduled_at < slot_end, Race.status.in_(['open', 'upcoming']))
        .order_by(Race.scheduled_at.asc())
        .all()
    )
    race_by_slot = {race.scheduled_at: race for race in races}

    participants = []
    if races:
        race_ids = [race.id for race in races]
        participants = Participant.query.filter(Participant.race_id.in_(race_ids)).all()
    participants_by_race = {}
    for participant in participants:
        participants_by_race.setdefault(participant.race_id, []).append(participant)

    plans = (
        CoursePlan.query
        .filter(CoursePlan.scheduled_at >= slot_start, CoursePlan.scheduled_at < slot_end)
        .order_by(CoursePlan.scheduled_at.asc(), CoursePlan.created_at.asc(), CoursePlan.id.asc())
        .all()
    )
    plans_by_slot = {}
    for plan in plans:
        plans_by_slot.setdefault(plan.scheduled_at, []).append(plan)

    schedule = []
    for slot_time in slots:
        race = race_by_slot.get(slot_time)
        slot_participants = participants_by_race.get(race.id, []) if race else []
        slot_participants.sort(key=lambda participant: (participant.odds or 999, participant.name))
        slot_plan_rows = plans_by_slot.get(slot_time, [])
        slot_user_plans = [plan for plan in slot_plan_rows if plan.user_id == user.id]
        slot_user_plan_by_pig = {plan.pig_id: plan for plan in slot_user_plans}
        slot_actual_pig_ids = {participant.pig_id for participant in slot_participants if participant.pig_id}
        slot_locked = (slot_time - now).total_seconds() < 30
        if race and Bet.query.filter_by(race_id=race.id).count() > 0:
            slot_locked = True

        pig_options = []
        for pig in pigs:
            is_actual_participant = pig.id in slot_actual_pig_ids
            is_planned = pig.id in slot_user_plan_by_pig
            
            # Find current strategy if already participant
            current_strategy = 50
            if is_actual_participant:
                part = next((p for p in slot_participants if p.pig_id == pig.id), None)
                if part:
                    current_strategy = part.strategy
            elif is_planned:
                current_strategy = slot_user_plan_by_pig[pig.id].strategy

            exclude_slot = slot_time if (is_actual_participant or is_planned) else None
            weekly_commitments = count_pig_weekly_course_commitments(pig.id, slot_time, exclude_scheduled_at=exclude_slot)
            projected_commitments = weekly_commitments + (0 if (is_actual_participant or is_planned) else 1)
            quota_reached = weekly_commitments >= WEEKLY_RACE_QUOTA and not (is_actual_participant or is_planned)
            quota_remaining = max(0, WEEKLY_RACE_QUOTA - weekly_commitments)
            projected_remaining = max(0, WEEKLY_RACE_QUOTA - projected_commitments)

            can_toggle = True
            disabled_reason = None
            if slot_locked:
                can_toggle = False
                disabled_reason = "Course verrouillee"
            elif race and race.status == 'open' and (pig.is_injured or pig.energy <= 20 or pig.hunger <= 20):
                can_toggle = False
                disabled_reason = "Trop faible pour la course ouverte"
            elif quota_reached:
                can_toggle = False
                disabled_reason = "Quota hebdo atteint"

            pig_options.append({
                'pig': pig,
                'is_planned': is_planned,
                'is_actual_participant': is_actual_participant,
                'current_strategy': current_strategy,
                'can_toggle': can_toggle,
                'disabled_reason': disabled_reason,
                'weekly_commitments': projected_commitments,
                'quota_remaining': quota_remaining,
                'projected_remaining': projected_remaining,
            })

        user_weekly_plans = len(slot_user_plans)
        user_weekly_remaining = {
            pig.id: max(0, WEEKLY_RACE_QUOTA - count_pig_weekly_course_commitments(pig.id, slot_time))
            for pig in pigs
        }

        schedule.append({
            'slot': slot_time,
            'slot_key': slot_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'day_name': JOURS_FR[slot_time.weekday()],
            'theme': get_course_theme(slot_time),
            'race': race,
            'participants': slot_participants,
            'planned_count': len(slot_plan_rows),
            'user_plans': slot_user_plans,
            'user_plan_names': [plan.pig.name for plan in slot_user_plans if plan.pig],
            'is_next': slot_time == slots[0],
            'is_locked': slot_locked,
            'pig_options': pig_options,
            'user_weekly_plan_count': user_weekly_plans,
            'user_weekly_remaining': user_weekly_remaining,
        })

    return schedule

def refresh_race_betting_lines(race):
    if not race or race.status != 'open':
        return
    if Bet.query.filter_by(race_id=race.id).count() > 0:
        return
    participants = Participant.query.filter_by(race_id=race.id).all()
    if not participants:
        return
    total_prob = sum(p.win_probability for p in participants) or 1.0
    participants_by_id = {participant.id: participant for participant in participants}
    for participant in participants:
        participant.win_probability = participant.win_probability / total_prob
    for participant in participants:
        participant.odds = calculate_bet_odds(participants_by_id, [participant.id], 'win')
    db.session.commit()

def get_user_active_pigs(user):
    pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    if not pigs:
        if Pig.query.filter_by(user_id=user.id).count() > 0:
            return []
        origin = random.choice(PIG_ORIGINS)
        origin_country = origin['country']
        origin_flag = origin['flag']
        pig = Pig(
            user_id=user.id,
            name=build_unique_pig_name(f"Cochon de {user.username}", fallback_prefix='Cochon'),
            emoji='🐷',
            origin_country=origin_country,
            origin_flag=origin_flag,
            lineage_name=f"Maison {user.username}",
        )
        apply_origin_bonus(pig, origin)
        pig.weight_kg = generate_weight_kg_for_profile(pig)
        db.session.add(pig)
        db.session.commit()
        return [pig]
    return pigs

def get_first_injured_pig(user_id):
    if not user_id:
        return None
    return Pig.query.filter_by(user_id=user_id, is_alive=True, is_injured=True).order_by(Pig.vet_deadline.asc(), Pig.id.asc()).first()

def check_vet_deadlines():
    now = datetime.utcnow()
    injured_pigs = Pig.query.filter_by(is_injured=True, is_alive=True).all()
    for pig in injured_pigs:
        if pig.vet_deadline and now > pig.vet_deadline:
            pig.kill(cause='blessure')

def send_to_abattoir(pig, cause='abattoir', commit=True):
    charcuterie = random.choice(CHARCUTERIE)
    epitaph_template = random.choice(EPITAPHS)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = cause
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = epitaph_template.format(name=pig.name, wins=pig.races_won)
    pig.challenge_mort_wager = 0
    if commit:
        db.session.commit()

def retire_pig_old_age(pig, commit=True):
    charcuterie = random.choice(CHARCUTERIE_PREMIUM)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = 'vieillesse'
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = f"{pig.name} a pris sa retraite après {pig.races_entered} courses glorieuses. Un cochon bien vieilli fait le meilleur jambon."
    pig.challenge_mort_wager = 0
    db.session.commit()

def get_dead_pigs_abattoir():
    return Pig.query.filter_by(is_alive=False).order_by(Pig.death_date.desc()).all()

def get_legendary_pigs():
    return Pig.query.filter(Pig.is_alive == False, Pig.races_won >= 3).order_by(Pig.races_won.desc()).all()


# ─── HELPERS BITGROIN ───────────────────────────────────────────────────────

def get_prix_moyen_groin():
    recent_sales = Auction.query.filter_by(status='sold') \
        .order_by(Auction.ends_at.desc()).limit(10).all()
    if recent_sales:
        return round(sum(a.current_bid for a in recent_sales) / len(recent_sales), 2)
    active = Auction.query.filter_by(status='active').all()
    if active:
        return round(sum(a.starting_price for a in active) / len(active), 2)
    return 42.0


# ─── HELPERS MARCHÉ ─────────────────────────────────────────────────────────

def get_next_market_time():
    market_day = int(get_config('market_day', '4'))
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))

    now = datetime.now()
    days_ahead = market_day - now.weekday()
    if days_ahead < 0 or (days_ahead == 0 and now.hour * 60 + now.minute >= market_hour * 60 + market_minute + int(get_config('market_duration', '120'))):
        days_ahead += 7
    next_market = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_market

def is_market_open():
    market_day = int(get_config('market_day', '4'))
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))
    duration = int(get_config('market_duration', '120'))

    now = datetime.now()
    if now.weekday() != market_day:
        return False
    market_start = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0)
    market_end = market_start + timedelta(minutes=duration)
    return market_start <= now <= market_end

def get_market_close_time():
    market_hour = int(get_config('market_hour', '13'))
    market_minute = int(get_config('market_minute', '45'))
    duration = int(get_config('market_duration', '120'))
    now = datetime.now()
    market_start = now.replace(hour=market_hour, minute=market_minute, second=0, microsecond=0)
    return market_start + timedelta(minutes=duration)

def generate_auction_pig():
    rarities = list(RARITIES.keys())
    weights = [RARITIES[r]['weight'] for r in rarities]
    rarity_key = random.choices(rarities, weights=weights, k=1)[0]
    rarity = RARITIES[rarity_key]

    name = f"{random.choice(PIG_NAME_PREFIXES)} {random.choice(PIG_NAME_SUFFIXES)}"
    emoji = random.choice(PIG_EMOJIS)
    origin = random.choice(PIG_ORIGINS)

    min_s, max_s = rarity['stats_range']
    min_r, max_r = rarity['max_races_range']
    min_p, max_p = rarity['price_range']

    if is_market_open():
        ends = get_market_close_time()
    else:
        ends = datetime.utcnow() + timedelta(hours=2)

    stats = {s: round(random.uniform(min_s, max_s), 1) for s in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']}
    stats[origin['bonus_stat']] = min(100, stats[origin['bonus_stat']] + origin['bonus'])

    return Auction(
        pig_name=name, pig_emoji=emoji,
        pig_vitesse=stats['vitesse'], pig_endurance=stats['endurance'],
        pig_agilite=stats['agilite'], pig_force=stats['force'],
        pig_intelligence=stats['intelligence'], pig_moral=stats['moral'],
        pig_weight=generate_weight_kg_for_profile(stats),
        pig_rarity=rarity_key,
        pig_max_races=random.randint(min_r, max_r),
        pig_origin=origin['country'], pig_origin_flag=origin['flag'],
        starting_price=random.randint(min_p, max_p),
        current_bid=0,
        ends_at=ends,
        status='active'
    )

def resolve_auctions():
    now = datetime.utcnow()
    expired = Auction.query.filter(Auction.status == 'active', Auction.ends_at <= now).all()

    for auction in expired:
        auction = apply_row_lock(Auction.query.filter_by(id=auction.id)).first()
        if not auction or auction.status != 'active' or auction.ends_at > now:
            continue
        if auction.bidder_id and auction.current_bid > 0:
            auction.status = 'sold'
            winner = User.query.get(auction.bidder_id)
            if winner:
                active_pigs = Pig.query.filter_by(user_id=winner.id, is_alive=True).order_by(Pig.id).all()
                if len(active_pigs) >= 2:
                    active_pigs[0].kill(cause='sacrifice')

                origin_data = next((o for o in PIG_ORIGINS if o['country'] == auction.pig_origin), PIG_ORIGINS[0])
                new_pig = Pig(
                    user_id=winner.id, name=build_unique_pig_name(auction.pig_name, fallback_prefix='Champion du marche'), emoji=auction.pig_emoji,
                    vitesse=auction.pig_vitesse, endurance=auction.pig_endurance,
                    agilite=auction.pig_agilite, force=auction.pig_force,
                    intelligence=auction.pig_intelligence, moral=auction.pig_moral,
                    weight_kg=auction.pig_weight or DEFAULT_PIG_WEIGHT_KG,
                    max_races=auction.pig_max_races, rarity=auction.pig_rarity,
                    origin_country=auction.pig_origin, origin_flag=auction.pig_origin_flag,
                    energy=80, hunger=60, happiness=70
                )
                db.session.add(new_pig)
            if auction.seller_id:
                buyer_name = winner.username if winner else "un acheteur"
                credit_user_balance(
                    auction.seller_id, auction.current_bid,
                    reason_code='auction_sale',
                    reason_label='Vente au marche',
                    details=f"{auction.pig_name} vendu a {buyer_name}.",
                    reference_type='auction',
                    reference_id=auction.id,
                )
        else:
            auction.status = 'expired'
            if auction.seller_id and auction.source_pig_id:
                returned_pig = Pig.query.get(auction.source_pig_id)
                if returned_pig and returned_pig.user_id == auction.seller_id:
                    returned_pig.is_alive = True
                    returned_pig.death_date = None
                    returned_pig.death_cause = None
                    returned_pig.charcuterie_type = None
                    returned_pig.charcuterie_emoji = None
                    returned_pig.epitaph = None

    if is_market_open():
        active_count = Auction.query.filter_by(status='active').count()
        while active_count < 5:
            db.session.add(generate_auction_pig())
            active_count += 1

    db.session.commit()


# ─── HELPERS COURSE ─────────────────────────────────────────────────────────

def get_next_race_time():
    race_hour = int(get_config('race_hour', '14'))
    race_minute = int(get_config('race_minute', '00'))
    now = datetime.now()
    today_race = now.replace(hour=race_hour, minute=race_minute, second=0, microsecond=0)
    if now >= today_race:
        return today_race + timedelta(days=1)
    return today_race

def ensure_next_race():
    next_time = get_next_race_time()
    existing = Race.query.filter(
        Race.scheduled_at == next_time,
        Race.status.in_(['upcoming', 'open'])
    ).first()
    if existing:
        populate_race_participants(existing, respect_course_plans=True, allow_rebuild_if_bets=False, commit=True)
        refresh_race_betting_lines(existing)
        return existing

    race = Race(scheduled_at=next_time, status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=True)
    return race

def run_race_if_needed():
    now = datetime.now()
    due_races = Race.query.filter(Race.status == 'open', Race.scheduled_at <= now).all()

    for race in due_races:
        participants = Participant.query.filter_by(race_id=race.id).all()
        if not participants:
            continue

        real_participants = [p for p in participants if p.owner_name]
        min_real = int(get_config('min_real_participants', '2'))
        mode = get_config('empty_race_mode', 'fill')

        if len(real_participants) < min_real and mode == 'cancel':
            race.status = 'cancelled'
            race.finished_at = now
            # Refund bets
            bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
            for bet in bets:
                bet.status = 'refunded'
                credit_user_balance(
                    bet.user_id, bet.amount,
                    reason_code='bet_refund',
                    reason_label='Remboursement pari',
                    details=f"Course #{race.id} annulee (nombre de participants reels insuffisant).",
                    reference_type='race',
                    reference_id=race.id,
                )
            db.session.commit()
            continue

        participants_by_id = {participant.id: participant for participant in participants}
        
        # New Tactical Simulation
        # Fetch actual pig stats for simulation
        pigs_for_sim = []
        for p in participants:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if pig:
                    pig.strategy = p.strategy # Sync current player strategy
                    pigs_for_sim.append(pig)
                else:
                    # Mock NPC pig stats based on odds
                    pigs_for_sim.append({
                        'id': p.id, 'name': p.name, 'emoji': p.emoji,
                        'vitesse': 20 + (1.0/p.odds)*100, 'endurance': 30, 'force': 30, 'agilite': 30,
                        'intelligence': 30, 'moral': 50, 'strategy': 50
                    })
            else:
                # Mock NPC pig stats based on odds
                pigs_for_sim.append({
                    'id': p.id, 'name': p.name, 'emoji': p.emoji,
                    'vitesse': 20 + (1.0/p.odds)*100, 'endurance': 30, 'force': 30, 'agilite': 30,
                    'intelligence': 30, 'moral': 50, 'strategy': 50
                })

        segments = generate_course_segments()
        manager = CourseManager(pigs_for_sim, segments)
        history = manager.run()
        race.replay_json = manager.to_json()

        # Determine order from finish_time and distance
        final_pigs = sorted(manager.participants, key=lambda x: (x.finish_time or 9999, -x.distance))
        
        order = []
        for fp in final_pigs:
            participant = participants_by_id.get(fp.id)
            if participant:
                order.append(participant)

        for i, p in enumerate(order):
            p.finish_position = i + 1

        winner_participant = order[0]
        race.winner_name = winner_participant.name
        race.winner_odds = winner_participant.odds
        race.finished_at = now
        race.status = 'finished'

        POSITION_XP = {1: 100, 2: 60, 3: 40, 4: 25, 5: 15, 6: 10, 7: 5, 8: 3}
        num_participants = len(order)

        for p in order:
            if p.pig_id:
                pig = Pig.query.get(p.pig_id)
                if not pig or not pig.is_alive:
                    continue
                owner = User.query.get(pig.user_id)
                pig.races_entered += 1
                xp_gained = POSITION_XP.get(p.finish_position, 3)

                if owner:
                    theme = get_course_theme(race.scheduled_at)
                    reward_multiplier = theme.get('reward_multiplier', 1)
                    reward = (RACE_APPEARANCE_REWARD + RACE_POSITION_REWARDS.get(p.finish_position, 0.0)) * reward_multiplier
                    details = f"{pig.name} a termine {p.finish_position}e sur la course #{race.id}."
                    if reward_multiplier > 1:
                        details += f" Bonus {theme['name']} x{reward_multiplier} applique."
                    credit_user_balance(
                        owner.id, reward,
                        reason_code='race_reward',
                        reason_label="Prime d'éleveur",
                        details=details,
                        reference_type='race',
                        reference_id=race.id,
                    )

                if pig.challenge_mort_wager > 0:
                    wager = pig.challenge_mort_wager
                    if p.finish_position <= 3:
                        if owner:
                            credit_user_balance(
                                owner.id, wager * 3,
                                reason_code='challenge_payout',
                                reason_label='Gain Challenge de la Mort',
                                details=f"{pig.name} a survecu au Challenge de la Mort sur la course #{race.id}.",
                                reference_type='race',
                                reference_id=race.id,
                            )
                        xp_gained *= 2
                        pig.happiness = min(100, pig.happiness + 15)
                    elif p.finish_position == num_participants:
                        pig.kill(cause='challenge')
                        pig.challenge_mort_wager = 0
                        continue
                    pig.challenge_mort_wager = 0

                pig.xp += xp_gained
                if p.finish_position == 1:
                    pig.races_won += 1
                    pig.vitesse = min(100, pig.vitesse + random.uniform(0.5, 1.5))
                    pig.endurance = min(100, pig.endurance + random.uniform(0.5, 1.5))
                    pig.moral = min(100, pig.moral + 2)
                elif p.finish_position <= 3:
                    pig.moral = min(100, pig.moral + 1)
                    stat = random.choice(['vitesse', 'endurance', 'agilite', 'force', 'intelligence'])
                    setattr(pig, stat, min(100, getattr(pig, stat) + random.uniform(0.3, 0.8)))

                pig.energy = max(0, pig.energy - 15)
                pig.hunger = max(0, pig.hunger - 10)
                pig.adjust_weight(-0.3)
                pig.last_updated = datetime.utcnow()
                pig.check_level_up()

                base_risk = (pig.injury_risk or MIN_INJURY_RISK) / 100.0
                fatigue_factor = 1.0 + max(0, (50 - pig.energy) / 100)
                hunger_factor = 1.0 + max(0, (30 - pig.hunger) / 100)
                weight_profile = get_weight_profile(pig)
                effective_risk = min(0.70, base_risk * fatigue_factor * hunger_factor * weight_profile['injury_factor'])
                if random.random() < effective_risk and not pig.is_injured:
                    pig.is_injured = True
                    pig.vet_deadline = datetime.utcnow() + timedelta(minutes=VET_RESPONSE_MINUTES)
                    pig.challenge_mort_wager = 0
                else:
                    pig.injury_risk = min(MAX_INJURY_RISK, (pig.injury_risk or MIN_INJURY_RISK) + random.uniform(0.3, 0.8))

                if pig.max_races and pig.races_entered >= pig.max_races:
                    pig.retire()

        bets = Bet.query.filter_by(race_id=race.id, status='pending').all()
        finish_order_ids = [participant.id for participant in order]
        for bet in bets:
            bet_type = normalize_bet_type(getattr(bet, 'bet_type', None))
            expected_count = BET_TYPES[bet_type]['selection_count']
            selection_ids = get_bet_selection_ids(bet, participants_by_id)
            if len(selection_ids) == expected_count and finish_order_ids[:expected_count] == selection_ids:
                winnings = round(bet.amount * bet.odds_at_bet, 2)
                bet.status = 'won'
                bet.winnings = winnings
                credit_user_balance(
                    bet.user_id, winnings,
                    reason_code='bet_payout',
                    reason_label='Gain de pari',
                    details=f"Ticket {BET_TYPES[bet_type]['label'].lower()} gagnant sur la course #{race.id}: {bet.pig_name}.",
                    reference_type='bet',
                    reference_id=bet.id,
                )
            else:
                bet.status = 'lost'
                bet.winnings = 0.0

        db.session.commit()

    if due_races:
        ensure_next_race()

def get_race_history_entries():
    races = Race.query.filter(Race.status.in_(['finished', 'cancelled'])).order_by(Race.finished_at.desc(), Race.id.desc()).all()
    if not races:
        return []

    race_ids = [race.id for race in races]
    participants = Participant.query.filter(Participant.race_id.in_(race_ids)).all()
    participants_by_race = {}
    for participant in participants:
        participants_by_race.setdefault(participant.race_id, []).append(participant)

    bet_stats_rows = (
        db.session.query(
            Bet.race_id,
            func.count(Bet.id),
            func.coalesce(func.sum(Bet.amount), 0.0),
            func.coalesce(func.sum(Bet.winnings), 0.0),
        )
        .filter(Bet.race_id.in_(race_ids))
        .group_by(Bet.race_id)
        .all()
    )
    bet_stats_by_race = {
        race_id: {
            'bet_count': bet_count,
            'total_staked': round(float(total_staked or 0.0), 2),
            'total_paid_out': round(float(total_paid_out or 0.0), 2),
        }
        for race_id, bet_count, total_staked, total_paid_out in bet_stats_rows
    }

    entries = []
    for race in races:
        ordered_participants = sorted(
            participants_by_race.get(race.id, []),
            key=lambda participant: (
                participant.finish_position is None,
                participant.finish_position or 999,
                participant.id,
            )
        )
        stats = bet_stats_by_race.get(race.id, {'bet_count': 0, 'total_staked': 0.0, 'total_paid_out': 0.0})
        entries.append({
            'race': race,
            'participants': ordered_participants,
            'podium': ordered_participants[:3],
            'winner': ordered_participants[0] if ordered_participants else None,
            'player_count': sum(1 for participant in ordered_participants if participant.owner_name),
            'npc_count': sum(1 for participant in ordered_participants if not participant.owner_name),
            'bet_count': stats['bet_count'],
            'total_staked': stats['total_staked'],
            'total_paid_out': stats['total_paid_out'],
        })
    return entries


# ─── BOURSE AUX GRAINS ──────────────────────────────────────────────────────

def get_grain_market():
    """Retourne le singleton GrainMarket (le cree si absent)."""
    market = GrainMarket.query.first()
    if market is None:
        market = GrainMarket(
            id=1,
            cursor_x=BOURSE_DEFAULT_POS,
            cursor_y=BOURSE_DEFAULT_POS,
        )
        db.session.add(market)
        db.session.commit()
    return market


# ── Positions & surcouts ─────────────────────────────────────────

def _cell_value(grid_index):
    """Valeur de surcout pour un indice 0-6 de la grille 7x7."""
    return BOURSE_GRID_VALUES[max(0, min(BOURSE_GRID_SIZE - 1, grid_index))]


def get_grain_grid_pos(market, dx, dy):
    """Position absolue (gx, gy) sur la grille 7x7 d'un grain relatif (dx, dy)."""
    bx = market.cursor_x if market.cursor_x is not None else BOURSE_DEFAULT_POS
    by = market.cursor_y if market.cursor_y is not None else BOURSE_DEFAULT_POS
    return (bx + dx, by + dy)


def get_grain_surcharge(gx, gy):
    """Surcout (multiplicateur) pour un grain a la position absolue (gx, gy).

    Retourne un float >= 1.0.  Centre (3,3) -> valeurs 0+0 -> x1.00.
    Coin extreme (0,0) -> valeurs 6+6=12 -> x1.60.
    """
    val = _cell_value(gx) + _cell_value(gy)
    return 1.0 + val * BOURSE_SURCHARGE_FACTOR


def get_all_grain_surcharges(market):
    """Dict {cereal_key: surcharge_multiplier} pour chaque grain du bloc 3x3."""
    result = {}
    for (dx, dy), cereal_key in BOURSE_GRAIN_LAYOUT.items():
        if cereal_key is None:
            continue
        gx, gy = get_grain_grid_pos(market, dx, dy)
        result[cereal_key] = get_grain_surcharge(gx, gy)
    return result


# ── Mouvement ────────────────────────────────────────────────────

def get_bourse_movement_points(user_id):
    """Nombre de cases que l'utilisateur peut deplacer le curseur."""
    total_purchases = db.session.query(func.count(BalanceTransaction.id)).filter(
        BalanceTransaction.user_id == user_id,
        BalanceTransaction.reason_code == 'feed_purchase',
    ).scalar() or 0
    return max(BOURSE_MIN_MOVEMENT, total_purchases // BOURSE_MOVEMENT_DIVISOR)


def move_bourse_cursor(market, dx, dy, max_points):
    """Deplace le centre du bloc 3x3 de (dx, dy).

    Le centre est contraint entre BLOCK_MIN et BLOCK_MAX (1-5)
    pour que le bloc 3x3 reste dans la grille 7x7.
    Retourne le nombre de points consommes.
    """
    if dx == 0 and dy == 0:
        return 0

    # Limiter au nombre de points dispo
    total_requested = abs(dx) + abs(dy)
    if total_requested > max_points:
        if dx != 0:
            dx = max(-max_points, min(max_points, dx))
        else:
            dy = max(-max_points, min(max_points, dy))

    # Clamper aux bornes du bloc
    new_x = max(BOURSE_BLOCK_MIN, min(BOURSE_BLOCK_MAX, market.cursor_x + dx))
    new_y = max(BOURSE_BLOCK_MIN, min(BOURSE_BLOCK_MAX, market.cursor_y + dy))
    actual_dx = new_x - market.cursor_x
    actual_dy = new_y - market.cursor_y
    points_used = abs(actual_dx) + abs(actual_dy)

    market.cursor_x = new_x
    market.cursor_y = new_y
    return points_used


# ── Vitrine (anti-spam) ──────────────────────────────────────────

def is_grain_blocked(grain_key, market):
    """Retourne True si ce grain est actuellement bloque en vitrine."""
    return market.vitrine_grain == grain_key


def update_vitrine(market, grain_key, user_id):
    """Met a jour la vitrine apres un achat."""
    market.vitrine_grain = grain_key
    market.vitrine_user_id = user_id
    market.last_purchase_at = datetime.utcnow()
    market.total_transactions = (market.total_transactions or 0) + 1


# ── Cereales enrichies pour le template ──────────────────────────

def get_bourse_cereals(market, feeding_multiplier=1.0):
    """Retourne les cereales presentes dans le bloc 3x3, avec surcout individuel.

    Chaque cereal est enrichi de :
        original_cost, surcharge, bourse_cost, effective_cost,
        grid_x, grid_y, cell_value, is_blocked, block_dx, block_dy
    """
    surcharges = get_all_grain_surcharges(market)
    result = {}
    for (dx, dy), cereal_key in BOURSE_GRAIN_LAYOUT.items():
        if cereal_key is None:
            continue
        cereals = get_cereals_dict()
        cer = cereals[cereal_key]
        gx, gy = get_grain_grid_pos(market, dx, dy)
        surcharge = surcharges[cereal_key]
        c = dict(cer)
        c['original_cost'] = cer['cost']
        c['surcharge'] = surcharge
        c['bourse_cost'] = round(cer['cost'] * surcharge, 2)
        c['effective_cost'] = round(cer['cost'] * surcharge * feeding_multiplier, 2)
        c['grid_x'] = gx
        c['grid_y'] = gy
        c['cell_value'] = _cell_value(gx) + _cell_value(gy)
        c['is_blocked'] = is_grain_blocked(cereal_key, market)
        c['block_dx'] = dx
        c['block_dy'] = dy
        result[cereal_key] = c
    return result


# ── Donnees de grille 7x7 pour le template ───────────────────────

def get_bourse_grid_data(market):
    """Construit les donnees de la grille 7x7 avec le bloc 3x3 superpose."""
    bx = market.cursor_x if market.cursor_x is not None else BOURSE_DEFAULT_POS
    by = market.cursor_y if market.cursor_y is not None else BOURSE_DEFAULT_POS

    # Index inversé : grain relatif -> cereal key
    block_grains = {}
    for (dx, dy), ck in BOURSE_GRAIN_LAYOUT.items():
        abs_x, abs_y = bx + dx, by + dy
        block_grains[(abs_x, abs_y)] = ck  # ck peut etre None (case vide du bloc)

    grid = []
    for y in range(BOURSE_GRID_SIZE):        # y=0 en haut
        row = []
        for x in range(BOURSE_GRID_SIZE):    # x=0 a gauche
            val_x = BOURSE_GRID_VALUES[x]
            val_y = BOURSE_GRID_VALUES[y]
            cell_value = val_x + val_y
            is_block = (abs(x - bx) <= 1 and abs(y - by) <= 1)
            is_center = (x == bx and y == by)
            grain_key = block_grains.get((x, y))  # None si hors bloc ou case vide
            _cereals = get_cereals_dict()
            grain_emoji = _cereals[grain_key]['emoji'] if grain_key and grain_key in _cereals else None
            grain_name = _cereals[grain_key]['name'] if grain_key and grain_key in _cereals else None

            row.append({
                'x': x, 'y': y,
                'val_x': val_x,
                'val_y': val_y,
                'cell_value': cell_value,
                'surcharge': round(1.0 + cell_value * BOURSE_SURCHARGE_FACTOR, 2),
                'is_block': is_block,
                'is_center': is_center,
                'grain_key': grain_key,
                'grain_emoji': grain_emoji,
                'grain_name': grain_name,
            })
        grid.append(row)
    return grid


# ══════════════════════════════════════════════════════════════════════════════
# Données de jeu dynamiques (DB) — remplace les constantes data.py
# ══════════════════════════════════════════════════════════════════════════════

def _is_available(item):
    """Vérifie qu'un item est actif et dans sa fenêtre de disponibilité."""
    if not item.is_active:
        return False
    now = datetime.utcnow()
    if item.available_from and now < item.available_from:
        return False
    if item.available_until and now > item.available_until:
        return False
    return True


def get_cereals_dict():
    """Retourne un dict {key: {...}} identique à l'ancien data.CEREALS, depuis la DB.
    Fallback sur data.CEREALS si la table est vide (1er lancement)."""
    items = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    if not items:
        return CEREALS  # fallback constantes
    return {c.key: c.to_dict() for c in items if _is_available(c)}


def get_trainings_dict():
    """Retourne un dict {key: {...}} identique à l'ancien data.TRAININGS, depuis la DB."""
    from data import TRAININGS
    items = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    if not items:
        return TRAININGS
    return {t.key: t.to_dict() for t in items if _is_available(t)}


def get_school_lessons_dict():
    """Retourne un dict {key: {...}} identique à l'ancien data.SCHOOL_LESSONS, depuis la DB."""
    from data import SCHOOL_LESSONS
    items = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    if not items:
        return SCHOOL_LESSONS
    return {l.key: l.to_dict() for l in items if _is_available(l)}


def get_all_cereals_dict():
    """Comme get_cereals_dict() mais inclut les items inactifs (pour l'admin)."""
    items = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    return {c.key: c for c in items}


def get_all_trainings_dict():
    """Comme get_trainings_dict() mais inclut les items inactifs (pour l'admin)."""
    items = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    return {t.key: t for t in items}


def get_all_school_lessons_dict():
    """Comme get_school_lessons_dict() mais inclut les items inactifs (pour l'admin)."""
    items = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    return {l.key: l for l in items}


# ─── DOMAIN SERVICES (compatibility re-exports) ────────────────────────────
from services.finance_service import (
    adjust_user_balance, credit_user_balance, debit_user_balance,
    maybe_grant_emergency_relief, record_balance_transaction,
    release_pig_challenge_slot, reserve_pig_challenge_slot,
)
from services.market_service import (
    get_bourse_cereals, get_bourse_grid_data, get_bourse_movement_points,
    get_grain_market, get_grain_grid_pos, get_grain_surcharge,
    get_market_close_time, get_next_market_time, get_prix_moyen_groin,
    get_all_grain_surcharges, is_grain_blocked, is_market_open,
    move_bourse_cursor, resolve_auctions, update_vitrine, generate_auction_pig,
)
from services.pig_service import (
    adjust_pig_weight, apply_origin_bonus, build_unique_pig_name,
    calculate_pig_power, calculate_target_weight_kg, can_retire_into_heritage,
    check_level_up, clamp_pig_weight, create_offspring, create_preloaded_admin_pigs,
    generate_weight_kg_for_profile, get_active_listing_count, get_adoption_cost,
    get_feeding_cost_multiplier, get_freshness_bonus, get_lineage_label,
    get_max_pig_slots, get_pig_heritage_value, get_pig_performance_flags,
    get_pig_slot_count, get_weight_profile, get_weight_stat, is_pig_name_taken,
    normalize_pig_name, reset_snack_share_limit_if_needed, retire_pig_into_heritage,
    update_pig_state, xp_for_level,
)
from services.race_service import (
    build_course_schedule, calculate_bet_odds, calculate_ordered_finish_probability,
    count_pig_weekly_course_commitments, format_bet_label, generate_course_segments,
    get_bet_selection_ids, get_course_theme, get_next_race_time,
    get_pig_dashboard_status, get_pig_last_race_datetime, get_planned_pig_ids_for_slot,
    get_race_ready_pigs, get_upcoming_course_slots, get_user_weekly_bet_count,
    get_week_window, normalize_bet_type, parse_selection_ids,
    populate_race_participants, serialize_selection_ids, build_weighted_finish_order,
)
