from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import update
from datetime import datetime

from extensions import db
from models import User, Pig, Auction
from data import RARITIES, PIG_ORIGINS, JOURS_FR, DEFAULT_PIG_WEIGHT_KG
from helpers import (
    get_market_unlock_progress, get_market_lock_reason,
    is_market_open, get_next_market_time, get_market_close_time,
    get_prix_moyen_groin, apply_row_lock,
)
from services.game_settings_service import get_game_settings

market_bp = Blueprint('market', __name__)


@market_bp.route('/marche')
def marche():
    active_auctions = Auction.query.filter_by(status='active').order_by(Auction.ends_at).all()
    recent_sold = Auction.query.filter_by(status='sold').order_by(Auction.ends_at.desc()).limit(5).all()

    user = None
    pigs = []
    market_access = False
    market_lock_reason = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            pigs = Pig.query.filter_by(user_id=user.id, is_alive=True).all()
            market_access = get_market_unlock_progress(user)[0]
            market_lock_reason = get_market_lock_reason(user)

    settings = get_game_settings()
    market_open = is_market_open()
    next_market = get_next_market_time()
    market_day_name = JOURS_FR[settings.market_day]
    market_time = f"{settings.market_hour}h{settings.market_minute:02d}"
    prix_groin = get_prix_moyen_groin()

    return render_template('marche.html',
        user=user, pigs=pigs,
        auctions=active_auctions, recent_sold=recent_sold,
        rarities=RARITIES, now=datetime.utcnow(),
        market_open=market_open, next_market=next_market,
        market_day_name=market_day_name, market_time=market_time,
        prix_groin=prix_groin, origins=PIG_ORIGINS,
        market_access=market_access, market_lock_reason=market_lock_reason
    )


@market_bp.route('/bid', methods=['POST'])
def bid():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not get_market_unlock_progress(user)[0]:
        flash(get_market_lock_reason(user), "warning")
        return redirect(url_for('market.marche'))
    auction_id = request.form.get('auction_id', type=int)
    bid_amount = request.form.get('bid_amount', type=float)
    auction = apply_row_lock(Auction.query.filter_by(id=auction_id)).first()
    if not auction or auction.status != 'active':
        flash("Cette enchère n'est plus disponible !", "error")
        return redirect(url_for('market.marche'))
    if datetime.utcnow() >= auction.ends_at:
        flash("L'enchère est terminée !", "error")
        return redirect(url_for('market.marche'))
    min_bid = auction.current_bid + 5 if auction.current_bid > 0 else auction.starting_price
    if not bid_amount or bid_amount < min_bid:
        flash(f"Enchère minimum : {min_bid:.0f} 🪙 !", "error")
        return redirect(url_for('market.marche'))

    if not user.pay(
        bid_amount,
        reason_code='auction_bid',
        reason_label='Mise bloquee en enchere',
        details=f"Enchere sur {auction.pig_name}.",
        reference_type='auction',
        reference_id=auction.id,
    ):
        flash("Pas assez de BitGroins !", "error")
        return redirect(url_for('market.marche'))

    previous_bidder_id = auction.bidder_id
    previous_bid_amount = round(auction.current_bid or 0.0, 2)
    auction_conditions = [
        Auction.id == auction.id,
        Auction.status == 'active',
        Auction.ends_at > datetime.utcnow(),
        Auction.current_bid == previous_bid_amount,
    ]
    if previous_bidder_id is None:
        auction_conditions.append(Auction.bidder_id.is_(None))
    else:
        auction_conditions.append(Auction.bidder_id == previous_bidder_id)

    result = db.session.execute(
        update(Auction)
        .where(*auction_conditions)
        .values(current_bid=bid_amount, bidder_id=user.id)
    )
    if result.rowcount != 1:
        db.session.rollback()
        flash("Quelqu'un a enchéri juste avant toi. Recharge le marché et retente.", "warning")
        return redirect(url_for('market.marche'))

    if previous_bidder_id and previous_bid_amount > 0:
        previous_user = User.query.get(previous_bidder_id)
        if previous_user:
            previous_user.earn(
                previous_bid_amount,
                reason_code='auction_outbid_refund',
                reason_label='Remboursement enchere depassee',
                details=f"Ton offre sur {auction.pig_name} a ete depassee.",
                reference_type='auction',
                reference_id=auction.id,
            )

    db.session.commit()
    flash(f"Enchère placée : {bid_amount:.0f} 🪙 sur {auction.pig_name} !", "success")
    return redirect(url_for('market.marche'))


@market_bp.route('/sell-pig', methods=['POST'])
def sell_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not get_market_unlock_progress(user)[0]:
        flash(get_market_lock_reason(user), "warning")
        return redirect(url_for('market.marche'))
    if not is_market_open():
        flash("Le marché est fermé ! Reviens le jour du marché.", "error")
        return redirect(url_for('market.marche'))
    pig_id = request.form.get('pig_id', type=int)
    pig = Pig.query.filter_by(id=pig_id, user_id=user.id, is_alive=True).first()
    if not pig:
        flash("Tu n'as pas ce cochon ou il n'est plus disponible !", "error")
        return redirect(url_for('market.marche'))
    if pig.is_injured:
        flash("Impossible de vendre un cochon blessé. Il doit d'abord voir le vétérinaire.", "warning")
        return redirect(url_for('market.marche'))
    starting_price = request.form.get('price', type=float)
    if not starting_price or starting_price < 5:
        flash("Prix minimum : 5 🪙 !", "error")
        return redirect(url_for('market.marche'))

    auction = Auction(
        pig_name=pig.name, pig_emoji=pig.emoji,
        pig_vitesse=pig.vitesse, pig_endurance=pig.endurance,
        pig_agilite=pig.agilite, pig_force=pig.force,
        pig_intelligence=pig.intelligence, pig_moral=pig.moral,
        pig_weight=pig.weight_kg or DEFAULT_PIG_WEIGHT_KG,
        pig_rarity=pig.rarity or 'commun',
        pig_max_races=max(0, (pig.max_races or 80) - pig.races_entered),
        pig_origin=pig.origin_country or 'France',
        pig_origin_flag=pig.origin_flag or '🇫🇷',
        starting_price=starting_price,
        current_bid=0,
        seller_id=user.id,
        source_pig_id=pig.id,
        ends_at=get_market_close_time(),
        status='active'
    )
    pig.is_alive = False
    pig.death_cause = 'vendu'
    pig.death_date = datetime.utcnow()
    pig.charcuterie_type = 'En vente'
    pig.charcuterie_emoji = '🏷️'
    pig.epitaph = f"{pig.name} a été mis en vente au Marché aux Groins."
    db.session.add(auction)
    db.session.commit()
    flash(f"🏷️ {pig.name} est en vente pour {starting_price:.0f} 🪙 minimum !", "success")
    return redirect(url_for('market.marche'))
