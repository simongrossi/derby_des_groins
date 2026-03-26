from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import Trophy, User
from services.finance_service import credit_user_balance

agenda_bp = Blueprint('agenda', __name__)

AGENDA_REWARD = 50
REQUIRED_CATCHES = 5
GAME_DURATION = 30


def _already_played_today(user):
    """Return True if the user already played the agenda game today."""
    if not user.last_agenda_at:
        return False
    return user.last_agenda_at.date() >= date.today()


@agenda_bp.route('/agenda')
def agenda():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    already_played = _already_played_today(user)
    return render_template(
        'agenda.html',
        user=user,
        active_page='agenda',
        reward=AGENDA_REWARD,
        required_catches=REQUIRED_CATCHES,
        game_duration=GAME_DURATION,
        already_played=already_played,
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
        return jsonify({'ok': False, 'error': 'Déjà joué aujourd\'hui'}), 429

    user.last_agenda_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


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
        reason_label='COMOP atteint',
        details=f'{catches} COMOP(s) attrapé(s) en 30s. Dédommagement psychologique crédité.',
        reference_type='user',
        reference_id=user.id,
    )

    Trophy.award(
        user_id=user.id,
        code='legende_du_comop',
        label='Ceinture Noire de Porc-Look',
        emoji='🐷',
        description='A survécu au Chef de Porc-jet et attrapé 5 COMOPs fantômes en 30 secondes.',
    )

    db.session.commit()
    db.session.refresh(user)

    return jsonify({
        'ok': True,
        'reward': AGENDA_REWARD,
        'new_balance': round(user.balance or 0.0, 2),
    })
