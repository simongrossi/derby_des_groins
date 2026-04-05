from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from exceptions import BusinessRuleError, InsufficientFundsError, ValidationError
from extensions import db, limiter
from models import Pig, User
from services.haras_service import (
    get_haras_listings,
    get_user_haras_eligible_pigs,
    list_pig_in_haras,
    perform_saillie,
    unlist_pig_from_haras,
    MIN_HARAS_PRICE,
)

haras_bp = Blueprint('haras', __name__)


def _get_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])


@haras_bp.route('/haras')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = _get_user()
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    listings = get_haras_listings()
    eligible_pigs = get_user_haras_eligible_pigs(user)
    user_listed = [pig for pig in user.pigs if pig.haras_listed]

    return render_template(
        'haras.html',
        user=user,
        listings=listings,
        eligible_pigs=eligible_pigs,
        user_listed=user_listed,
        min_haras_price=MIN_HARAS_PRICE,
    )


@haras_bp.route('/haras/lister', methods=['POST'])
@limiter.limit("10 per minute")
def lister():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = _get_user()
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    pig_id = request.form.get('pig_id', type=int)
    price = request.form.get('price', type=float)

    pig = db.session.get(Pig, pig_id) if pig_id else None
    if not pig:
        flash("Cochon introuvable.", "error")
        return redirect(url_for('haras.index'))

    try:
        list_pig_in_haras(user, pig, price)
        flash(f"✅ {pig.emoji} {pig.name} est maintenant au Haras pour {price:.0f} BG par saillie !", "success")
    except (BusinessRuleError, ValidationError) as e:
        flash(str(e), "error")

    return redirect(url_for('haras.index'))


@haras_bp.route('/haras/retirer', methods=['POST'])
@limiter.limit("10 per minute")
def retirer():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = _get_user()
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    pig_id = request.form.get('pig_id', type=int)
    pig = db.session.get(Pig, pig_id) if pig_id else None
    if not pig:
        flash("Cochon introuvable.", "error")
        return redirect(url_for('haras.index'))

    try:
        unlist_pig_from_haras(user, pig)
        flash(f"🏠 {pig.emoji} {pig.name} a quitté le Haras.", "success")
    except BusinessRuleError as e:
        flash(str(e), "error")

    return redirect(url_for('haras.index'))


@haras_bp.route('/haras/saillir', methods=['POST'])
@limiter.limit("5 per minute")
def saillir():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = _get_user()
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    stud_pig_id = request.form.get('stud_pig_id', type=int)
    porcelet_name = request.form.get('porcelet_name', '').strip() or None

    stud_pig = db.session.get(Pig, stud_pig_id) if stud_pig_id else None
    if not stud_pig:
        flash("Géniteur introuvable.", "error")
        return redirect(url_for('haras.index'))

    try:
        porcelet = perform_saillie(user, stud_pig, porcelet_name=porcelet_name)
        flash(
            f"🎉 Félicitations ! {porcelet.emoji} {porcelet.name} est né·e ! "
            f"Héritier·e de {stud_pig.name} (Génération {porcelet.generation}).",
            "success",
        )
    except (BusinessRuleError, ValidationError) as e:
        flash(str(e), "error")
    except InsufficientFundsError:
        flash(f"Solde insuffisant pour cette saillie ({stud_pig.haras_price:.0f} BG requis).", "error")

    return redirect(url_for('haras.index'))
