from datetime import datetime, timedelta

from config.game_rules import PIG_DEFAULTS, PIG_INTERACTION_RULES, PIG_LIMITS
from extensions import db


class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False, default='Mon Cochon')
    emoji = db.Column(db.String(10), default='🐷')
    sex = db.Column(db.String(1), nullable=False, default='M')
    avatar_id = db.Column(db.Integer, db.ForeignKey('pig_avatar.id'), nullable=True)
    avatar = db.relationship('PigAvatar', lazy='joined')

    vitesse = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    endurance = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    agilite = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    force = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    intelligence = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    moral = db.Column(db.Float, default=PIG_DEFAULTS.stat)

    energy = db.Column(db.Float, default=PIG_DEFAULTS.energy)
    hunger = db.Column(db.Float, default=PIG_DEFAULTS.hunger)
    happiness = db.Column(db.Float, default=PIG_DEFAULTS.happiness)
    weight_kg = db.Column(db.Float, default=PIG_DEFAULTS.weight_kg)
    freshness = db.Column(db.Float, default=PIG_DEFAULTS.freshness)
    ever_bad_state = db.Column(db.Boolean, default=False)

    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    races_won = db.Column(db.Integer, default=0)
    races_entered = db.Column(db.Integer, default=0)
    school_sessions_completed = db.Column(db.Integer, default=0)

    max_races = db.Column(db.Integer, default=PIG_DEFAULTS.max_races)
    rarity = db.Column(db.String(20), default='commun')
    origin_country = db.Column(db.String(30), default='France')
    origin_flag = db.Column(db.String(10), default='🇫🇷')

    is_alive = db.Column(db.Boolean, default=True)
    death_date = db.Column(db.DateTime, nullable=True)
    death_cause = db.Column(db.String(30), nullable=True)
    charcuterie_type = db.Column(db.String(50), nullable=True)
    charcuterie_emoji = db.Column(db.String(10), nullable=True)
    epitaph = db.Column(db.String(200), nullable=True)

    challenge_mort_wager = db.Column(db.Float, default=0.0)

    is_injured = db.Column(db.Boolean, default=False)
    injury_risk = db.Column(db.Float, default=PIG_DEFAULTS.injury_risk)
    vet_deadline = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    last_school_at = db.Column(db.DateTime, nullable=True)
    last_fed_at = db.Column(db.DateTime, nullable=True)
    last_interaction_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    comeback_bonus_ready = db.Column(db.Boolean, default=False)
    daily_train_count = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    last_train_date = db.Column(db.Date, nullable=True)
    daily_school_sessions = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    last_school_date = db.Column(db.Date, nullable=True)

    lineage_name = db.Column(db.String(80), nullable=True)
    generation = db.Column(db.Integer, default=1)
    lineage_boost = db.Column(db.Float, default=0.0)
    sire_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    dam_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    retired_into_heritage = db.Column(db.Boolean, default=False)

    owner = db.relationship('User', backref=db.backref('pigs', lazy=True))

    __table_args__ = (
        db.Index('ix_pig_user_alive', 'user_id', 'is_alive'),
    )

    @property
    def avatar_url(self):
        if self.avatar and self.avatar.filename:
            return f'/static/avatars/{self.avatar.filename}'
        return None

    @property
    def races_remaining(self) -> int:
        return max(0, (self.max_races or PIG_DEFAULTS.max_races) - self.races_entered)

    @property
    def can_race(self) -> bool:
        return (
            self.is_alive
            and not self.is_injured
            and self.energy > PIG_INTERACTION_RULES.race_ready_energy_threshold
            and self.hunger > PIG_INTERACTION_RULES.race_ready_hunger_threshold
        )

    @property
    def can_train(self) -> bool:
        return self.is_alive and not self.is_injured

    @property
    def can_school(self) -> bool:
        return self.is_alive and not self.is_injured

    def apply_stat_boosts(self, stats: dict):
        for stat, boost in stats.items():
            current = getattr(self, stat, None)
            if current is not None:
                setattr(self, stat, min(PIG_LIMITS.max_value, current + boost))

    def reset_freshness(self):
        self.freshness = PIG_DEFAULTS.freshness

    def register_positive_interaction(self, interacted_at: datetime | None = None):
        interaction_time = interacted_at or datetime.utcnow()
        previous_interaction = self.last_interaction_at or self.last_updated or self.created_at
        if previous_interaction and (
            interaction_time - previous_interaction
        ) > timedelta(hours=PIG_INTERACTION_RULES.comeback_bonus_idle_hours):
            self.comeback_bonus_ready = True
        self.last_interaction_at = interaction_time
        self.last_updated = interaction_time
        self.reset_freshness()

    def mark_bad_state_if_needed(self):
        if (
            (self.hunger or 0) < PIG_INTERACTION_RULES.bad_state_hunger_threshold
            or (self.energy or 0) < PIG_INTERACTION_RULES.bad_state_energy_threshold
        ):
            self.ever_bad_state = True

    def heal(self):
        self.is_injured = False
        self.vet_deadline = None

    def injure(self, deadline: datetime):
        self.is_injured = True
        self.vet_deadline = deadline


class UserCerealInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    cereal_key = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'cereal_key', name='uq_user_cereal'),
    )


class Trophy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    trophy_key = db.Column(db.String(50), nullable=True)
    code = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='🏆')
    description = db.Column(db.String(255), nullable=False)
    pig_name = db.Column(db.String(80), nullable=True)
    date_earned = db.Column(db.DateTime, nullable=True, index=True)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'code', name='ux_trophy_user_code'),
    )

    @classmethod
    def award(
        cls,
        user_id: int,
        code: str,
        label: str,
        emoji: str,
        description: str,
        pig_name: str | None = None,
    ):
        trophy = cls.query.filter_by(user_id=user_id, code=code).first()
        if trophy:
            return trophy
        trophy = cls(
            user_id=user_id,
            trophy_key=code,
            code=code,
            label=label,
            emoji=emoji,
            description=description,
            pig_name=pig_name,
            date_earned=datetime.utcnow(),
        )
        db.session.add(trophy)
        return trophy


class PigAvatar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    filename = db.Column(db.String(100), nullable=False, unique=True)
    format = db.Column(db.String(10), nullable=False, default='png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
