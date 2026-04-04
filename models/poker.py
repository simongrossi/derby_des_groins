from datetime import datetime

from extensions import db


class PokerTable(db.Model):
    __tablename__ = 'poker_table'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='lobby', nullable=False)
    phase = db.Column(db.String(20), default='preflop', nullable=True)
    buy_in = db.Column(db.Integer, default=0, nullable=False)
    pot = db.Column(db.Float, default=0.0)
    current_bet = db.Column(db.Float, default=0.0)
    dealer_seat = db.Column(db.Integer, default=1)
    action_seat = db.Column(db.Integer, default=1)
    hand_number = db.Column(db.Integer, default=0)
    deck_json = db.Column(db.Text, default='[]')
    community_json = db.Column(db.Text, default='[]')
    state_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    players = db.relationship('PokerPlayer', backref='table', lazy=True, cascade='all, delete-orphan')
    hands = db.relationship('PokerHandHistory', backref='table', lazy=True, cascade='all, delete-orphan')


class PokerPlayer(db.Model):
    __tablename__ = 'poker_player'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    seat = db.Column(db.Integer, nullable=False)
    chips = db.Column(db.Float, default=0.0)
    current_bet = db.Column(db.Float, default=0.0)
    has_folded = db.Column(db.Boolean, default=False)
    has_acted = db.Column(db.Boolean, default=False)
    is_spectator = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='waiting')
    hole_json = db.Column(db.Text, default='[]')
    vote = db.Column(db.Integer, nullable=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('poker_seats', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('table_id', 'seat', name='uq_poker_table_seat'),
    )


class PokerHandHistory(db.Model):
    __tablename__ = 'poker_hand_history'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=False, index=True)
    hand_number = db.Column(db.Integer, nullable=False)
    pot = db.Column(db.Float, default=0.0)
    winner_ids = db.Column(db.Text, default='[]')
    hand_results = db.Column(db.Text, default='{}')
    community_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
