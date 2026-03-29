from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
import random

from sqlalchemy import func

from data import (
    JOURS_FR, MAX_INJURY_RISK, MIN_INJURY_RISK, PIGS,
    PIG_COURSE_SEGMENT_TYPES, VET_RESPONSE_MINUTES,
)
from extensions import db
from models import Bet, CoursePlan, Participant, Pig, Race, User
from race_engine import CourseManager

from helpers.db import apply_row_lock
from services.economy_service import get_configured_bet_types, get_weekly_race_quota_value
from services.finance_service import credit_user_balance
from services.game_settings_service import get_game_settings
from services.pig_service import calculate_pig_power, get_weight_profile, update_pig_state


class RacePlanningError(Exception):
    """Erreur métier levée pendant la planification d'une course."""


class PigNotFoundError(RacePlanningError):
    pass


class InvalidRaceSlotError(RacePlanningError):
    pass


class RaceLockedError(RacePlanningError):
    pass


class PigNotRaceReadyError(RacePlanningError):
    pass


class RaceAlreadyJoinedError(RacePlanningError):
    pass


class WeeklyQuotaReachedError(RacePlanningError):
    pass


@dataclass(frozen=True)
class BetParticipantSnapshot:
    id: int
    win_probability: float

    @classmethod
    def from_source(cls, source):
        if isinstance(source, dict):
            source_id = source.get('id', 0)
            win_probability = source.get('win_probability', 0.0)
        else:
            source_id = getattr(source, 'id', 0)
            win_probability = getattr(source, 'win_probability', 0.0)
        return cls(id=int(source_id), win_probability=float(win_probability or 0.0))


@dataclass(frozen=True)
class PlannedRaceAction:
    action: str
    pig_name: str
    scheduled_at: datetime


def get_configured_npcs():
    """Renvoie la liste des PNJ de course configurable depuis l'admin."""
    from helpers.config import get_config

    raw_npcs = get_config('race_npcs', '')
    if not raw_npcs:
        return list(PIGS)

    try:
        parsed = json.loads(raw_npcs)
    except (TypeError, ValueError):
        return list(PIGS)

    if not isinstance(parsed, list):
        return list(PIGS)

    normalized = []
    seen_names = set()
    for npc in parsed:
        if not isinstance(npc, dict):
            continue
        name = str(npc.get('name', '')).strip()
        emoji = str(npc.get('emoji', '🐷')).strip() or '🐷'
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        normalized.append({'name': name, 'emoji': emoji})

    return normalized if normalized else list(PIGS)


def normalize_bet_type(bet_type):
    bet_types = get_configured_bet_types()
    return bet_type if bet_type in bet_types else 'win'


def serialize_selection_ids(selection_ids):
    return ','.join(str(int(selection_id)) for selection_id in selection_ids)


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
    return ' -> '.join(participant.name for participant in participants)


def _build_bet_participant_snapshots(participants_by_id):
    return {participant_id: BetParticipantSnapshot.from_source(participant) for participant_id, participant in participants_by_id.items()}


def calculate_ordered_finish_probability(participants_by_id, ordered_ids):
    participant_snapshots = _build_bet_participant_snapshots(participants_by_id)
    remaining_probabilities = {participant_id: max(participant.win_probability, 0.0) for participant_id, participant in participant_snapshots.items()}
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
    bet_types = get_configured_bet_types()
    bet_config = bet_types.get(normalize_bet_type(bet_type), bet_types['win'])
    
    probability = calculate_ordered_finish_probability(participants_by_id, ordered_ids)
    if probability <= 0:
        return 0.0
        
    multiplier = 1.0
    if not bet_config.get('order_matters', True):
        # Unordered permutations: e.g. Tiercé any = 3!
        multiplier *= math.factorial(len(ordered_ids))
        
        # If we just need to find N among top_M, e.g. 2 of 4 (Two in Four), the combinations of positions
        # Actually it's simpler: math.comb(top_n, selection_count)
        top_n = bet_config.get('top_n', len(ordered_ids))
        sel_count = bet_config.get('selection_count', len(ordered_ids))
        if top_n > sel_count:
            multiplier *= math.comb(top_n, sel_count)
            
    final_prob = min(probability * multiplier, 0.99)
    if final_prob <= 0:
        return 0.0
        
    return max(1.1, math.floor(((1 / final_prob) / bet_config['house_edge']) * 10) / 10)


def build_weighted_finish_order(participants):
    remaining = list(participants)
    finish_order = []
    while remaining:
        chosen = random.choices(remaining, weights=[max(participant.win_probability or 0.0, 0.000001) for participant in remaining], k=1)[0]
        finish_order.append(chosen)
        remaining.remove(chosen)
    return finish_order


def generate_course_segments(length=600):
    segments = []
    current_dist = 0
    while current_dist < length:
        seg_type = random.choice(PIG_COURSE_SEGMENT_TYPES)
        seg_len = random.randint(60, 180)
        actual_len = min(seg_len, length - current_dist)
        segments.append({'type': seg_type, 'length': actual_len})
        current_dist += actual_len
    return segments


def get_bet_selection_ids(bet, participants_by_id):
    selection_ids = parse_selection_ids(getattr(bet, 'selection_order', None))
    if selection_ids:
        return selection_ids
    matching_participant = next((participant for participant in participants_by_id.values() if participant.name == bet.pig_name), None)
    return [matching_participant.id] if matching_participant else []


def get_week_window(anchor_dt):
    week_start = (anchor_dt - timedelta(days=anchor_dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return week_start, week_start + timedelta(days=7)


def get_user_weekly_bet_count(user, anchor_dt=None):
    if not user:
        return 0
    week_start, week_end = get_week_window(anchor_dt or datetime.now())
    return Bet.query.filter(Bet.user_id == user.id, Bet.placed_at >= week_start, Bet.placed_at < week_end).count()


def count_pig_weekly_course_commitments(pig_id, anchor_dt, exclude_scheduled_at=None):
    week_start, week_end = get_week_window(anchor_dt)
    planned_query = CoursePlan.query.filter(CoursePlan.pig_id == pig_id, CoursePlan.scheduled_at >= week_start, CoursePlan.scheduled_at < week_end)
    if exclude_scheduled_at is not None:
        planned_query = planned_query.filter(CoursePlan.scheduled_at != exclude_scheduled_at)
    actual_query = db.session.query(func.count(Participant.id)).join(Race, Participant.race_id == Race.id).filter(Participant.pig_id == pig_id, Race.scheduled_at >= week_start, Race.scheduled_at < week_end, Race.status.in_(['open', 'finished']))
    if exclude_scheduled_at is not None:
        actual_query = actual_query.filter(Race.scheduled_at != exclude_scheduled_at)
    return int(planned_query.count() + (actual_query.scalar() or 0))


def batch_pig_weekly_commitments(pig_ids, anchor_dt):
    """Pre-load weekly commitments for all pigs in 2 queries instead of 2*N."""
    if not pig_ids:
        return {}
    week_start, week_end = get_week_window(anchor_dt)
    planned_counts = dict(
        db.session.query(CoursePlan.pig_id, func.count(CoursePlan.id))
        .filter(CoursePlan.pig_id.in_(pig_ids), CoursePlan.scheduled_at >= week_start, CoursePlan.scheduled_at < week_end)
        .group_by(CoursePlan.pig_id).all()
    )
    actual_counts = dict(
        db.session.query(Participant.pig_id, func.count(Participant.id))
        .join(Race, Participant.race_id == Race.id)
        .filter(Participant.pig_id.in_(pig_ids), Race.scheduled_at >= week_start, Race.scheduled_at < week_end, Race.status.in_(['open', 'finished']))
        .group_by(Participant.pig_id).all()
    )
    return {pid: int(planned_counts.get(pid, 0) + actual_counts.get(pid, 0)) for pid in pig_ids}


def get_course_theme(slot_time):
    """Retourne le thème de course pour un créneau donné.

    Charge depuis GameConfig clé 'race_themes' (JSON), avec fallback
    sur les defaults hardcodés dans helpers/config.py.
    """
    import json
    from helpers.config import get_config, DEFAULT_RACE_THEMES

    weekday = str(slot_time.weekday())
    raw = get_config('race_themes', '')
    if raw:
        try:
            themes = json.loads(raw)
            if weekday in themes:
                # Fusionner avec le default pour garantir toutes les clés
                return {**DEFAULT_RACE_THEMES.get(weekday, {}), **themes[weekday]}
        except (json.JSONDecodeError, TypeError):
            pass
    return dict(DEFAULT_RACE_THEMES.get(weekday, DEFAULT_RACE_THEMES["5"]))


def get_next_race_time():
    """Renvoie le prochain créneau de course défini dans la grille horaire admin."""
    settings = get_game_settings()
    schedule = settings.schedule_dict
    now = datetime.now()
    
    # On regarde aujourd'hui et les 7 prochains jours
    for i in range(8):
        day = now + timedelta(days=i)
        day_idx = str(day.weekday())
        times = schedule.get(day_idx, [])
        for t_str in sorted(times):
            try:
                h, m = map(int, t_str.split(':'))
                race_time = day.replace(hour=h, minute=m, second=0, microsecond=0)
                if race_time > now:
                    return race_time
            except (ValueError, AttributeError):
                continue
    # Fallback si grille vide : demain 14:00
    return (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)


def get_upcoming_course_slots(days=2):
    """Renvoie les prochains créneaux selon la grille horaire, limités aux 'days' prochains jours."""
    settings = get_game_settings()
    schedule = settings.schedule_dict
    now = datetime.now()
    slots = []
    
    max_date = now + timedelta(days=days)
    
    # On itère sur chaque jour de la plage demandée
    for i in range(days + 1):
        day = now + timedelta(days=i)
        day_idx = str(day.weekday())
        times = schedule.get(day_idx, [])
        for t_str in sorted(times):
            try:
                h, m = map(int, t_str.split(':'))
                race_time = day.replace(hour=h, minute=m, second=0, microsecond=0)
                if race_time > now and race_time <= max_date:
                    slots.append(race_time)
            except (ValueError, AttributeError):
                continue
    
    slots.sort()
    return slots[:500]


def _get_open_race_for_slot(scheduled_at):
    return Race.query.filter_by(scheduled_at=scheduled_at, status='open').first()


def plan_pig_for_race(user_id, pig_id, scheduled_at_raw, strategy_profile):
    pig = Pig.query.filter_by(id=pig_id, user_id=user_id, is_alive=True).first()
    if not pig:
        raise PigNotFoundError("Cochon introuvable pour cette planification.")

    try:
        scheduled_at = datetime.fromisoformat((scheduled_at_raw or '').strip()).replace(microsecond=0)
    except ValueError as exc:
        raise InvalidRaceSlotError("Creneau de course invalide.") from exc

    if scheduled_at <= datetime.now() + timedelta(seconds=30):
        raise RaceLockedError("Cette course est trop proche pour modifier les inscriptions.")

    open_race = _get_open_race_for_slot(scheduled_at)
    if open_race and Bet.query.filter_by(race_id=open_race.id).count() > 0:
        raise RaceLockedError("Cette course est deja verrouillee par des paris. Plus de modification possible.")

    if open_race and (pig.is_injured or pig.energy <= 20 or pig.hunger <= 20):
        raise PigNotRaceReadyError(f"{pig.name} n'est pas en etat de rejoindre la course ouverte du moment.")

    already_participant = False
    if open_race:
        already_participant = Participant.query.filter_by(race_id=open_race.id, pig_id=pig.id).first() is not None

    existing_plan = CoursePlan.query.filter_by(user_id=user_id, pig_id=pig.id, scheduled_at=scheduled_at).first()
    if existing_plan:
        db.session.delete(existing_plan)
        if open_race:
            populate_race_participants(open_race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=False)
        db.session.commit()
        return PlannedRaceAction(action='removed', pig_name=pig.name, scheduled_at=scheduled_at)

    if already_participant:
        raise RaceAlreadyJoinedError(f"{pig.name} est deja partant sur cette course ouverte.")

    weekly_quota = get_weekly_race_quota_value()
    if count_pig_weekly_course_commitments(pig.id, scheduled_at) >= weekly_quota:
        raise WeeklyQuotaReachedError(f"{pig.name} a deja atteint son quota hebdomadaire de {weekly_quota} courses.")

    db.session.add(
        CoursePlan(
            user_id=user_id,
            pig_id=pig.id,
            scheduled_at=scheduled_at,
            strategy_profile=CoursePlan.build_strategy_profile(
                phase_1=strategy_profile['phase_1'],
                phase_2=strategy_profile['phase_2'],
                phase_3=strategy_profile['phase_3'],
            ),
        )
    )
    db.session.flush()

    if open_race:
        populate_race_participants(open_race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=False)

    db.session.commit()
    return PlannedRaceAction(action='planned', pig_name=pig.name, scheduled_at=scheduled_at)


def get_race_ready_pigs():
    fit_pigs = Pig.query.filter(Pig.is_alive == True, Pig.is_injured == False, Pig.energy > 20, Pig.hunger > 20).all()
    for pig in fit_pigs:
        update_pig_state(pig)
    fit_pigs = [pig for pig in fit_pigs if not pig.is_injured and pig.energy > 20 and pig.hunger > 20]
    fit_pigs.sort(key=lambda pig: calculate_pig_power(pig), reverse=True)
    return fit_pigs


def get_pig_last_race_datetime(pig):
    if not pig:
        return None
    return db.session.query(func.max(Race.scheduled_at)).join(Participant, Participant.race_id == Race.id).filter(Participant.pig_id == pig.id, Race.status == 'finished').scalar()


def get_pig_dashboard_status(pig):
    if not pig:
        return None
    last_race_at = get_pig_last_race_datetime(pig)
    reference_dt = last_race_at or pig.created_at or datetime.utcnow()
    rest_days = max(0, (datetime.now() - reference_dt).days)
    fatigue_pct = max(0, min(100, int(round(100 - (pig.energy or 0)))))
    health_base = ((pig.energy or 0) * 0.4) + ((pig.hunger or 0) * 0.25) + ((pig.happiness or 0) * 0.35) - (35 if pig.is_injured else 0)
    health_pct = max(0, min(100, int(round(health_base))))
    if rest_days >= 5:
        rest_label, rest_note = 'En pause cafe', "Il prend son temps loin de la piste. La fraicheur remontera au premier geste positif."
    elif rest_days >= 2:
        rest_label, rest_note = 'Se repose', "Un rythme doux, parfait pour garder le cochon serein avant la prochaine sortie."
    else:
        rest_label, rest_note = 'Routine legere', "Petit passage recent sur la piste, rien d'alarmant : il suit simplement son tempo."
    return {'health_pct': health_pct, 'fatigue_pct': fatigue_pct, 'rest_days': rest_days, 'last_race_at': last_race_at, 'rest_label': rest_label, 'rest_note': rest_note}


def get_planned_pig_ids_for_slot(scheduled_at):
    plans = CoursePlan.query.filter(CoursePlan.scheduled_at == scheduled_at).order_by(CoursePlan.created_at.asc(), CoursePlan.id.asc()).all()
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
            fit_pigs.sort(key=lambda pig: (0 if pig.id in planned_order else 1, planned_order.get(pig.id, 999), -calculate_pig_power(pig)))
    fit_pigs = fit_pigs[:max_participants]
    Participant.query.filter_by(race_id=race.id).delete(synchronize_session=False)
    db.session.flush()
    participants_list, all_powers, player_powers = [], [], []
    for pig in fit_pigs:
        power = calculate_pig_power(pig)
        player_powers.append(power)
        all_powers.append(power)
        owner = User.query.get(pig.user_id)
        plan = CoursePlan.query.filter_by(pig_id=pig.id, scheduled_at=race.scheduled_at).first()
        plan_profile = plan.strategy_segments if plan else {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}
        participant = Participant(
            race_id=race.id,
            name=pig.name,
            emoji=pig.emoji,
            avatar_url=pig.avatar_url,
            pig_id=pig.id,
            owner_name=owner.username if owner else None,
            strategy=plan_profile['phase_1'],
            odds=0,
            win_probability=0,
        )
        db.session.add(participant)
        participants_list.append(participant)
    player_names = {pig.name for pig in fit_pigs}
    available_npcs = [npc for npc in get_configured_npcs() if npc['name'] not in player_names]
    npc_count = min(max_participants - len(fit_pigs), len(available_npcs))
    if npc_count > 0:
        avg_player_power = sum(player_powers) / len(player_powers) if player_powers else 34.0
        npc_min_power = max(22.0, avg_player_power * 0.9)
        npc_max_power = max(npc_min_power + 2.0, avg_player_power * 1.1)
        for npc in random.sample(available_npcs, npc_count):
            all_powers.append(random.uniform(npc_min_power, npc_max_power))
            participant = Participant(race_id=race.id, name=npc['name'], emoji=npc['emoji'], avatar_url=None, pig_id=None, owner_name=None, odds=0, win_probability=0)
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
    weekly_quota = get_weekly_race_quota_value()
    slots = get_upcoming_course_slots(days)
    if not slots:
        return []
    slot_start, slot_end = slots[0], slots[-1] + timedelta(seconds=1)
    races = Race.query.filter(Race.scheduled_at >= slot_start, Race.scheduled_at < slot_end, Race.status.in_(['open', 'upcoming'])).order_by(Race.scheduled_at.asc()).all()
    race_by_slot = {race.scheduled_at: race for race in races}
    participants = Participant.query.filter(Participant.race_id.in_([race.id for race in races])).all() if races else []
    participants_by_race = {}
    for participant in participants:
        participants_by_race.setdefault(participant.race_id, []).append(participant)
    plans = CoursePlan.query.filter(CoursePlan.scheduled_at >= slot_start, CoursePlan.scheduled_at < slot_end).order_by(CoursePlan.scheduled_at.asc(), CoursePlan.created_at.asc(), CoursePlan.id.asc()).all()
    plans_by_slot = {}
    for plan in plans:
        plans_by_slot.setdefault(plan.scheduled_at, []).append(plan)

    # Pre-load bet counts per race in one query to avoid N+1
    race_ids_with_races = [race.id for race in races]
    bet_counts_by_race = {}
    if race_ids_with_races:
        bet_counts_by_race = dict(
            db.session.query(Bet.race_id, func.count(Bet.id))
            .filter(Bet.race_id.in_(race_ids_with_races))
            .group_by(Bet.race_id).all()
        )

    # Pre-load weekly commitments per pig per week (batch, 2 queries per week instead of 2 per pig per slot)
    pig_ids = [pig.id for pig in pigs]
    weekly_cache = {}
    for slot_time in slots:
        week_key = get_week_window(slot_time)
        if week_key not in weekly_cache:
            weekly_cache[week_key] = batch_pig_weekly_commitments(pig_ids, slot_time)

    schedule = []
    for slot_time in slots:
        race = race_by_slot.get(slot_time)
        slot_participants = participants_by_race.get(race.id, []) if race else []
        slot_participants.sort(key=lambda participant: (participant.odds or 999, participant.name))
        slot_plan_rows = plans_by_slot.get(slot_time, [])
        slot_user_plans = [plan for plan in slot_plan_rows if plan.user_id == user.id]
        slot_user_plan_by_pig = {plan.pig_id: plan for plan in slot_user_plans}
        slot_actual_pig_ids = {participant.pig_id for participant in slot_participants if participant.pig_id}
        seconds_to_start = (slot_time - now).total_seconds()
        bet_count = bet_counts_by_race.get(race.id, 0) if race else 0
        slot_locked = seconds_to_start < 30 or bet_count > 0

        lock_reason = None
        if seconds_to_start < 30:
            lock_reason = "Départ imminent"
        elif bet_count > 0:
            lock_reason = "Paris déjà placés"

        week_key = get_week_window(slot_time)
        week_commitments = weekly_cache[week_key]

        pig_options = []
        for pig in pigs:
            is_actual_participant = pig.id in slot_actual_pig_ids
            is_planned = pig.id in slot_user_plan_by_pig
            current_strategy = slot_user_plan_by_pig[pig.id].strategy_segments if is_planned else {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}
            weekly_commitments_pig = week_commitments.get(pig.id, 0)
            # If pig is already committed to this slot, don't double-count
            if is_actual_participant or is_planned:
                weekly_commitments_pig = max(0, weekly_commitments_pig - 1)
            projected_commitments = weekly_commitments_pig + (0 if (is_actual_participant or is_planned) else 1)
            quota_reached = weekly_commitments_pig >= weekly_quota and not (is_actual_participant or is_planned)
            can_toggle, disabled_reason = True, None
            if slot_locked:
                can_toggle, disabled_reason = False, lock_reason
            elif race and race.status == 'open' and (pig.is_injured or pig.energy <= 20 or pig.hunger <= 20):
                can_toggle, disabled_reason = False, 'Trop faible pour la course ouverte'
            elif quota_reached:
                can_toggle, disabled_reason = False, 'Quota hebdo atteint'
            pig_options.append({'pig': pig, 'is_planned': is_planned, 'is_actual_participant': is_actual_participant, 'current_strategy_profile': current_strategy, 'current_strategy_summary': f"D {current_strategy['phase_1']} • M {current_strategy['phase_2']} • F {current_strategy['phase_3']}", 'can_toggle': can_toggle, 'disabled_reason': disabled_reason, 'weekly_commitments': projected_commitments, 'quota_remaining': max(0, weekly_quota - weekly_commitments_pig), 'projected_remaining': max(0, weekly_quota - projected_commitments)})
        schedule.append({'slot': slot_time, 'slot_key': slot_time.strftime('%Y-%m-%dT%H:%M:%S'), 'day_name': JOURS_FR[slot_time.weekday()], 'theme': get_course_theme(slot_time), 'race': race, 'participants': slot_participants, 'planned_count': len(slot_plan_rows), 'user_plans': slot_user_plans, 'user_plan_names': [plan.pig.name for plan in slot_user_plans if plan.pig], 'is_next': slot_time == slots[0], 'is_locked': slot_locked, 'lock_reason': lock_reason, 'pig_options': pig_options, 'user_weekly_plan_count': len(slot_user_plans), 'user_weekly_remaining': {pig.id: max(0, weekly_quota - week_commitments.get(pig.id, 0)) for pig in pigs}})
    return schedule
