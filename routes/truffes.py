from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import User
from services.finance_service import credit_user_balance

truffes_bp = Blueprint('truffes', __name__)

TRUFFE_REWARD = 20
MAX_CLICKS = 7
GRID_SIZE = 20


def _already_played_today(user):
    """Return True if the user already played the truffle hunt today. Admins: never blocked."""
    if getattr(user, 'is_admin', False):
        return False
    if not user.last_truffe_at:
        return False
    return user.last_truffe_at.date() >= date.today()


@truffes_bp.route('/truffes')
def truffes():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    already_played = _already_played_today(user)
    return render_template(
        'truffes.html',
        user=user,
        active_page='truffes',
        reward=TRUFFE_REWARD,
        max_clicks=MAX_CLICKS,
        grid_size=GRID_SIZE,
        already_played=already_played,
    )


@truffes_bp.route('/truffes/play', methods=['POST'])
@limiter.limit("10 per minute")
def truffes_play():
    """Called when the user starts a game (first click). Marks the day as used."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    if _already_played_today(user):
        return jsonify({'ok': False, 'error': 'Déjà joué aujourd\'hui'}), 429

    user.last_truffe_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})


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
