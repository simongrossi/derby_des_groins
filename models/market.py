from datetime import datetime

from config.game_rules import PIG_DEFAULTS
from extensions import db


class GrainMarket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cursor_x = db.Column(db.Integer, default=3)
    cursor_y = db.Column(db.Integer, default=3)
    vitrine_grain = db.Column(db.String(20), nullable=True)
    vitrine_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_move_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_move_at = db.Column(db.DateTime, nullable=True)
    last_purchase_at = db.Column(db.DateTime, nullable=True)
    total_transactions = db.Column(db.Integer, default=0)

    vitrine_user = db.relationship('User', foreign_keys=[vitrine_user_id])
    last_move_user = db.relationship('User', foreign_keys=[last_move_user_id])


class MarketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cereal_key = db.Column(db.String(20), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    surcharge = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class MarketPositionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cursor_x = db.Column(db.Integer, nullable=False)
    cursor_y = db.Column(db.Integer, nullable=False)
    average_surcharge = db.Column(db.Float, nullable=False, default=1.0)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class GrainFutureContract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    cereal_key = db.Column(db.String(20), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    base_unit_price = db.Column(db.Float, nullable=False)
    locked_unit_price = db.Column(db.Float, nullable=False)
    surcharge_locked = db.Column(db.Float, nullable=False, default=1.0)
    feeding_multiplier_locked = db.Column(db.Float, nullable=False, default=1.0)
    premium_rate = db.Column(db.Float, nullable=False, default=0.10)
    total_price_paid = db.Column(db.Float, nullable=False)
    delivery_due_at = db.Column(db.DateTime, nullable=False, index=True)
    delivered_at = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='active', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('grain_future_contracts', lazy=True))


class MarketEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(30), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='medium')
    blocked_cereal_key = db.Column(db.String(20), nullable=True, index=True)
    cursor_shift_x = db.Column(db.Integer, nullable=False, default=0)
    cursor_shift_y = db.Column(db.Integer, nullable=False, default=0)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ends_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pig_name = db.Column(db.String(80), nullable=False)
    pig_emoji = db.Column(db.String(10), default='🐷')
    pig_sex = db.Column(db.String(1), nullable=False, default='M')
    pig_avatar_url = db.Column(db.String(500), nullable=True)
    pig_vitesse = db.Column(db.Float, default=10.0)
    pig_endurance = db.Column(db.Float, default=10.0)
    pig_agilite = db.Column(db.Float, default=10.0)
    pig_force = db.Column(db.Float, default=10.0)
    pig_intelligence = db.Column(db.Float, default=10.0)
    pig_moral = db.Column(db.Float, default=10.0)
    pig_weight = db.Column(db.Float, default=112.0)
    pig_rarity = db.Column(db.String(20), default='commun')
    pig_max_races = db.Column(db.Integer, default=PIG_DEFAULTS.max_races)
    pig_origin = db.Column(db.String(30), default='France')
    pig_origin_flag = db.Column(db.String(10), default='🇫🇷')
    starting_price = db.Column(db.Float, default=20.0)
    current_bid = db.Column(db.Float, default=0.0)
    bidder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    bidder = db.relationship('User', foreign_keys=[bidder_id], backref='bids_placed')
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    seller = db.relationship('User', foreign_keys=[seller_id])
    source_pig_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')
