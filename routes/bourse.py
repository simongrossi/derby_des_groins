from flask import Blueprint, render_template, redirect, url_for, session, flash, request, jsonify
from datetime import datetime, timedelta

from extensions import db, limiter
from exceptions import BusinessRuleError
from models import User, BalanceTransaction, MarketHistory
from data import BOURSE_BLOCK_MIN, BOURSE_BLOCK_MAX
from helpers import get_feeding_cost_multiplier, get_cereals_dict
from services.market_service import (
    get_grain_market, get_all_grain_surcharges, get_bourse_movement_points,
    get_bourse_cereals, get_bourse_grid_data, move_bourse_for_user,
)
from services.pig_service import buy_cereal_from_bourse_for_user

bourse_bp = Blueprint('bourse', __name__)


@bourse_bp.route('/bourse')
def bourse():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    market = get_grain_market()
    movement_points = get_bourse_movement_points(user.id)
    feeding_multiplier = get_feeding_cost_multiplier(user)
    cereals = get_bourse_cereals(market, feeding_multiplier)
    grid = get_bourse_grid_data(market)

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
        total_purchases=total_purchases,
        last_movers=last_movers,
        block_min=BOURSE_BLOCK_MIN,
        block_max=BOURSE_BLOCK_MAX,
    )


@bourse_bp.route('/bourse/move', methods=['POST'])
@limiter.limit("20 per minute")
def bourse_move():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = move_bourse_for_user(
            session['user_id'],
            request.form.get('dx', 0, type=int),
            request.form.get('dy', 0, type=int),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")

    return redirect(url_for('bourse.bourse'))


@bourse_bp.route('/bourse/buy', methods=['POST'])
@limiter.limit("10 per minute")
def bourse_buy():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('auth.login'))

    try:
        result = buy_cereal_from_bourse_for_user(user.id, request.form.get('cereal'))
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
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

    cereals = get_cereals_dict()

    # Si l'historique est vide, on renvoie au moins l'etat courant pour eviter
    # d'afficher des cartes entierement vides.
    if not history_rows:
        market = get_grain_market()
        surcharges = get_all_grain_surcharges(market)
        snapshot_at = datetime.utcnow().isoformat()
        datasets = {}
        for key, cereal in cereals.items():
            base_cost = float(cereal.get('cost', 0) or 0)
            surcharge = float(surcharges.get(key, 1.0) or 1.0)
            datasets[key] = {
                'label': cereal.get('name', key),
                'emoji': cereal.get('emoji', '🌾'),
                'prices': [round(base_cost * surcharge, 2)],
                'surcharges': [round(surcharge, 2)],
            }
        return jsonify({
            'timestamps': [snapshot_at],
            'datasets': datasets,
            'source': 'snapshot',
        })

    # Organiser par céréale
    data = {}
    labels = []

    # On veut des labels temporels uniques pour l'axe X
    # Mais comme on logue tout d'un coup, on peut grouper par "recorded_at"
    timestamps = sorted(list(set(h.recorded_at.isoformat() for h in history_rows)))

    cereal_keys = sorted(set(cereals.keys()) | {h.cereal_key for h in history_rows})

    for key in cereal_keys:
        cereal = cereals.get(key, {})
        data[key] = {
            'label': cereal.get('name', key),
            'emoji': cereal.get('emoji', '🌾'),
            'prices': [],
            'surcharges': []
        }

    # On remplit les trous si nécessaire (même si normalement on logue tout le bloc)
    for ts in timestamps:
        rows_at_ts = [h for h in history_rows if h.recorded_at.isoformat() == ts]
        for key in cereal_keys:
            match = next((h for h in rows_at_ts if h.cereal_key == key), None)
            if match:
                data[key]['prices'].append(match.price)
                data[key]['surcharges'].append(match.surcharge)
            else:
                # Valeur par défaut ou répétition de la dernière
                prev_price = data[key]['prices'][-1] if data[key]['prices'] else float(cereals.get(key, {}).get('cost', 0) or 0)
                prev_sur = data[key]['surcharges'][-1] if data[key]['surcharges'] else 1.0
                data[key]['prices'].append(prev_price)
                data[key]['surcharges'].append(prev_sur)

    return jsonify({
        'timestamps': timestamps,
        'datasets': data,
        'source': 'history',
    })
