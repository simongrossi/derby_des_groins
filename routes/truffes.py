from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from helpers.config import get_config
from models import User
from services.finance_service import credit_user_balance, debit_user_balance
from services.gameplay_settings_service import get_minigame_settings

truffes_bp = Blueprint('truffes', __name__)


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_truffe_config():
    try:
        limit = int(get_config('truffe_daily_limit', '1'))
        replay_cost = int(get_config('truffe_replay_cost', '2'))
        return limit, replay_cost
    except (ValueError, TypeError):
        return 1, 2


def _sync_truffe_daily_counter(user):
    """Reset the daily counter when the stored play date is from a previous day."""
    today = date.today()
    if user.last_truffe_at and user.last_truffe_at.date() < today and user.truffe_plays_today:
        user.truffe_plays_today = 0
        db.session.commit()
        db.session.refresh(user)


def _get_remaining_free_plays(user, limit=None):
    applied_limit = limit if limit is not None else _get_truffe_config()[0]
    _sync_truffe_daily_counter(user)
    return max(0, applied_limit - (user.truffe_plays_today or 0))


def _already_played_today(user):
    """Return whether the user has exhausted today's free plays."""
    limit, _ = _get_truffe_config()
    remaining = _get_remaining_free_plays(user, limit=limit)
    return remaining <= 0


@truffes_bp.route('/truffes')
def truffes():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = db.session.get(User, user_id)
    already_played = _already_played_today(user)
    limit, replay_cost = _get_truffe_config()
    remaining = _get_remaining_free_plays(user, limit=limit)
    settings = get_minigame_settings()
    
    return render_template(
        'truffes.html',
        user=user,
        active_page='truffes',
        reward=settings.truffe_reward,
        max_clicks=settings.truffe_max_clicks,
        grid_size=settings.truffe_grid_size,
        already_played=already_played,
        limit=limit,
        replay_cost=replay_cost,
        remaining=remaining,
    )


@truffes_bp.route('/truffes/play', methods=['POST'])
@limiter.limit("10 per minute")
def truffes_play():
    """Called when the user starts a game (first click). Increments the daily counter."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = db.session.get(User, user_id)
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
            
            debit_ok = debit_user_balance(
                user.id,
                replay_cost,
                reason_code='truffe_replay',
                reason_label='Rejouer aux Truffes',
                details=f'Rejeu payant de la chasse aux truffes ({replay_cost} 🪙).',
                reference_type='user',
                reference_id=user.id
            )
            if not debit_ok:
                db.session.rollback()
                return jsonify({'ok': False, 'error': 'Fonds insuffisants'}), 400
        else:
            return jsonify({'ok': False, 'error': 'Limite quotidienne atteinte'}), 429

    user.last_truffe_at = _utcnow_naive()
    user.truffe_plays_today += 1
    db.session.commit()
    db.session.refresh(user)
    
    return jsonify({
        'ok': True,
        'new_balance': round(user.balance or 0.0, 2),
        'remaining_free_plays': _get_remaining_free_plays(user, limit=limit),
    })


@truffes_bp.route('/truffes/win', methods=['POST'])
@limiter.limit("10 per minute")
def truffes_win():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    payload = request.get_json(silent=True) or {}
    clicks = payload.get('clicks', '?')
    settings = get_minigame_settings()

    credit_user_balance(
        user.id,
        settings.truffe_reward,
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
        'reward': settings.truffe_reward,
        'new_balance': round(user.balance or 0.0, 2),
    })
