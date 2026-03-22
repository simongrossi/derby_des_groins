from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from extensions import db
from models import User, Race, Participant, Bet
from data import BET_TYPES, WEEKLY_RACE_QUOTA, WEEKLY_BACON_TICKETS
from helpers import ensure_next_race, get_user_active_pigs, apply_row_lock
from services.pig_service import calculate_pig_power, get_weight_profile
from services.race_service import (
    RacePlanningError, build_course_schedule, calculate_bet_odds,
    count_pig_weekly_course_commitments, format_bet_label,
    get_user_weekly_bet_count, normalize_bet_type, parse_selection_ids,
    plan_pig_for_race, serialize_selection_ids,
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

    pigs_data = []
    for pig in pigs:
        pig.update_vitals()
        weekly_commitments = count_pig_weekly_course_commitments(pig.id, datetime.now())
        pigs_data.append({
            'pig': pig,
            'power': round(calculate_pig_power(pig), 1),
            'weekly_commitments': weekly_commitments,
            'weekly_remaining': max(0, WEEKLY_RACE_QUOTA - weekly_commitments),
            'weight_profile': get_weight_profile(pig),
        })

    schedule = build_course_schedule(user, pigs, days=30)
    next_week_slots = schedule[:7]

    return render_template(
        'courses.html',
        user=user,
        pigs_data=pigs_data,
        next_week_slots=next_week_slots,
        month_slots=schedule,
        weekly_quota=WEEKLY_RACE_QUOTA,
        now=datetime.now(),
    )


@race_bp.route('/courses/plan', methods=['POST'])
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
def place_bet():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))
    weekly_bet_count = get_user_weekly_bet_count(user, datetime.now())
    if weekly_bet_count >= WEEKLY_BACON_TICKETS:
        flash(f"Tu as deja utilise tes {WEEKLY_BACON_TICKETS} Tickets Bacon de la semaine.", "warning")
        return redirect(url_for('main.index'))

    race_id = request.form.get('race_id', type=int)
    bet_type = normalize_bet_type(request.form.get('bet_type', 'win'))
    selection_ids = parse_selection_ids(request.form.get('selection_order', '').strip())
    amount = request.form.get('amount', type=float)
    if not all([race_id, amount]):
        flash("Ticket incomplet. Choisis ton pari et ta mise.", "warning")
        return redirect(url_for('main.index'))

    race = apply_row_lock(Race.query.filter_by(id=race_id)).first()
    if not race or race.status != 'open':
        flash("Cette course n'accepte plus de paris.", "warning")
        return redirect(url_for('main.index'))

    now = datetime.now()
    if (race.scheduled_at - now).total_seconds() < 30:
        flash("Les paris ferment 30 secondes avant le départ.", "warning")
        return redirect(url_for('main.index'))

    participants = Participant.query.filter_by(race_id=race_id).all()
    participants_by_id = {participant.id: participant for participant in participants}
    expected_count = BET_TYPES[bet_type]['selection_count']
    if len(participants) < expected_count:
        flash("Pas assez de partants pour ce type de ticket.", "warning")
        return redirect(url_for('main.index'))

    if len(selection_ids) != expected_count or len(set(selection_ids)) != expected_count:
        flash(f"Ce ticket demande {expected_count} cochon(s) distinct(s) dans l'ordre.", "warning")
        return redirect(url_for('main.index'))

    selected_participants = [participants_by_id.get(selection_id) for selection_id in selection_ids]
    if any(participant is None for participant in selected_participants):
        flash("Sélection invalide pour cette course.", "error")
        return redirect(url_for('main.index'))

    if amount <= 0:
        flash("Mise invalide pour ton solde actuel.", "error")
        return redirect(url_for('main.index'))

    existing = apply_row_lock(Bet.query.filter_by(user_id=user.id, race_id=race_id)).first()
    if existing:
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('main.index'))

    odds_at_bet = calculate_bet_odds(participants_by_id, selection_ids, bet_type)
    if odds_at_bet <= 0:
        flash("Impossible de calculer la cote de ce ticket.", "error")
        return redirect(url_for('main.index'))

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
            details=f"Ticket {BET_TYPES[bet_type]['label'].lower()} sur la course #{race_id}: {bet_label}.",
            reference_type='race',
            reference_id=race_id,
        ):
            flash("Pas assez de BitGroins pour valider ce ticket.", "error")
            return redirect(url_for('main.index'))
        db.session.add(bet)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Tu as déjà un ticket sur cette course.", "warning")
        return redirect(url_for('main.index'))

    flash(f"{BET_TYPES[bet_type]['icon']} Ticket {BET_TYPES[bet_type]['label'].lower()} validé sur {bet_label}.", "success")
    return redirect(url_for('main.index'))
