from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime

from content.pigs_catalog import PIG_ORIGINS, RARITIES
from content.stats_metadata import JOURS_FR
from exceptions import BusinessRuleError
from extensions import limiter
from helpers.market_helpers import get_market_lock_reason, get_market_unlock_progress
from helpers.race import get_user_active_pigs
from models import User, Auction
from services.game_settings_service import get_game_settings
from services.market_service import (
    get_next_market_time,
    get_prix_moyen_groin,
    is_market_open,
    list_pig_for_sale,
    place_auction_bid_for_user,
)

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
            pigs = get_user_active_pigs(user)
            market_access = get_market_unlock_progress(user)[0]
            market_lock_reason = get_market_lock_reason(user)

    settings = get_game_settings()
    market_open = is_market_open(user)
    next_market = get_next_market_time()
    market_day_name = ', '.join(JOURS_FR[d] for d in settings.market_days) if settings.market_days else JOURS_FR[4]
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
@limiter.limit("10 per minute")
def bid():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = place_auction_bid_for_user(
            session['user_id'],
            request.form.get('auction_id', type=int),
            request.form.get('bid_amount', type=float),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('market.marche'))


@market_bp.route('/sell-pig', methods=['POST'])
@limiter.limit("5 per minute")
def sell_pig():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        result = list_pig_for_sale(
            session['user_id'],
            request.form.get('pig_id', type=int),
            request.form.get('price', type=float),
        )
        flash(result['message'], result.get('category', 'success'))
    except BusinessRuleError as exc:
        flash(str(exc), "error")
    return redirect(url_for('market.marche'))
