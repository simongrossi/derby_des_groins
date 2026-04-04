from datetime import datetime

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
    pig_max_races = db.Column(db.Integer, default=80)
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
