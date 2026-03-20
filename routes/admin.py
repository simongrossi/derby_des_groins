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
    next_race = Race.query.filter(Race.status == 'open').order_by(Race.scheduled_at).first()
    recent_races = Race.query.filter_by(status='finished').order_by(Race.finished_at.desc()).limit(10).all()

    return render_template('admin.html',
        user=user, users=users, pigs=pigs,
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
