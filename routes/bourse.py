from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify
from datetime import datetime, timedelta

from extensions import db
from models import User, Pig, BalanceTransaction
from models import User, Pig, BalanceTransaction, MarketHistory
from data import BOURSE_BLOCK_MIN, BOURSE_BLOCK_MAX, BOURSE_GRAIN_LAYOUT
from helpers import get_feeding_cost_multiplier, get_user_active_pigs, get_cereals_dict
from services.market_service import (
    get_grain_market, get_all_grain_surcharges, get_bourse_movement_points,
    move_bourse_cursor, is_grain_blocked, update_vitrine,
    get_bourse_cereals, get_bourse_grid_data,
    log_market_state,
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
        _cereals = get_cereals_dict()
        last_movers.append({
            'action': 'achat',
            'user': market.vitrine_user.username,
            'grain': _cereals.get(market.vitrine_grain, {}).get('name', '?'),
            'grain_emoji': _cereals.get(market.vitrine_grain, {}).get('emoji', '?'),
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
    cereals = get_cereals_dict()

    # Verifier le blocage vitrine
    if is_grain_blocked(cereal_key, market):
        blocked_name = cereals[cereal_key]['name']
        flash(f"{blocked_name} est en vitrine ! Achete autre chose pour debloquer.", "warning")
        return redirect(url_for('bourse.bourse'))

    # Calculer le prix effectif avec surcout individuel
    surcharges = get_all_grain_surcharges(market)
    surcharge = surcharges.get(cereal_key, 1.0)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    base_cost = cereals[cereal_key]['cost']
    effective_cost = round(base_cost * surcharge * feeding_multiplier, 2)

    # Debiter
    if not user.pay(
        effective_cost,
        reason_code='feed_purchase',
        reason_label='Achat Bourse aux Grains',
        details=(
            f"{cereals[cereal_key]['name']} pour {pig.name}. "
            f"Surcout Bourse x{surcharge:.2f}, "
            f"Pression x{feeding_multiplier:.2f}."
        ),
        reference_type='pig',
        reference_id=pig.id,
    ):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('bourse.bourse'))

    # Appliquer les effets
    pig.feed(cereals[cereal_key])

    # Mettre a jour la vitrine
    update_vitrine(market, cereal_key, user.id)

    db.session.commit()

    emoji = cereals[cereal_key]['emoji']
    name = cereals[cereal_key]['name']
    flash(
        f"{emoji} {name} achete a la Bourse ! "
        f"Prix: {effective_cost:.0f} 🪙 (surcout x{surcharge:.2f})",
        "success"
    )
    return redirect(url_for('bourse.bourse'))


@bourse_bp.route('/bourse/history')
def bourse_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Non connecté'}), 401

    days = request.args.get('days', 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    # Récupérer l'historique
    history_rows = MarketHistory.query.filter(
        MarketHistory.recorded_at >= since
    ).order_by(MarketHistory.recorded_at.asc()).all()

    from data import CEREALS
    
    # Organiser par céréale
    data = {}
    labels = []
    
    # On veut des labels temporels uniques pour l'axe X
    # Mais comme on logue tout d'un coup, on peut grouper par "recorded_at"
    timestamps = sorted(list(set(h.recorded_at.isoformat() for h in history_rows)))
    
    for key in CEREALS.keys():
        data[key] = {
            'label': CEREALS[key]['name'],
            'emoji': CEREALS[key]['emoji'],
            'prices': [],
            'surcharges': []
        }
        
    # On remplit les trous si nécessaire (même si normalement on logue tout le bloc)
    for ts in timestamps:
        rows_at_ts = [h for h in history_rows if h.recorded_at.isoformat() == ts]
        for key in CEREALS.keys():
            match = next((h for h in rows_at_ts if h.cereal_key == key), None)
            if match:
                data[key]['prices'].append(match.price)
                data[key]['surcharges'].append(match.surcharge)
            else:
                # Valeur par défaut ou répétition de la dernière
                prev_price = data[key]['prices'][-1] if data[key]['prices'] else CEREALS[key]['cost']
                prev_sur = data[key]['surcharges'][-1] if data[key]['surcharges'] else 1.0
                data[key]['prices'].append(prev_price)
                data[key]['surcharges'].append(prev_sur)

    return jsonify({
        'timestamps': timestamps,
        'datasets': data
    })
