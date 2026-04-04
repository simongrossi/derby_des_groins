from datetime import datetime, timedelta
import random

from sqlalchemy import func
from sqlalchemy import update

from config.game_rules import MARKET_RULES
from data import (
    BOURSE_BLOCK_MAX, BOURSE_BLOCK_MIN, BOURSE_DEFAULT_POS, BOURSE_GRAIN_LAYOUT,
    BOURSE_GRID_SIZE, BOURSE_GRID_VALUES, BOURSE_MIN_MOVEMENT, BOURSE_MOVEMENT_DIVISOR,
    BOURSE_SURCHARGE_FACTOR, CEREALS, DEFAULT_PIG_WEIGHT_KG, PIG_EMOJIS,
    PIG_NAME_PREFIXES, PIG_NAME_SUFFIXES, PIG_ORIGINS, RARITIES,
)
from exceptions import InsufficientFundsError, UserNotFoundError, ValidationError


def _get_bourse_surcharge_factor():
    from helpers.config import get_config
    try:
        return float(get_config('bourse_surcharge_factor', str(BOURSE_SURCHARGE_FACTOR)))
    except (TypeError, ValueError):
        return float(BOURSE_SURCHARGE_FACTOR)


def _get_bourse_movement_divisor():
    from helpers.config import get_config
    try:
        return max(1, int(float(get_config('bourse_movement_divisor', str(BOURSE_MOVEMENT_DIVISOR)))))
    except (TypeError, ValueError):
        return int(BOURSE_MOVEMENT_DIVISOR)
from extensions import db
from models import Auction, BalanceTransaction, GrainMarket, MarketHistory, Pig, User

from services.game_settings_service import get_game_settings
from services.finance_service import credit_user, credit_user_balance, debit_user
from services.pig_service import build_unique_pig_name, generate_weight_kg_for_profile, kill_pig, random_pig_sex
from services.notification_service import push_user_notification


def get_prix_moyen_groin():
    recent_sales = Auction.query.filter_by(status='sold').order_by(Auction.ends_at.desc()).limit(10).all()
    if recent_sales:
        return round(sum(a.current_bid for a in recent_sales) / len(recent_sales), 2)
    active = Auction.query.filter_by(status='active').all()
    if active:
        return round(sum(a.starting_price for a in active) / len(active), 2)
    return 42.0


def _get_market_user(user_or_id):
    user = user_or_id if isinstance(user_or_id, User) else User.query.get(user_or_id)
    if not user:
        raise UserNotFoundError("Utilisateur introuvable.")
    return user


def _ensure_market_access(user):
    from helpers.market_helpers import get_market_lock_reason, get_market_unlock_progress

    if not get_market_unlock_progress(user)[0]:
        raise ValidationError(get_market_lock_reason(user))


def place_auction_bid_for_user(user_or_id, auction_id, bid_amount):
    from helpers.db import apply_row_lock

    user = _get_market_user(user_or_id)
    _ensure_market_access(user)

    auction = apply_row_lock(Auction.query.filter_by(id=auction_id)).first()
    if not auction or auction.status != 'active':
        raise ValidationError("Cette enchère n'est plus disponible !")
    if datetime.utcnow() >= auction.ends_at:
        raise ValidationError("L'enchère est terminée !")

    min_bid = (
        round((auction.current_bid or 0.0) + MARKET_RULES.minimum_bid_increment, 2)
        if auction.current_bid and auction.current_bid > 0
        else round(float(auction.starting_price or 0.0), 2)
    )
    if not bid_amount or bid_amount < min_bid:
        raise ValidationError(f"Enchère minimum : {min_bid:.0f} 🪙 !")

    try:
        debit_user(
            user,
            bid_amount,
            reason_code='auction_bid',
            reason_label='Mise bloquee en enchere',
            details=f"Enchere sur {auction.pig_name}.",
            reference_type='auction',
            reference_id=auction.id,
            commit=False,
        )
    except InsufficientFundsError:
        raise InsufficientFundsError("Pas assez de BitGroins !") from None

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
        raise ValidationError("Quelqu'un a enchéri juste avant toi. Recharge le marché et retente.")

    if previous_bidder_id and previous_bid_amount > 0:
        previous_user = User.query.get(previous_bidder_id)
        if previous_user:
            credit_user(
                previous_user,
                previous_bid_amount,
                reason_code='auction_outbid_refund',
                reason_label='Remboursement enchere depassee',
                details=f"Ton offre sur {auction.pig_name} a ete depassee.",
                reference_type='auction',
                reference_id=auction.id,
                commit=False,
            )
            push_user_notification(
                user_id=previous_user.id,
                title="Marché aux Groins",
                message=(
                    f"{auction.pig_name} a été surenchéri. "
                    f"Ta mise ({previous_bid_amount:.0f} 🪙) a été remboursée."
                ),
                category='warning',
                event_key=f"auction_outbid:{auction.id}:{int(bid_amount)}:{user.id}",
            )

    db.session.commit()
    return {
        'category': 'success',
        'message': f"Enchère placée : {bid_amount:.0f} 🪙 sur {auction.pig_name} !",
    }


def list_pig_for_sale(user_or_id, pig_id, starting_price):
    user = _get_market_user(user_or_id)
    _ensure_market_access(user)

    if not is_market_open(user):
        raise ValidationError("Le marché est fermé ! Reviens le jour du marché.")

    pig = Pig.query.filter_by(id=pig_id, user_id=user.id, is_alive=True).first()
    if not pig:
        raise ValidationError("Tu n'as pas ce cochon ou il n'est plus disponible !")
    if pig.is_injured:
        raise ValidationError("Impossible de vendre un cochon blessé. Il doit d'abord voir le vétérinaire.")
    if not starting_price or starting_price < MARKET_RULES.minimum_starting_price:
        raise ValidationError(f"Prix minimum : {MARKET_RULES.minimum_starting_price:.0f} 🪙 !")

    auction = Auction(
        pig_name=pig.name,
        pig_emoji=pig.emoji,
        pig_sex=pig.sex or 'M',
        pig_avatar_url=pig.avatar_url,
        pig_vitesse=pig.vitesse,
        pig_endurance=pig.endurance,
        pig_agilite=pig.agilite,
        pig_force=pig.force,
        pig_intelligence=pig.intelligence,
        pig_moral=pig.moral,
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
        status='active',
    )
    pig.is_alive = False
    pig.death_cause = 'vendu'
    pig.death_date = datetime.utcnow()
    pig.charcuterie_type = 'En vente'
    pig.charcuterie_emoji = '🏷️'
    pig.epitaph = f"{pig.name} a été mis en vente au Marché aux Groins."
    db.session.add(auction)
    db.session.commit()

    return {
        'category': 'success',
        'message': f"🏷️ {pig.name} est en vente pour {starting_price:.0f} 🪙 minimum !",
    }


def move_bourse_for_user(user_or_id, dx, dy):
    user = _get_market_user(user_or_id)
    if dx == 0 and dy == 0:
        raise ValidationError("Deplacement impossible (bord de grille ou points insuffisants).")

    market = get_grain_market()
    max_points = get_bourse_movement_points(user.id)
    points_used = move_bourse_cursor(market, dx, dy, max_points)
    if points_used <= 0:
        raise ValidationError("Deplacement impossible (bord de grille ou points insuffisants).")

    market.last_move_user_id = user.id
    market.last_move_at = datetime.utcnow()
    db.session.commit()

    direction = []
    if dx > 0:
        direction.append(f'{dx} vers la droite')
    elif dx < 0:
        direction.append(f'{abs(dx)} vers la gauche')
    if dy > 0:
        direction.append(f'{dy} vers le bas')
    elif dy < 0:
        direction.append(f'{abs(dy)} vers le haut')

    return {
        'category': 'success',
        'message': f"Bloc deplace de {', '.join(direction)} ! ({points_used} point(s) utilise(s))",
    }


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
        pig_sex=random_pig_sex(),
        pig_vitesse=stats['vitesse'], pig_endurance=stats['endurance'], pig_agilite=stats['agilite'], pig_force=stats['force'],
        pig_intelligence=stats['intelligence'], pig_moral=stats['moral'], pig_weight=generate_weight_kg_for_profile(stats),
        pig_rarity=rarity_key, pig_max_races=random.randint(min_r, max_r), pig_origin=origin['country'], pig_origin_flag=origin['flag'],
        starting_price=random.randint(min_p, max_p), current_bid=0, ends_at=ends, status='active'
    )


def resolve_auctions():
    from helpers.db import apply_row_lock

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
                    kill_pig(active_pigs[0], cause='sacrifice', commit=False)
                new_pig = Pig(
                    user_id=winner.id, name=build_unique_pig_name(auction.pig_name, fallback_prefix='Champion du marche'), emoji=auction.pig_emoji,
                    sex=auction.pig_sex or random_pig_sex(),
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
    return 1.0 + (_cell_value(gx) + _cell_value(gy)) * _get_bourse_surcharge_factor()


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
    return max(BOURSE_MIN_MOVEMENT, total_purchases // _get_bourse_movement_divisor())


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
    recorded_at = datetime.utcnow()
    for key, surcharge in surcharges.items():
        base_cost = CEREALS[key]['cost']
        history = MarketHistory(
            cereal_key=key,
            price=round(base_cost * surcharge, 2),
            surcharge=round(surcharge, 2),
            recorded_at=recorded_at
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
            row.append({'x': x, 'y': y, 'val_x': BOURSE_GRID_VALUES[x], 'val_y': BOURSE_GRID_VALUES[y], 'cell_value': cell_value, 'surcharge': round(1.0 + cell_value * _get_bourse_surcharge_factor(), 2), 'is_block': (abs(x - bx) <= 1 and abs(y - by) <= 1), 'is_center': (x == bx and y == by), 'grain_key': grain_key, 'grain_emoji': cereals[grain_key]['emoji'] if grain_key in cereals else None, 'grain_name': cereals[grain_key]['name'] if grain_key in cereals else None})
        grid.append(row)
    return grid
