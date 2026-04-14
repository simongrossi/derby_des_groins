from datetime import datetime

from extensions import db


class Duel(db.Model):
    __tablename__ = 'duel'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default='waiting')
    visibility = db.Column(db.String(20), nullable=False, default='public')
    stake = db.Column(db.Float, nullable=False, default=0.0)

    player1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    pig1_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=False, index=True)
    player2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    pig2_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True, index=True)
    challenged_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)

    current_round = db.Column(db.Integer, nullable=False, default=0)
    pig1_position = db.Column(db.Float, nullable=False, default=0.0)
    pig2_position = db.Column(db.Float, nullable=False, default=0.0)
    pig1_endurance = db.Column(db.Float, nullable=False, default=100.0)
    pig2_endurance = db.Column(db.Float, nullable=False, default=100.0)
    arena_type = db.Column(db.String(30), nullable=False, default='classic')

    round_actions_p1 = db.Column(db.Text, nullable=True)
    round_actions_p2 = db.Column(db.Text, nullable=True)
    round_deadline_at = db.Column(db.DateTime, nullable=True)

    replay_json = db.Column(db.Text, nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    player1 = db.relationship('User', foreign_keys=[player1_id])
    player2 = db.relationship('User', foreign_keys=[player2_id])
    challenged_user = db.relationship('User', foreign_keys=[challenged_user_id])
    winner = db.relationship('User', foreign_keys=[winner_id])
    pig1 = db.relationship('Pig', foreign_keys=[pig1_id])
    pig2 = db.relationship('Pig', foreign_keys=[pig2_id])

    __table_args__ = (
        db.Index('ix_duel_lobby', 'status', 'visibility', 'created_at'),
    )

    def opponent_of(self, user_id):
        if user_id == self.player1_id:
            return self.player2
        if user_id == self.player2_id:
            return self.player1
        return None

    def pig_of(self, user_id):
        if user_id == self.player1_id:
            return self.pig1
        if user_id == self.player2_id:
            return self.pig2
        return None
