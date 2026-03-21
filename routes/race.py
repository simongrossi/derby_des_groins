from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta

from extensions import db
from models import User, Pig, Race, Participant, Bet, CoursePlan
from data import BET_TYPES, WEEKLY_RACE_QUOTA, WEEKLY_BACON_TICKETS
from helpers import ensure_next_race, get_user_active_pigs, apply_row_lock
from services.pig_service import calculate_pig_power, get_weight_profile
from services.race_service import (
    count_pig_weekly_course_commitments, build_course_schedule,
    populate_race_participants, get_user_weekly_bet_count,
    normalize_bet_type, parse_selection_ids, serialize_selection_ids,
    format_bet_label, calculate_bet_odds,
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
    pig = Pig.query.filter_by(id=pig_id, user_id=user.id, is_alive=True).first()
    if not pig:
        flash("Cochon introuvable pour cette planification.", "error")
        return redirect(url_for('race.courses'))

    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_raw).replace(microsecond=0)
    except ValueError:
        flash("Creneau de course invalide.", "error")
        return redirect(url_for('race.courses'))

    if scheduled_at <= datetime.now() + timedelta(seconds=30):
        flash("Cette course est trop proche pour modifier les inscriptions.", "warning")
        return redirect(url_for('race.courses'))

    open_race = Race.query.filter_by(scheduled_at=scheduled_at, status='open').first()
    if open_race and Bet.query.filter_by(race_id=open_race.id).count() > 0:
        flash("Cette course est deja verrouillee par des paris. Plus de modification possible.", "warning")
        return redirect(url_for('race.courses'))
    if open_race and (pig.is_injured or pig.energy <= 20 or pig.hunger <= 20):
        flash(f"{pig.name} n'est pas en etat de rejoindre la course ouverte du moment.", "warning")
        return redirect(url_for('race.courses'))

    already_participant = False
    if open_race:
        already_participant = Participant.query.filter_by(race_id=open_race.id, pig_id=pig.id).first() is not None

    existing_plan = CoursePlan.query.filter_by(user_id=user.id, pig_id=pig.id, scheduled_at=scheduled_at).first()
    if existing_plan:
        db.session.delete(existing_plan)
        if open_race:
            populate_race_participants(open_race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=False)
        db.session.commit()
        flash(f"📅 {pig.name} est retire du planning du {scheduled_at.strftime('%d/%m %H:%M')}.", "success")
        return redirect(url_for('race.courses'))

    if already_participant:
        flash(f"{pig.name} est deja partant sur cette course ouverte.", "warning")
        return redirect(url_for('race.courses'))

    if count_pig_weekly_course_commitments(pig.id, scheduled_at) >= WEEKLY_RACE_QUOTA:
        flash(f"{pig.name} a deja atteint son quota hebdomadaire de {WEEKLY_RACE_QUOTA} courses.", "warning")
        return redirect(url_for('race.courses'))

    strategy = request.form.get('strategy', 50, type=int)

    db.session.add(CoursePlan(user_id=user.id, pig_id=pig.id, scheduled_at=scheduled_at, strategy=strategy))
    db.session.flush()

    if open_race:
        populate_race_participants(open_race, respect_course_plans=True, allow_rebuild_if_bets=False, commit=False)

    db.session.commit()
    flash(f"📅 {pig.name} est maintenant planifie pour la course du {scheduled_at.strftime('%d/%m %H:%M')}.", "success")
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
