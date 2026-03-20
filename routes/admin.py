from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime

from extensions import db
from models import User, Race, Pig
from data import JOURS_FR
from helpers import (
    get_config, set_config, populate_race_participants, run_race_if_needed,
)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        flash("Accès réservé aux administrateurs.", "error")
        return redirect(url_for('main.index'))

    users = User.query.order_by(User.username.asc()).all()
    pigs = Pig.query.order_by(Pig.is_alive.desc(), Pig.name.asc()).all()
    upcoming_races = Race.query.filter(Race.status.in_(['upcoming', 'open'])).order_by(Race.scheduled_at).limit(20).all()
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(10).all()

    return render_template('admin.html',
        user=user, users=users, pigs=pigs, upcoming_races=upcoming_races,
        next_race=next_race, recent_races=recent_races,
        config={
            'race_hour': get_config('race_hour', '14'),
            'race_minute': get_config('race_minute', '00'),
            'market_day': get_config('market_day', '4'),
            'market_hour': get_config('market_hour', '13'),
            'market_minute': get_config('market_minute', '45'),
            'market_duration': get_config('market_duration', '120'),
            'min_real_participants': get_config('min_real_participants', '2'),
            'empty_race_mode': get_config('empty_race_mode', 'fill'),
        },
        jours=JOURS_FR
    )


@admin_bp.route('/admin/save', methods=['POST'])
def admin_save():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    keys = [
        'race_hour', 'race_minute', 'market_day', 'market_hour',
        'market_minute', 'market_duration', 'min_real_participants', 'empty_race_mode'
    ]
    for key in keys:
        val = request.form.get(key)
        if val is not None:
            set_config(key, val)

    flash("Configuration sauvegardée !", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/force-race', methods=['POST'])
def admin_force_race():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    race = Race(scheduled_at=datetime.now(), status='open')
    db.session.add(race)
    db.session.flush()
    populate_race_participants(race, respect_course_plans=False, allow_rebuild_if_bets=True, commit=True)
    run_race_if_needed()
    flash("🏁 Course forcée ! Résultats disponibles.", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/pigs/<int:pig_id>/toggle-life', methods=['POST'])
def admin_toggle_pig_life(pig_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    pig = Pig.query.get_or_404(pig_id)
    pig.is_alive = not pig.is_alive
    if pig.is_alive:
        pig.death_date = None
        pig.death_cause = None
        pig.charcuterie_type = None
        pig.charcuterie_emoji = None
        pig.epitaph = None
    else:
        pig.death_date = datetime.utcnow()
        pig.death_cause = pig.death_cause or 'admin'
    db.session.commit()
    flash(f"Statut mis à jour pour {pig.name}.", 'success')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/races/<int:race_id>/cancel', methods=['POST'])
def admin_cancel_race(race_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    race = Race.query.get_or_404(race_id)
    if race.status == 'finished':
        flash("Impossible d'annuler une course terminée.", "error")
        return redirect(url_for('admin.admin'))

    # Refund bets if any
    for bet in race.bets:
        if bet.status == 'pending':
            from helpers import credit_user_balance
            credit_user_balance(bet.user_id, bet.amount, reason_code='bet_refund', reason_label='Remboursement (Course annulée)', reference_type='race', reference_id=race.id)
            bet.status = 'cancelled'

    db.session.delete(race)
    db.session.commit()
    flash(f"Course #{race_id} annulée et paris remboursés.", "success")
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/events/trigger', methods=['POST'])
def admin_trigger_event():
    if 'user_id' not in session:
        return redirect(url_for('auth.login', next=request.path))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('main.index'))

    event_type = request.form.get('event_type')
    if event_type == 'food_drop':
        all_pigs = Pig.query.filter_by(is_alive=True).all()
        for p in all_pigs:
            p.energy = min(100, (p.energy or 0) + 30)
            p.hunger = min(100, (p.hunger or 0) + 30)
        db.session.commit()
        flash("📦 Distribution de nourriture effectuée ! +30 Énergie/Faim pour tous les groins.", "success")
    elif event_type == 'vet_visit':
        injured_pigs = Pig.query.filter_by(is_alive=True, is_injured=True).all()
        for p in injured_pigs:
            p.is_injured = False
            p.injured_until = None
        db.session.commit()
        flash(f"🏥 Visite vétérinaire ! {len(injured_pigs)} groins soignés.", "success")
    elif event_type == 'bonus_bg':
        from helpers import credit_user_balance
        all_users = User.query.all()
        for u in all_users:
            credit_user_balance(u.id, 50.0, reason_code='admin_gift', reason_label='Cadeau Admin', reference_type='user', reference_id=user.id)
        db.session.commit()
        flash("💰 Bonus de 50 🪙 BitGroins accordé à tous les joueurs !", "success")
    else:
        flash("Événement inconnu.", "error")

    return redirect(url_for('admin.admin'))
