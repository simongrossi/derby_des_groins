from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db
from models import User
from services.finance_service import credit_user_balance

truffes_bp = Blueprint('truffes', __name__)

TRUFFE_REWARD = 20
MAX_CLICKS = 7
GRID_SIZE = 20


@truffes_bp.route('/truffes')
def truffes():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user = User.query.get(user_id)
    return render_template(
        'truffes.html',
        user=user,
        active_page='truffes',
        reward=TRUFFE_REWARD,
        max_clicks=MAX_CLICKS,
        grid_size=GRID_SIZE,
    )


@truffes_bp.route('/truffes/win', methods=['POST'])
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
