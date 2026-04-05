from flask import Blueprint, render_template, redirect, url_for, session

from models import User

place_financiere_bp = Blueprint('place_financiere', __name__)


@place_financiere_bp.route('/place-financiere')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    from services.place_financiere_service import get_place_financiere_data
    data = get_place_financiere_data()
    return render_template('place_financiere.html', user=user, **data)
