from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from datetime import datetime

from extensions import db
from models import User, Pig, BalanceTransaction
from data import CEREALS, BOURSE_BLOCK_MIN, BOURSE_BLOCK_MAX, BOURSE_GRAIN_LAYOUT
from helpers import (
    get_grain_market, get_all_grain_surcharges, get_bourse_movement_points,
    move_bourse_cursor, is_grain_blocked, update_vitrine,
    get_bourse_cereals, get_bourse_grid_data,
    get_feeding_cost_multiplier, get_user_active_pigs,
)

bourse_bp = Blueprint('bourse', __name__)


@bourse_bp.route('/bourse')
def bourse():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])

    market = get_grain_market()
    movement_points = get_bourse_movement_points(user.id)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    cereals = get_bourse_cereals(market, feeding_multiplier)
    grid = get_bourse_grid_data(market)

    # Cochons actifs du joueur
    active_pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
    for pig in active_pigs:
        pig.update_vitals()

    # Compteur d'achats total de l'utilisateur (pour affichage)
    total_purchases = db.session.query(db.func.count(BalanceTransaction.id)).filter(
        BalanceTransaction.user_id == user.id,
        BalanceTransaction.reason_code == 'feed_purchase',
    ).scalar() or 0

    # Derniers mouvements du marche pour l'historique
    last_movers = []
    if market.last_move_user:
        last_movers.append({
            'action': 'deplacement',
            'user': market.last_move_user.username,
            'at': market.last_move_at,
        })
    if market.vitrine_user:
        last_movers.append({
            'action': 'achat',
            'user': market.vitrine_user.username,
            'grain': CEREALS.get(market.vitrine_grain, {}).get('name', '?'),
            'grain_emoji': CEREALS.get(market.vitrine_grain, {}).get('emoji', '?'),
            'at': market.last_purchase_at,
        })

    return render_template(
        'bourse.html',
        user=user,
        active_page='bourse',
        market=market,
        movement_points=movement_points,
        feeding_multiplier=feeding_multiplier,
        cereals=cereals,
        grid=grid,
        active_pigs=active_pigs,
        total_purchases=total_purchases,
        last_movers=last_movers,
        block_min=BOURSE_BLOCK_MIN,
        block_max=BOURSE_BLOCK_MAX,
    )


@bourse_bp.route('/bourse/move', methods=['POST'])
def bourse_move():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])

    dx = request.form.get('dx', 0, type=int)
    dy = request.form.get('dy', 0, type=int)

    if dx == 0 and dy == 0:
        return redirect(url_for('bourse.bourse'))

    market = get_grain_market()
    max_pts = get_bourse_movement_points(user.id)

    points_used = move_bourse_cursor(market, dx, dy, max_pts)
    if points_used > 0:
        market.last_move_user_id = user.id
        market.last_move_at = datetime.utcnow()
        db.session.commit()
        direction = []
        if dx > 0: direction.append(f'{dx} vers la droite')
        elif dx < 0: direction.append(f'{abs(dx)} vers la gauche')
        if dy > 0: direction.append(f'{dy} vers le bas')
        elif dy < 0: direction.append(f'{abs(dy)} vers le haut')
        flash(f"Bloc deplace de {', '.join(direction)} ! ({points_used} point(s) utilise(s))", "success")
    else:
        flash("Deplacement impossible (bord de grille ou points insuffisants).", "warning")

    return redirect(url_for('bourse.bourse'))


@bourse_bp.route('/bourse/buy', methods=['POST'])
def bourse_buy():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])

    cereal_key = request.form.get('cereal')
    pig_id = request.form.get('pig_id', type=int)

    # Verifier que ce grain fait partie du bloc 3x3
    if cereal_key not in [ck for ck in BOURSE_GRAIN_LAYOUT.values() if ck]:
        flash("Cereale inconnue ou pas dans le bloc.", "error")
        return redirect(url_for('bourse.bourse'))

    pig = Pig.query.get(pig_id)
    if not pig or pig.user_id != user.id or not pig.is_alive:
        flash("Cochon introuvable !", "error")
        return redirect(url_for('bourse.bourse'))

    pig.update_vitals()

    if pig.hunger >= 95:
        flash("Ton cochon n'a plus faim !", "warning")
        return redirect(url_for('bourse.bourse'))

    market = get_grain_market()

    # Verifier le blocage vitrine
    if is_grain_blocked(cereal_key, market):
        blocked_name = CEREALS[cereal_key]['name']
        flash(f"{blocked_name} est en vitrine ! Achete autre chose pour debloquer.", "warning")
        return redirect(url_for('bourse.bourse'))

    # Calculer le prix effectif avec surcout individuel
    surcharges = get_all_grain_surcharges(market)
    surcharge = surcharges.get(cereal_key, 1.0)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    base_cost = CEREALS[cereal_key]['cost']
    effective_cost = round(base_cost * surcharge * feeding_multiplier, 2)

    # Debiter
    if not user.pay(
        effective_cost,
        reason_code='feed_purchase',
        reason_label='Achat Bourse aux Grains',
        details=(
            f"{CEREALS[cereal_key]['name']} pour {pig.name}. "
            f"Surcout Bourse x{surcharge:.2f}, "
            f"Pression x{feeding_multiplier:.2f}."
        ),
        reference_type='pig',
        reference_id=pig.id,
    ):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('bourse.bourse'))

    # Appliquer les effets
    pig.feed(CEREALS[cereal_key])

    # Mettre a jour la vitrine
    update_vitrine(market, cereal_key, user.id)

    db.session.commit()

    emoji = CEREALS[cereal_key]['emoji']
    name = CEREALS[cereal_key]['name']
    flash(
        f"{emoji} {name} achete a la Bourse ! "
        f"Prix: {effective_cost:.0f} 🪙 (surcout x{surcharge:.2f})",
        "success"
    )
    return redirect(url_for('bourse.bourse'))
