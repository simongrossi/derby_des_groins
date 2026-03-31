from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import Trophy, User
from services.finance_service import credit_user_balance

agenda_bp = Blueprint('agenda', __name__)

AGENDA_REWARD = 50
REQUIRED_CATCHES = 5
GAME_DURATION = 30
MAX_PLAYS_PER_DAY = 2


def _plays_remaining(user):
    """Return the number of plays left today (resets daily). Admins: unlimited."""
    if getattr(user, 'is_admin', False):
        return MAX_PLAYS_PER_DAY  # always show full for admins
    if not user.last_agenda_at or user.last_agenda_at.date() < date.today():
        return MAX_PLAYS_PER_DAY
    return max(0, MAX_PLAYS_PER_DAY - (user.agenda_plays_today or 0))


def _already_played_today(user):
    """Return True if the user has exhausted today's plays. Admins: never blocked."""
    if getattr(user, 'is_admin', False):
        return False
    return _plays_remaining(user) <= 0


@agenda_bp.route('/agenda')
def agenda():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    already_played = _already_played_today(user)
    remaining = _plays_remaining(user)
    return render_template(
        'agenda.html',
        user=user,
        active_page='agenda',
        reward=AGENDA_REWARD,
        required_catches=REQUIRED_CATCHES,
        game_duration=GAME_DURATION,
        already_played=already_played,
        plays_remaining=remaining,
        max_plays=MAX_PLAYS_PER_DAY,
    )


@agenda_bp.route('/agenda/play', methods=['POST'])
@limiter.limit("10 per minute")
def agenda_play():
    """Called when the user starts a game. Marks the day as used."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    if _already_played_today(user):
        return jsonify({'ok': False, 'error': 'Tu as déjà utilisé tes 2 parties du jour !'}), 429

    # Reset counter if new day
    if not user.last_agenda_at or user.last_agenda_at.date() < date.today():
        user.agenda_plays_today = 1
    else:
        user.agenda_plays_today = (user.agenda_plays_today or 0) + 1

    user.last_agenda_at = datetime.utcnow()
    db.session.commit()
    remaining = _plays_remaining(user)
    return jsonify({'ok': True, 'remaining': remaining})


@agenda_bp.route('/agenda/win', methods=['POST'])
@limiter.limit("10 per minute")
def agenda_win():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    catches = payload.get('catches', '?')

    credit_user_balance(
        user.id,
        AGENDA_REWARD,
        reason_code='agenda_win',
        reason_label='GROSMOP atteint',
        details=f'{catches} GROSMOP(s) attrapé(s) en 30s. Dédommagement pour illusion de management.',
        reference_type='user',
        reference_id=user.id,
    )

    Trophy.award(
        user_id=user.id,
        code='legende_du_grosmop',
        label='Ceinture Noire de Porc-Look',
        emoji='🐷',
        description='A survécu au Chef de Porc-jet et attrapé 5 GROSMOPs fantômes en 30 secondes.',
    )

    db.session.commit()
    db.session.refresh(user)

    return jsonify({
        'ok': True,
        'reward': AGENDA_REWARD,
        'new_balance': round(user.balance or 0.0, 2),
    })
