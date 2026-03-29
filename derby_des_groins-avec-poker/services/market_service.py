from datetime import datetime, timedelta
import random

from sqlalchemy import func

from data import (
    BOURSE_BLOCK_MAX, BOURSE_BLOCK_MIN, BOURSE_DEFAULT_POS, BOURSE_GRAIN_LAYOUT,
    BOURSE_GRID_SIZE, BOURSE_GRID_VALUES, BOURSE_MIN_MOVEMENT, BOURSE_MOVEMENT_DIVISOR,
    BOURSE_SURCHARGE_FACTOR, CEREALS, DEFAULT_PIG_WEIGHT_KG, PIG_EMOJIS,
    PIG_NAME_PREFIXES, PIG_NAME_SUFFIXES, PIG_ORIGINS, RARITIES,
)
from extensions import db
from models import Auction, BalanceTransaction, GrainMarket, MarketHistory, Pig, User

from helpers.db import apply_row_lock
from services.game_settings_service import get_game_settings
from services.finance_service import credit_user_balance
from services.pig_service import build_unique_pig_name, generate_weight_kg_for_profile


def get_prix_moyen_groin():
    recent_sales = Auction.query.filter_by(status='sold').order_by(Auction.ends_at.desc()).limit(10).all()
    if recent_sales:
        return round(sum(a.current_bid for a in recent_sales) / len(recent_sales), 2)
    active = Auction.query.filter_by(status='active').all()
    if active:
        return round(sum(a.starting_price for a in active) / len(active), 2)
    return 42.0


def get_next_market_time():
    """Retourne le prochain créneau d'ouverture du marché."""
    settings = get_game_settings()
    now = datetime.now()
    market_days = settings.market_days
    if not market_days:
        return now + timedelta(days=7)

    closing_minutes = settings.market_hour * 60 + settings.market_minute + settings.market_duration

    for offset in range(8):  # 0..7 couvre la semaine + rebouclage
        candidate_day = (now.weekday() + offset) % 7
        if candidate_day not in market_days:
            continue
        candidate = now.replace(hour=settings.market_hour, minute=settings.market_minute, second=0, microsecond=0) + timedelta(days=offset)
        # Si c'est aujourd'hui mais déjà fermé, passer
        if offset == 0 and now.hour * 60 + now.minute >= closing_minutes:
            continue
        return candidate

    # Fallback : prochain occurrence du premier jour configuré
    days_ahead = (market_days[0] - now.weekday()) % 7 or 7
    return now.replace(hour=settings.market_hour, minute=settings.market_minute, second=0, microsecond=0) + timedelta(days=days_ahead)


def is_market_open(user=None):
    """Vérifie si le marché est ouvert maintenant."""
    if user and user.is_admin:
        return True
    settings = get_game_settings()
    now = datetime.now()
    if now.weekday() not in settings.market_days:
        return False
    market_start = now.replace(hour=settings.market_hour, minute=settings.market_minute, second=0, microsecond=0)
    return market_start <= now <= market_start + timedelta(minutes=settings.market_duration)


def get_market_close_time():
    settings = get_game_settings()
    now = datetime.now()
    market_start = now.replace(hour=settings.market_hour, minute=settings.market_minute, second=0, microsecond=0)
    return market_start + timedelta(minutes=settings.market_duration)


def generate_auction_pig():
    rarities = list(RARITIES.keys())
    weights = [RARITIES[r]['weight'] for r in rarities]
    rarity_key = random.choices(rarities, weights=weights, k=1)[0]
    rarity = RARITIES[rarity_key]
    origin = random.choice(PIG_ORIGINS)
    min_s, max_s = rarity['stats_range']
    min_r, max_r = rarity['max_races_range']
    min_p, max_p = rarity['price_range']
    ends = get_market_close_time() if is_market_open() else datetime.utcnow() + timedelta(hours=2)
    stats = {s: round(random.uniform(min_s, max_s), 1) for s in ['vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral']}
    stats[origin['bonus_stat']] = min(100, stats[origin['bonus_stat']] + origin['bonus'])
    return Auction(
        pig_name=f"{random.choice(PIG_NAME_PREFIXES)} {random.choice(PIG_NAME_SUFFIXES)}", pig_emoji=random.choice(PIG_EMOJIS),
        pig_vitesse=stats['vitesse'], pig_endurance=stats['endurance'], pig_agilite=stats['agilite'], pig_force=stats['force'],
        pig_intelligence=stats['intelligence'], pig_moral=stats['moral'], pig_weight=generate_weight_kg_for_profile(stats),
        pig_rarity=rarity_key, pig_max_races=random.randint(min_r, max_r), pig_origin=origin['country'], pig_origin_flag=origin['flag'],
        starting_price=random.randint(min_p, max_p), current_bid=0, ends_at=ends, status='active'
    )


def resolve_auctions():
    now = datetime.utcnow()
    expired = Auction.query.filter(Auction.status == 'active', Auction.ends_at <= now).all()
    for auction in expired:
        auction = apply_row_lock(Auction.query.filter_by(id=auction.id)).first()
        if not auction or auction.status != 'active' or auction.ends_at > now:
            continue
        if auction.bidder_id and auction.current_bid > 0:
            auction.status = 'sold'
            winner = User.query.get(auction.bidder_id)
            if winner:
                active_pigs = Pig.query.filter_by(user_id=winner.id, is_alive=True).order_by(Pig.id).all()
                if len(active_pigs) >= 2:
                    active_pigs[0].kill(cause='sacrifice')
                new_pig = Pig(
                    user_id=winner.id, name=build_unique_pig_name(auction.pig_name, fallback_prefix='Champion du marche'), emoji=auction.pig_emoji,
                    vitesse=auction.pig_vitesse, endurance=auction.pig_endurance, agilite=auction.pig_agilite, force=auction.pig_force,
                    intelligence=auction.pig_intelligence, moral=auction.pig_moral, weight_kg=auction.pig_weight or DEFAULT_PIG_WEIGHT_KG,
                    max_races=auction.pig_max_races, rarity=auction.pig_rarity, origin_country=auction.pig_origin, origin_flag=auction.pig_origin_flag,
                    energy=80, hunger=60, happiness=70
                )
                db.session.add(new_pig)
            if auction.seller_id:
                buyer_name = winner.username if winner else 'un acheteur'
                credit_user_balance(auction.seller_id, auction.current_bid, reason_code='auction_sale', reason_label='Vente au marche', details=f"{auction.pig_name} vendu a {buyer_name}.", reference_type='auction', reference_id=auction.id)
        else:
            auction.status = 'expired'
            if auction.seller_id and auction.source_pig_id:
                returned_pig = Pig.query.get(auction.source_pig_id)
                if returned_pig and returned_pig.user_id == auction.seller_id:
                    returned_pig.is_alive = True
                    returned_pig.death_date = None
                    returned_pig.death_cause = None
                    returned_pig.charcuterie_type = None
                    returned_pig.charcuterie_emoji = None
                    returned_pig.epitaph = None
    if is_market_open():
        active_count = Auction.query.filter_by(status='active').count()
        while active_count < 5:
            db.session.add(generate_auction_pig())
            active_count += 1
    db.session.commit()


def get_grain_market():
    market = GrainMarket.query.first()
    if market is None:
        market = GrainMarket(id=1, cursor_x=BOURSE_DEFAULT_POS, cursor_y=BOURSE_DEFAULT_POS)
        db.session.add(market)
        db.session.commit()
    return market


def _cell_value(grid_index):
    return BOURSE_GRID_VALUES[max(0, min(BOURSE_GRID_SIZE - 1, grid_index))]


def get_grain_grid_pos(market, dx, dy):
    bx = market.cursor_x if market.cursor_x is not None else BOURSE_DEFAULT_POS
    by = market.cursor_y if market.cursor_y is not None else BOURSE_DEFAULT_POS
    return (bx + dx, by + dy)


def get_grain_surcharge(gx, gy):
    return 1.0 + (_cell_value(gx) + _cell_value(gy)) * BOURSE_SURCHARGE_FACTOR


def get_all_grain_surcharges(market):
    result = {}
    for (dx, dy), cereal_key in BOURSE_GRAIN_LAYOUT.items():
        if cereal_key is not None:
            gx, gy = get_grain_grid_pos(market, dx, dy)
            result[cereal_key] = get_grain_surcharge(gx, gy)
    return result


def get_bourse_movement_points(user_id):
    user = User.query.get(user_id)
    if user and user.is_admin:
        return 99
    total_purchases = db.session.query(func.count(BalanceTransaction.id)).filter(BalanceTransaction.user_id == user_id, BalanceTransaction.reason_code == 'feed_purchase').scalar() or 0
    return max(BOURSE_MIN_MOVEMENT, total_purchases // BOURSE_MOVEMENT_DIVISOR)


def move_bourse_cursor(market, dx, dy, max_points):
    if dx == 0 and dy == 0:
        return 0
    total_requested = abs(dx) + abs(dy)
    if total_requested > max_points:
        if dx != 0:
            dx = max(-max_points, min(max_points, dx))
        else:
            dy = max(-max_points, min(max_points, dy))
    new_x = max(BOURSE_BLOCK_MIN, min(BOURSE_BLOCK_MAX, market.cursor_x + dx))
    new_y = max(BOURSE_BLOCK_MIN, min(BOURSE_BLOCK_MAX, market.cursor_y + dy))
    actual_dx = new_x - market.cursor_x
    actual_dy = new_y - market.cursor_y
    points_used = abs(actual_dx) + abs(actual_dy)
    market.cursor_x = new_x
    market.cursor_y = new_y
    return points_used


def is_grain_blocked(grain_key, market):
    return market.vitrine_grain == grain_key


def update_vitrine(market, grain_key, user_id):
    market.vitrine_grain = grain_key
    market.vitrine_user_id = user_id
    market.last_purchase_at = datetime.utcnow()
    market.total_transactions = (market.total_transactions or 0) + 1
    log_market_state(market)


def log_market_state(market):
    """Enregistre l'état actuel des prix dans l'historique."""
    from data import CEREALS
    surcharges = get_all_grain_surcharges(market)
    for key, surcharge in surcharges.items():
        base_cost = CEREALS[key]['cost']
        history = MarketHistory(
            cereal_key=key,
            price=round(base_cost * surcharge, 2),
            surcharge=round(surcharge, 2),
            recorded_at=datetime.utcnow()
        )
        db.session.add(history)


def resolve_market_history():
    """Tâche planifiée pour nettoyer le vieil historique ou agréger ?
    Pour l'instant, on se contente de logger de temps en temps."""
    market = get_grain_market()
    log_market_state(market)
    db.session.commit()


def get_bourse_cereals(market, feeding_multiplier=1.0):
    from helpers.game_data import get_cereals_dict
    surcharges = get_all_grain_surcharges(market)
    cereals = get_cereals_dict()
    result = {}
    for (dx, dy), cereal_key in BOURSE_GRAIN_LAYOUT.items():
        if cereal_key is None:
            continue
        cer = cereals[cereal_key]
        gx, gy = get_grain_grid_pos(market, dx, dy)
        surcharge = surcharges[cereal_key]
        c = dict(cer)
        c['original_cost'] = cer['cost']
        c['surcharge'] = surcharge
        c['bourse_cost'] = round(cer['cost'] * surcharge, 2)
        c['effective_cost'] = round(cer['cost'] * surcharge * feeding_multiplier, 2)
        c['grid_x'] = gx
        c['grid_y'] = gy
        c['cell_value'] = _cell_value(gx) + _cell_value(gy)
        c['is_blocked'] = is_grain_blocked(cereal_key, market)
        c['block_dx'] = dx
        c['block_dy'] = dy
        result[cereal_key] = c
    return result


def get_bourse_grid_data(market):
    from helpers.game_data import get_cereals_dict
    bx = market.cursor_x if market.cursor_x is not None else BOURSE_DEFAULT_POS
    by = market.cursor_y if market.cursor_y is not None else BOURSE_DEFAULT_POS
    block_grains = {(bx + dx, by + dy): ck for (dx, dy), ck in BOURSE_GRAIN_LAYOUT.items()}
    cereals = get_cereals_dict()
    grid = []
    for y in range(BOURSE_GRID_SIZE):
        row = []
        for x in range(BOURSE_GRID_SIZE):
            cell_value = BOURSE_GRID_VALUES[x] + BOURSE_GRID_VALUES[y]
            grain_key = block_grains.get((x, y))
            row.append({'x': x, 'y': y, 'val_x': BOURSE_GRID_VALUES[x], 'val_y': BOURSE_GRID_VALUES[y], 'cell_value': cell_value, 'surcharge': round(1.0 + cell_value * BOURSE_SURCHARGE_FACTOR, 2), 'is_block': (abs(x - bx) <= 1 and abs(y - by) <= 1), 'is_center': (x == bx and y == by), 'grain_key': grain_key, 'grain_emoji': cereals[grain_key]['emoji'] if grain_key in cereals else None, 'grain_name': cereals[grain_key]['name'] if grain_key in cereals else None})
        grid.append(row)
    return grid
