from datetime import datetime
import json

from config.game_rules import RACE_PLANNING_RULES
from extensions import db


class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    winner_name = db.Column(db.String(80), nullable=True)
    winner_odds = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='upcoming')
    replay_json = db.Column(db.Text, nullable=True)
    preview_segments_json = db.Column(db.Text, nullable=True)
    participants = db.relationship('Participant', backref='race', lazy=True)
    bets = db.relationship('Bet', backref='race', lazy=True)

    __table_args__ = (
        db.Index('ix_race_status_finished', 'status', 'finished_at'),
    )


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), default='🐷')
    avatar_url = db.Column(db.String(500), nullable=True)
    odds = db.Column(db.Float, nullable=False)
    win_probability = db.Column(db.Float, nullable=False)
    finish_position = db.Column(db.Integer, nullable=True)
    pig_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    strategy = db.Column(db.Integer, default=50)
    owner_name = db.Column(db.String(80), nullable=True)

    __table_args__ = (
        db.Index('ix_participant_race', 'race_id'),
    )


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

    __table_args__ = (
        db.Index('ix_bet_user_race', 'user_id', 'race_id'),
    )


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
    strategy_profile = db.Column(
        db.Text,
        nullable=False,
        default=lambda: CoursePlan.build_strategy_profile(),
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @staticmethod
    def build_strategy_profile(
        phase_1=RACE_PLANNING_RULES.default_strategy_phase_1,
        phase_2=RACE_PLANNING_RULES.default_strategy_phase_2,
        phase_3=RACE_PLANNING_RULES.default_strategy_phase_3,
    ) -> str:
        return json.dumps(
            {
                'phase_1': int(phase_1),
                'phase_2': int(phase_2),
                'phase_3': int(phase_3),
            }
        )

    @property
    def strategy_segments(self) -> dict:
        default_profile = RACE_PLANNING_RULES.default_strategy_profile()
        if not self.strategy_profile:
            return default_profile
        try:
            profile = json.loads(self.strategy_profile)
        except (TypeError, ValueError):
            return default_profile
        return {
            'phase_1': int(profile.get('phase_1', default_profile['phase_1'])),
            'phase_2': int(profile.get('phase_2', default_profile['phase_2'])),
            'phase_3': int(profile.get('phase_3', default_profile['phase_3'])),
        }

    @property
    def strategy_summary(self) -> str:
        profile = self.strategy_segments
        return f"Départ {profile['phase_1']} • Milieu {profile['phase_2']} • Final {profile['phase_3']}"

    pig = db.relationship('Pig', backref=db.backref('course_plans', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('pig_id', 'scheduled_at', name='ux_course_plan_pig_slot'),
    )
