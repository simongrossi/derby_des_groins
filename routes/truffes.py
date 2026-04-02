from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import User
from services.finance_service import credit_user_balance, debit_user_balance

truffes_bp = Blueprint('truffes', __name__)

TRUFFE_REWARD = 20
MAX_CLICKS = 7
GRID_SIZE = 20


def _get_truffe_config():
    from helpers import get_config
    try:
        limit = int(get_config('truffe_daily_limit', '1'))
        replay_cost = int(get_config('truffe_replay_cost', '2'))
        return limit, replay_cost
    except (ValueError, TypeError):
        return 1, 2


def _already_played_today(user):
    """Note: This function now also resets the daily counter if the day has changed."""
    if getattr(user, 'is_admin', False):
        return False
    if not user.last_truffe_at:
        return False
    
    limit, _ = _get_truffe_config()
    today = date.today()
    if user.last_truffe_at.date() < today:
        user.truffe_plays_today = 0
        db.session.commit()
    
    return user.truffe_plays_today >= limit


@truffes_bp.route('/truffes')
def truffes():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    already_played = _already_played_today(user)
    limit, replay_cost = _get_truffe_config()
    
    return render_template(
        'truffes.html',
        user=user,
        active_page='truffes',
        reward=TRUFFE_REWARD,
        max_clicks=MAX_CLICKS,
        grid_size=GRID_SIZE,
        already_played=already_played,
        limit=limit,
        replay_cost=replay_cost,
        remaining=max(0, limit - user.truffe_plays_today) if not getattr(user, 'is_admin', False) else limit
    )


@truffes_bp.route('/truffes/play', methods=['POST'])
@limiter.limit("10 per minute")
def truffes_play():
    """Called when the user starts a game (first click). Increments the daily counter."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    is_replay = payload.get('is_replay', False)
    limit, replay_cost = _get_truffe_config()

    if _already_played_today(user):
        if is_replay:
            # Check balance and debit
            if (user.balance or 0) < replay_cost:
                return jsonify({'ok': False, 'error': 'Fonds insuffisants'}), 400
            
            debit_user_balance(
                user.id,
                replay_cost,
                reason_code='truffe_replay',
                reason_label='Rejouer aux Truffes',
                details=f'Rejeu payant de la chasse aux truffes ({replay_cost} 🪙).',
                reference_type='user',
                reference_id=user.id
            )
        else:
            return jsonify({'ok': False, 'error': 'Limite quotidienne atteinte'}), 429

    user.last_truffe_at = datetime.utcnow()
    user.truffe_plays_today += 1
    db.session.commit()
    db.session.refresh(user)
    
    return jsonify({
        'ok': True,
        'new_balance': round(user.balance or 0.0, 2)
    })


@truffes_bp.route('/truffes/win', methods=['POST'])
@limiter.limit("10 per minute")
def truffes_win():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    clicks = payload.get('clicks', '?')

    credit_user_balance(
        user.id,
        TRUFFE_REWARD,
        reason_code='truffe_found',
        reason_label='Truffe trouvée',
        details=f'Truffe dénichée en {clicks} clic(s). Récompense porcine créditée.',
        reference_type='user',
        reference_id=user.id,
    )
    db.session.commit()
    db.session.refresh(user)

    return jsonify({
        'ok': True,
        'reward': TRUFFE_REWARD,
        'new_balance': round(user.balance or 0.0, 2),
    })
