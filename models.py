from datetime import datetime
from extensions import db


class GameConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=100.0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_relief_at = db.Column(db.DateTime, nullable=True)
    barn_heritage_bonus = db.Column(db.Float, default=0.0)
    snack_shares_today = db.Column(db.Integer, default=0)
    snack_share_reset_at = db.Column(db.DateTime, nullable=True)
    bets = db.relationship('Bet', backref='user', lazy=True)
    balance_transactions = db.relationship('BalanceTransaction', backref='user', lazy=True)
    course_plans = db.relationship('CoursePlan', backref='user', lazy=True)

class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False, default='Mon Cochon')
    emoji = db.Column(db.String(10), default='🐷')

    # Compétences (0-100)
    vitesse = db.Column(db.Float, default=10.0)
    endurance = db.Column(db.Float, default=10.0)
    agilite = db.Column(db.Float, default=10.0)
    force = db.Column(db.Float, default=10.0)
    intelligence = db.Column(db.Float, default=10.0)
    moral = db.Column(db.Float, default=10.0)

    # État Tamagotchi (0-100)
    energy = db.Column(db.Float, default=80.0)
    hunger = db.Column(db.Float, default=60.0)
    happiness = db.Column(db.Float, default=70.0)
    weight_kg = db.Column(db.Float, default=112.0)

    # Progression
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    races_won = db.Column(db.Integer, default=0)
    races_entered = db.Column(db.Integer, default=0)
    school_sessions_completed = db.Column(db.Integer, default=0)

    # Durée de vie & Rareté & Origine
    max_races = db.Column(db.Integer, default=80)
    rarity = db.Column(db.String(20), default='commun')
    origin_country = db.Column(db.String(30), default='France')
    origin_flag = db.Column(db.String(10), default='🇫🇷')

    # Mort & Abattoir
    is_alive = db.Column(db.Boolean, default=True)
    death_date = db.Column(db.DateTime, nullable=True)
    death_cause = db.Column(db.String(30), nullable=True)
    charcuterie_type = db.Column(db.String(50), nullable=True)
    charcuterie_emoji = db.Column(db.String(10), nullable=True)
    epitaph = db.Column(db.String(200), nullable=True)

    # Challenge de la Mort
    challenge_mort_wager = db.Column(db.Float, default=0.0)

    # Blessures & Vétérinaire
    is_injured = db.Column(db.Boolean, default=False)
    injury_risk = db.Column(db.Float, default=10.0)
    vet_deadline = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    last_school_at = db.Column(db.DateTime, nullable=True)
    last_fed_at = db.Column(db.DateTime, nullable=True)

    lineage_name = db.Column(db.String(80), nullable=True)
    generation = db.Column(db.Integer, default=1)
    lineage_boost = db.Column(db.Float, default=0.0)
    sire_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    dam_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    retired_into_heritage = db.Column(db.Boolean, default=False)

    owner = db.relationship('User', backref=db.backref('pigs', lazy=True))

class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    winner_name = db.Column(db.String(80), nullable=True)
    winner_odds = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='upcoming')
    participants = db.relationship('Participant', backref='race', lazy=True)
    bets = db.relationship('Bet', backref='race', lazy=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), default='🐷')
    odds = db.Column(db.Float, nullable=False)
    win_probability = db.Column(db.Float, nullable=False)
    finish_position = db.Column(db.Integer, nullable=True)
    pig_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    owner_name = db.Column(db.String(80), nullable=True)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    pig_name = db.Column(db.String(80), nullable=False)
    bet_type = db.Column(db.String(20), default='win')
    selection_order = db.Column(db.String(240), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    odds_at_bet = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    winnings = db.Column(db.Float, default=0.0)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)

class BalanceTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    balance_before = db.Column(db.Float, nullable=True)
    balance_after = db.Column(db.Float, nullable=True)
    reason_code = db.Column(db.String(40), nullable=False, default='adjustment')
    reason_label = db.Column(db.String(80), nullable=False, default='Mouvement BitGroins')
    details = db.Column(db.String(255), nullable=True)
    reference_type = db.Column(db.String(30), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class CoursePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    pig_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=False, index=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    pig = db.relationship('Pig', backref=db.backref('course_plans', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('pig_id', 'scheduled_at', name='ux_course_plan_pig_slot'),
    )

class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Cochon en vente
    pig_name = db.Column(db.String(80), nullable=False)
    pig_emoji = db.Column(db.String(10), default='🐷')
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
    # Enchère
    starting_price = db.Column(db.Float, default=20.0)
    current_bid = db.Column(db.Float, default=0.0)
    bidder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    bidder = db.relationship('User', foreign_keys=[bidder_id], backref='bids_placed')
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    seller = db.relationship('User', foreign_keys=[seller_id])
    source_pig_id = db.Column(db.Integer, nullable=True)
    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')
