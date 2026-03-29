from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from extensions import db, limiter
from models import User, Race, Participant, Bet
from data import COMPLEX_BET_MIN_SELECTIONS
from helpers import ensure_next_race, get_user_active_pigs, apply_row_lock, ensure_race_for_slot
from services.economy_service import (
    get_bet_limits,
    get_configured_bet_types,
    get_effective_bet_odds,
    get_weekly_bacon_tickets_value,
    get_weekly_race_quota_value,
)
from services.pig_service import calculate_pig_power, get_weight_profile
from services.race_service import (
    RacePlanningError, build_course_schedule, calculate_bet_odds,
    count_pig_weekly_course_commitments, format_bet_label,
    get_course_theme, get_user_weekly_bet_count, normalize_bet_type,
    parse_selection_ids, plan_pig_for_race, serialize_selection_ids,
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
        pig.update_vitals()
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
                .order_by(Bet.id.desc())
                .limit(10)
                .all()
            )

    if next_race:
        participants = Participant.query.filter_by(race_id=next_race.id).order_by(Participant.odds).all()
        next_race_theme = get_course_theme(next_race.scheduled_at)
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
        'phase_1': request.form.get('strategy_phase_1', 35, type=int),
        'phase_2': request.form.get('strategy_phase_2', 50, type=int),
        'phase_3': request.form.get('strategy_phase_3', 80, type=int),
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
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))
    bet_types = get_configured_bet_types()
    weekly_bacon_tickets = get_weekly_bacon_tickets_value()
    bet_limits = get_bet_limits()
    weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
    if weekly_bet_count >= weekly_bacon_tickets:
        flash(f"Tu as deja utilise tes {weekly_bacon_tickets} Tickets Bacon de la semaine.", "warning")
        return redirect(url_for('race.paris'))

    race_id = request.form.get('race_id', type=int)
    bet_type = normalize_bet_type(request.form.get('bet_type', 'win'))
    selection_ids = parse_selection_ids(request.form.get('selection_order', '').strip())
    amount = request.form.get('amount', type=float)
    if not all([race_id, amount]):
        flash("Ticket incomplet. Choisis ton pari et ta mise.", "warning")
        return redirect(url_for('race.paris'))

    race = apply_row_lock(Race.query.filter_by(id=race_id)).first()
    if not race or race.status != 'open':
        flash("Cette course n'accepte plus de paris.", "warning")
        return redirect(url_for('race.paris'))

    now = datetime.now()
    if (race.scheduled_at - now).total_seconds() < 30:
        flash("Les paris ferment 30 secondes avant le départ.", "warning")
        return redirect(url_for('race.paris'))

    participants = Participant.query.filter_by(race_id=race_id).all()
    participants_by_id = {participant.id: participant for participant in participants}
    expected_count = bet_types[bet_type]['selection_count']
    if len(participants) < expected_count:
        flash("Pas assez de partants pour ce type de ticket.", "warning")
        return redirect(url_for('race.paris'))

    if len(selection_ids) != expected_count or len(set(selection_ids)) != expected_count:
        flash(f"Ce ticket demande {expected_count} cochon(s) distinct(s) dans l'ordre.", "warning")
        return redirect(url_for('race.paris'))

    selected_participants = [participants_by_id.get(selection_id) for selection_id in selection_ids]
    if any(participant is None for participant in selected_participants):
        flash("Sélection invalide pour cette course.", "error")
        return redirect(url_for('race.paris'))

    if not amount or amount < bet_limits['min_bet_race'] or amount > bet_limits['max_bet_race']:
        flash(f"La mise doit etre entre {bet_limits['min_bet_race']:.0f} et {bet_limits['max_bet_race']:.0f} BitGroins.", "error")
        return redirect(url_for('race.paris'))

    if expected_count >= COMPLEX_BET_MIN_SELECTIONS:
        user_pig_ids = {pig.id for pig in get_user_active_pigs(user)}
        user_has_pig_in_race = any(p.pig_id and p.pig_id in user_pig_ids for p in participants)
        if not user_has_pig_in_race:
            flash("Les paris complexes (3+ cochons) necessitent que ton cochon participe a la course.", "warning")
            return redirect(url_for('race.paris'))

    existing = apply_row_lock(Bet.query.filter_by(user_id=user.id, race_id=race_id)).first()
    if existing:
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('race.paris'))

    raw_odds = calculate_bet_odds(participants_by_id, selection_ids, bet_type)
    if raw_odds <= 0:
        flash("Impossible de calculer la cote de ce ticket.", "error")
        return redirect(url_for('race.paris'))
    odds_at_bet = get_effective_bet_odds(raw_odds, amount)
    if odds_at_bet <= 0:
        flash("Le plafond de gain actuel rend cette mise impossible pour ce ticket.", "error")
        return redirect(url_for('race.paris'))

    bet_label = format_bet_label(selected_participants)
    bet = Bet(
        user_id=user.id,
        race_id=race_id,
        pig_name=bet_label,
        bet_type=bet_type,
        selection_order=serialize_selection_ids(selection_ids),
        amount=amount,
        odds_at_bet=odds_at_bet,
        status='pending'
    )
    try:
        if not user.pay(
            amount,
            reason_code='bet_stake',
            reason_label='Mise de pari',
            details=f"Ticket {bet_types[bet_type]['label'].lower()} sur la course #{race_id}: {bet_label}.",
            reference_type='race',
            reference_id=race_id,
        ):
            flash("Pas assez de BitGroins pour valider ce ticket.", "error")
            return redirect(url_for('race.paris'))
        db.session.add(bet)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('race.paris'))

    flash(f"{bet_types[bet_type]['icon']} Ticket {bet_types[bet_type]['label'].lower()} validé sur {bet_label}.", "success")
    return redirect(url_for('race.paris'))
