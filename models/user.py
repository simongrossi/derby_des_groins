from datetime import UTC, datetime, timedelta

from config.economy_defaults import WEEKLY_BACON_TICKETS
from extensions import db


def utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


class GameConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=100.0)
    email = db.Column(db.String(200), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    last_relief_at = db.Column(db.DateTime, nullable=True)
    barn_heritage_bonus = db.Column(db.Float, default=0.0)
    snack_shares_today = db.Column(db.Integer, default=0)
    snack_share_reset_at = db.Column(db.DateTime, nullable=True)
    last_daily_reward_at = db.Column(db.DateTime, nullable=True)
    last_truffe_at = db.Column(db.DateTime, nullable=True)
    truffe_plays_today = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    last_agenda_at = db.Column(db.DateTime, nullable=True)
    agenda_plays_today = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    pendu_plays_today = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    last_pendu_at = db.Column(db.DateTime, nullable=True)
    daily_casino_wins = db.Column(db.Float, default=0.0, nullable=False, server_default='0')
    last_casino_date = db.Column(db.Date, nullable=True)
    bets = db.relationship('Bet', backref='user', lazy=True)
    balance_transactions = db.relationship('BalanceTransaction', backref='user', lazy=True)
    course_plans = db.relationship('CoursePlan', backref='user', lazy=True)
    trophies = db.relationship('Trophy', backref='user', lazy=True, cascade='all, delete-orphan')
    cereal_inventory = db.relationship(
        'UserCerealInventory',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def can_afford(self, amount: float) -> bool:
        return (self.balance or 0.0) >= amount

    @property
    def active_pigs(self):
        from models.pig import Pig

        return Pig.query.filter_by(user_id=self.id, is_alive=True).all()

    @property
    def pig_count(self) -> int:
        from models.pig import Pig

        return Pig.query.filter_by(user_id=self.id, is_alive=True).count()

    @property
    def bacon_tickets(self) -> int:
        from models.race import Bet

        current_dt = utcnow_naive()
        week_start = datetime.combine(
            (current_dt - timedelta(days=current_dt.weekday())).date(),
            datetime.min.time(),
        )
        week_end = week_start + timedelta(days=7)
        weekly_limit_entry = GameConfig.query.filter_by(key='economy_weekly_bacon_tickets').first()
        try:
            weekly_limit = (
                int(float(weekly_limit_entry.value))
                if weekly_limit_entry
                else int(WEEKLY_BACON_TICKETS)
            )
        except (TypeError, ValueError):
            weekly_limit = int(WEEKLY_BACON_TICKETS)
        count = Bet.query.filter(
            Bet.user_id == self.id,
            Bet.placed_at >= week_start,
            Bet.placed_at < week_end,
        ).count()
        return max(0, weekly_limit - count)
