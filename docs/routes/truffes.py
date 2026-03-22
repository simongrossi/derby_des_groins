from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from models import User
from helpers import credit_user_balance
from extensions import db

truffes_bp = Blueprint('truffes', __name__)

TRUFFE_REWARD = 20  # BitGroins gagnés en cas de victoire


@truffes_bp.route('/truffes')
def truffes():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    return render_template(
        'truffes.html',
        user=user,
        active_page='truffes',
        reward=TRUFFE_REWARD,
    )


@truffes_bp.route('/truffes/win', methods=['POST'])
def truffes_win():
    """
    Hook appelé par le mini-jeu JS en cas de victoire.
    Crédite le joueur et retourne le nouveau solde en JSON.
    """
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'Non connecté'}), 401

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'ok': False, 'error': 'Utilisateur introuvable'}), 404

    clics = request.json.get('clics', '?')

    credit_user_balance(
        user.id,
        TRUFFE_REWARD,
        reason_code='truffe_found',
        reason_label='🍄 Truffe Trouvée !',
        details=f"Truffe dénichée en {clics} clic(s). Récompense porcine créditée.",
        reference_type='user',
        reference_id=user.id,
    )
    db.session.commit()

    # Recharger le solde depuis la BDD
    db.session.refresh(user)
    return jsonify({'ok': True, 'reward': TRUFFE_REWARD, 'new_balance': round(user.balance, 2)})
