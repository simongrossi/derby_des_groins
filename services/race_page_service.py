from datetime import datetime

from models import Bet, Participant, Race, User
from helpers import ensure_next_race, ensure_race_for_slot, get_user_active_pigs
from services.economy_service import (
    get_bet_limits,
    get_configured_bet_types,
    get_weekly_bacon_tickets_value,
    get_weekly_race_quota_value,
)
from services.pig_service import calculate_pig_power, get_weight_profile, update_pig_vitals
from services.race_service import (
    attach_bet_outcome_snapshots,
    build_course_schedule,
    calculate_bet_odds,
    count_pig_weekly_course_commitments,
    get_course_theme,
    get_upcoming_course_slots,
    get_user_weekly_bet_count,
)

JOURS_FR_SHORT = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
MOIS_FR = ['', 'Janv', 'Fev', 'Mars', 'Avril', 'Mai', 'Juin', 'Juil', 'Aout', 'Sept', 'Oct', 'Nov', 'Dec']


def build_courses_page_context(user):
    ensure_next_race()
    pigs = get_user_active_pigs(user)
    weekly_quota = get_weekly_race_quota_value()

    pigs_data = []
    for pig in pigs:
        update_pig_vitals(pig)
        weekly_commitments = count_pig_weekly_course_commitments(pig.id, datetime.now())
        pigs_data.append({
            'pig': pig,
            'power': round(calculate_pig_power(pig), 1),
            'weekly_commitments': weekly_commitments,
            'weekly_remaining': max(0, weekly_quota - weekly_commitments),
            'weight_profile': get_weight_profile(pig),
        })

    schedule = build_course_schedule(user, pigs, days=2)
    next_week_slots = schedule[:24]
    for slot_entry in schedule:
        slot_dt = slot_entry['slot']
        slot_entry['date_key'] = slot_dt.strftime('%Y-%m-%d')
        slot_entry['date_label'] = (
            f"{JOURS_FR_SHORT[slot_dt.weekday()]}. {slot_dt.day} {MOIS_FR[slot_dt.month]}"
        )

    inscribed_slots = [slot for slot in next_week_slots if slot.get('user_plans')]
    next_pig_races = []
    for slot in inscribed_slots:
        for plan in slot['user_plans']:
            if not plan.pig:
                continue
            next_pig_races.append({
                'pig': plan.pig,
                'slot': slot['slot'],
                'theme': slot['theme'],
                'date_label': slot.get('date_label', ''),
            })
    next_pig_races.sort(key=lambda race_entry: race_entry['slot'])

    return {
        'user': user,
        'pigs_data': pigs_data,
        'next_week_slots': next_week_slots,
        'month_slots': schedule,
        'weekly_quota': weekly_quota,
        'now': datetime.now(),
        'total_inscribed': len(inscribed_slots),
        'next_pig_races': next_pig_races[:5],
    }


def build_betting_page_context(user_id=None, race_id=None, slot_str=None):
    bet_types = get_configured_bet_types()
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_limits = get_bet_limits()
    next_race = None

    if race_id:
        next_race = Race.query.filter_by(id=race_id, status='open').first()
    elif slot_str:
        try:
            next_race = ensure_race_for_slot(datetime.fromisoformat(slot_str))
        except ValueError:
            next_race = None

    if not next_race:
        ensure_next_race()
        next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()

    now = datetime.now()
    all_slots = get_upcoming_course_slots(days=3)
    future_slots = [slot for slot in all_slots if slot > now]
    if next_race:
        future_slots = [slot for slot in future_slots if slot != next_race.scheduled_at]
    future_slots = future_slots[:8]

    opened_races = (
        Race.query
        .filter(Race.scheduled_at.in_(future_slots), Race.status == 'open')
        .all()
        if future_slots else []
    )
    opened_races_by_slot = {race.scheduled_at: race for race in opened_races}
    upcoming_elements = [
        {
            'slot': slot,
            'race': opened_races_by_slot.get(slot),
            'status': 'open' if opened_races_by_slot.get(slot) else 'upcoming',
        }
        for slot in future_slots
    ]

    user = User.query.get(user_id) if user_id else None
    user_bets = []
    recent_bets = []
    pending_bets = []
    pigs = []
    bacon_tickets_remaining = weekly_bacon_tickets
    headline_status = {'participates': False}

    if user:
        pigs = get_user_active_pigs(user)
        weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
        bacon_tickets_remaining = max(0, weekly_bacon_tickets - weekly_bet_count)
        if next_race:
            user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()
        recent_bets = (
            Bet.query
            .filter_by(user_id=user.id)
            .order_by(Bet.placed_at.desc(), Bet.id.desc())
            .limit(10)
            .all()
        )
        attach_bet_outcome_snapshots(recent_bets)
        pending_bets = (
            Bet.query
            .join(Race, Bet.race_id == Race.id)
            .filter(Bet.user_id == user.id, Bet.status == 'pending')
            .order_by(Race.scheduled_at.asc())
            .all()
        )

    participants = []
    next_race_theme = None
    if next_race:
        next_race_theme = get_course_theme(next_race.scheduled_at)
        participants = Participant.query.filter_by(race_id=next_race.id).all()
        reward_multiplier = float((next_race_theme or {}).get('reward_multiplier', 1) or 1)
        participants_by_id = {participant.id: participant for participant in participants}
        for participant in participants:
            participant.odds = calculate_bet_odds(
                participants_by_id,
                [participant.id],
                'win',
                reward_multiplier=reward_multiplier,
            )
        participants = sorted(participants, key=lambda participant: participant.odds or 999.0)
        if user and pigs:
            user_pig_ids = {pig.id for pig in pigs}
            headline_status = {
                'participates': any(
                    participant.pig_id and participant.pig_id in user_pig_ids
                    for participant in participants
                )
            }

    return {
        'user': user,
        'next_race': next_race,
        'next_race_theme': next_race_theme,
        'participants': participants,
        'user_bets': user_bets,
        'recent_bets': recent_bets,
        'pending_bets': pending_bets,
        'upcoming_elements': upcoming_elements,
        'bacon_tickets_remaining': bacon_tickets_remaining,
        'weekly_bacon_tickets': weekly_bacon_tickets,
        'headline_status': headline_status,
        'bet_types': bet_types,
        'min_bet_race': bet_limits['min_bet_race'],
        'max_bet_race': bet_limits['max_bet_race'],
        'max_payout_race': bet_limits['max_payout_race'],
        'now': datetime.now(),
    }
