from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime

from config.game_rules import RACE_PLANNING_RULES
from exceptions import BusinessRuleError
from extensions import limiter
from models import User, Race, Participant, Bet
from helpers import ensure_next_race, get_user_active_pigs, ensure_race_for_slot
from services.bet_service import place_bet_for_user
from services.economy_service import (
    get_bet_limits,
    get_configured_bet_types,
    get_weekly_bacon_tickets_value,
    get_weekly_race_quota_value,
)
from services.pig_service import calculate_pig_power, get_weight_profile, update_pig_vitals
from services.race_service import (
    attach_bet_outcome_snapshots,
    RacePlanningError, build_course_schedule, calculate_bet_odds,
    count_pig_weekly_course_commitments,
    get_course_theme, plan_pig_for_race,
    get_upcoming_course_slots
)

race_bp = Blueprint('race', __name__)


@race_bp.route('/courses')
def courses():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

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

    # Ajouter date_key pour groupby Jinja2 dans le calendrier
    JOURS_FR_SHORT = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    MOIS_FR = ['', 'Janv', 'Fev', 'Mars', 'Avril', 'Mai', 'Juin',
               'Juil', 'Aout', 'Sept', 'Oct', 'Nov', 'Dec']
    for s in schedule:
        dt = s['slot']
        s['date_key'] = dt.strftime('%Y-%m-%d')
        s['date_label'] = f"{JOURS_FR_SHORT[dt.weekday()]}. {dt.day} {MOIS_FR[dt.month]}"

    # Stats d'inscription pour le hero card
    inscribed_slots = [s for s in next_week_slots if s.get('user_plans')]
    total_inscribed = len(inscribed_slots)
    # Prochaines courses inscrites (triées par date)
    next_pig_races = []
    for s in inscribed_slots:
        for plan in s['user_plans']:
            if plan.pig:
                next_pig_races.append({
                    'pig': plan.pig,
                    'slot': s['slot'],
                    'theme': s['theme'],
                    'date_label': s.get('date_label', ''),
                })
    next_pig_races.sort(key=lambda r: r['slot'])

    return render_template(
        'courses.html',
        user=user,
        pigs_data=pigs_data,
        next_week_slots=next_week_slots,
        month_slots=schedule,
        weekly_quota=weekly_quota,
        now=datetime.now(),
        total_inscribed=total_inscribed,
        next_pig_races=next_pig_races[:5],
    )


@race_bp.route('/paris')
def paris():
    """Page dédiée aux paris — cotes, formulaire de pari, historique."""
    bet_types = get_configured_bet_types()
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_limits = get_bet_limits()
    slot_str = request.args.get('slot')
    race_id = request.args.get('race_id', type=int)
    next_race = None

    if race_id:
        next_race = Race.query.filter_by(id=race_id, status='open').first()
    elif slot_str:
        try:
            slot_dt = datetime.fromisoformat(slot_str)
            next_race = ensure_race_for_slot(slot_dt)
        except ValueError:
            pass

    if not next_race:
        ensure_next_race()
        next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()

    now = datetime.now()
    all_slots = get_upcoming_course_slots(days=3)
    future_slots = [s for s in all_slots if s > now]
    if next_race:
        future_slots = [s for s in future_slots if s != next_race.scheduled_at]
    future_slots = future_slots[:8]

    opened_races = Race.query.filter(
        Race.scheduled_at.in_(future_slots),
        Race.status == 'open'
    ).all() if future_slots else []
    
    opened_races_by_slot = {r.scheduled_at: r for r in opened_races}
    
    upcoming_elements = []
    for s in future_slots:
        r = opened_races_by_slot.get(s)
        upcoming_elements.append({
            'slot': s,
            'race': r,
            'status': 'open' if r else 'upcoming'
        })

    user = None
    user_bets = []
    pigs = []
    bacon_tickets_remaining = weekly_bacon_tickets
    headline_status = {'participates': False}
    participants = []
    next_race_theme = None
    recent_bets = []
    pending_bets = []

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            pigs = get_user_active_pigs(user)
            weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
            bacon_tickets_remaining = max(0, weekly_bacon_tickets - weekly_bet_count)
            if next_race:
                user_bets = Bet.query.filter_by(user_id=user.id, race_id=next_race.id).all()
            # Derniers paris de l'utilisateur
            recent_bets = (
                Bet.query.filter_by(user_id=user.id)
                .order_by(Bet.placed_at.desc(), Bet.id.desc())
                .limit(10)
                .all()
            )
            attach_bet_outcome_snapshots(recent_bets)
            # Paris en cours (pending)
            pending_bets = (
                Bet.query
                .join(Race, Bet.race_id == Race.id)
                .filter(Bet.user_id == user.id, Bet.status == 'pending')
                .order_by(Race.scheduled_at.asc())
                .all()
            )

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
        # Vérifier si un cochon du joueur participe
        if user and pigs:
            user_pig_ids = {pig.id for pig in pigs}
            user_has_pig = any(p.pig_id and p.pig_id in user_pig_ids for p in participants)
            headline_status = {'participates': user_has_pig}

    return render_template(
        'paris.html',
        user=user,
        next_race=next_race,
        next_race_theme=next_race_theme,
        participants=participants,
        user_bets=user_bets,
        recent_bets=recent_bets,
        pending_bets=pending_bets,
        upcoming_elements=upcoming_elements,
        bacon_tickets_remaining=bacon_tickets_remaining,
        weekly_bacon_tickets=weekly_bacon_tickets,
        headline_status=headline_status,
        bet_types=bet_types,
        min_bet_race=bet_limits['min_bet_race'],
        max_bet_race=bet_limits['max_bet_race'],
        max_payout_race=bet_limits['max_payout_race'],
        now=datetime.now(),
    )


@race_bp.route('/courses/plan', methods=['POST'])
@limiter.limit("10 per minute")
def plan_course():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    pig_id = request.form.get('pig_id', type=int)
    scheduled_at_raw = (request.form.get('scheduled_at') or '').strip()
    strategy_profile = {
        'phase_1': request.form.get(
            'strategy_phase_1',
            RACE_PLANNING_RULES.default_strategy_phase_1,
            type=int,
        ),
        'phase_2': request.form.get(
            'strategy_phase_2',
            RACE_PLANNING_RULES.default_strategy_phase_2,
            type=int,
        ),
        'phase_3': request.form.get(
            'strategy_phase_3',
            RACE_PLANNING_RULES.default_strategy_phase_3,
            type=int,
        ),
    }

    try:
        action = plan_pig_for_race(user.id, pig_id, scheduled_at_raw, strategy_profile)
    except RacePlanningError as exc:
        category = 'error' if 'invalide' in str(exc).lower() or 'introuvable' in str(exc).lower() else 'warning'
        flash(str(exc), category)
        return redirect(url_for('race.courses'))

    if action.action == 'removed':
        flash(f"📅 {action.pig_name} est retire du planning du {action.scheduled_at.strftime('%d/%m %H:%M')}.", "success")
    else:
        flash(f"📅 {action.pig_name} est maintenant planifie pour la course du {action.scheduled_at.strftime('%d/%m %H:%M')}.", "success")
    return redirect(url_for('race.courses'))


@race_bp.route('/bet', methods=['POST'])
@limiter.limit("10 per minute")
def place_bet():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = place_bet_for_user(
            session['user_id'],
            request.form.get('race_id', type=int),
            request.form.get('bet_type', 'win'),
            request.form.get('selection_order', ''),
            request.form.get('amount', type=float),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('race.paris'))
