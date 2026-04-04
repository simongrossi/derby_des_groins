from datetime import datetime, timedelta
import json

from config.game_rules import PIG_DEFAULTS, PIG_INTERACTION_RULES, PIG_LIMITS
from data import WEEKLY_BACON_TICKETS
from extensions import db


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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

    # ── Méthodes métier ─────────────────────────────────────────────────

    def can_afford(self, amount: float) -> bool:
        """Vérifie si l'utilisateur a assez de BitGroins."""
        return (self.balance or 0.0) >= amount

    @property
    def active_pigs(self):
        """Liste des cochons vivants de l'utilisateur."""
        return Pig.query.filter_by(user_id=self.id, is_alive=True).all()

    @property
    def pig_count(self) -> int:
        """Nombre de cochons vivants."""
        return Pig.query.filter_by(user_id=self.id, is_alive=True).count()

    @property
    def bacon_tickets(self) -> int:
        """Nombre de tickets bacon (quota de paris hebdo) restants."""
        current_dt = datetime.utcnow()
        week_start = datetime.combine((current_dt - timedelta(days=current_dt.weekday())).date(), datetime.min.time())
        week_end = week_start + timedelta(days=7)
        weekly_limit_entry = GameConfig.query.filter_by(key='economy_weekly_bacon_tickets').first()
        try:
            weekly_limit = int(float(weekly_limit_entry.value)) if weekly_limit_entry else int(WEEKLY_BACON_TICKETS)
        except (TypeError, ValueError):
            weekly_limit = int(WEEKLY_BACON_TICKETS)
        count = Bet.query.filter(
            Bet.user_id == self.id,
            Bet.placed_at >= week_start,
            Bet.placed_at < week_end,
        ).count()
        return max(0, weekly_limit - count)


class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False, default='Mon Cochon')
    emoji = db.Column(db.String(10), default='🐷')
    avatar_id = db.Column(db.Integer, db.ForeignKey('pig_avatar.id'), nullable=True)
    avatar = db.relationship('PigAvatar', lazy='joined')

    # Compétences (0-100)
    vitesse = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    endurance = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    agilite = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    force = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    intelligence = db.Column(db.Float, default=PIG_DEFAULTS.stat)
    moral = db.Column(db.Float, default=PIG_DEFAULTS.stat)

    # État Tamagotchi (0-100)
    energy = db.Column(db.Float, default=PIG_DEFAULTS.energy)
    hunger = db.Column(db.Float, default=PIG_DEFAULTS.hunger)
    happiness = db.Column(db.Float, default=PIG_DEFAULTS.happiness)
    weight_kg = db.Column(db.Float, default=PIG_DEFAULTS.weight_kg)
    freshness = db.Column(db.Float, default=PIG_DEFAULTS.freshness)
    ever_bad_state = db.Column(db.Boolean, default=False)

    # Progression
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    races_won = db.Column(db.Integer, default=0)
    races_entered = db.Column(db.Integer, default=0)
    school_sessions_completed = db.Column(db.Integer, default=0)

    # Durée de vie & Rareté & Origine
    max_races = db.Column(db.Integer, default=PIG_DEFAULTS.max_races)
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
    injury_risk = db.Column(db.Float, default=PIG_DEFAULTS.injury_risk)
    vet_deadline = db.Column(db.DateTime, nullable=True)

    # Timestamps
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

    # ── Propriétés calculées ────────────────────────────────────────────

    @property
    def avatar_url(self):
        if self.avatar and self.avatar.filename:
            return f'/static/avatars/{self.avatar.filename}'
        return None

    @property
    def races_remaining(self) -> int:
        """Nombre de courses restantes avant la retraite."""
        return max(0, (self.max_races or PIG_DEFAULTS.max_races) - self.races_entered)

    @property
    def can_race(self) -> bool:
        """Le cochon est-il apte à courir ?"""
        return (self.is_alive and not self.is_injured
                and self.energy > PIG_INTERACTION_RULES.race_ready_energy_threshold
                and self.hunger > PIG_INTERACTION_RULES.race_ready_hunger_threshold)

    @property
    def can_train(self) -> bool:
        """Le cochon peut-il s'entraîner ? (vivant, pas blessé)"""
        return self.is_alive and not self.is_injured

    @property
    def can_school(self) -> bool:
        """Le cochon peut-il aller à l'école ? (vivant, pas blessé)"""
        return self.is_alive and not self.is_injured

    # ── Méthodes de mutation d'état simples ─────────────────────────────

    def apply_stat_boosts(self, stats: dict):
        """Applique un dictionnaire {stat_name: boost_value} en capant à 100."""
        for stat, boost in stats.items():
            current = getattr(self, stat, None)
            if current is not None:
                setattr(self, stat, min(PIG_LIMITS.max_value, current + boost))

    def reset_freshness(self):
        """Remet la fraicheur a fond apres une interaction positive."""
        self.freshness = PIG_DEFAULTS.freshness

    def register_positive_interaction(self, interacted_at: datetime | None = None):
        """Enregistre une interaction joueur et prepare le bonus de retrouvailles."""
        interaction_time = interacted_at or datetime.utcnow()
        previous_interaction = self.last_interaction_at or self.last_updated or self.created_at
        if previous_interaction and (interaction_time - previous_interaction) > timedelta(hours=PIG_INTERACTION_RULES.comeback_bonus_idle_hours):
            self.comeback_bonus_ready = True
        self.last_interaction_at = interaction_time
        self.last_updated = interaction_time
        self.reset_freshness()

    def mark_bad_state_if_needed(self):
        """Memorise si le cochon est deja passe par un mauvais etat."""
        if (
            (self.hunger or 0) < PIG_INTERACTION_RULES.bad_state_hunger_threshold
            or (self.energy or 0) < PIG_INTERACTION_RULES.bad_state_energy_threshold
        ):
            self.ever_bad_state = True

    def heal(self):
        """Soigne le cochon : retire blessure et deadline vétérinaire."""
        self.is_injured = False
        self.vet_deadline = None

    def injure(self, deadline: datetime):
        """Blesse le cochon avec une deadline vétérinaire."""
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
    def award(cls, user_id: int, code: str, label: str, emoji: str, description: str, pig_name: str | None = None):
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


class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    winner_name = db.Column(db.String(80), nullable=True)
    winner_odds = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='upcoming')
    replay_json = db.Column(db.Text, nullable=True) # Detailed history as JSON
    preview_segments_json = db.Column(db.Text, nullable=True)  # Segments pre-generated for circuit preview
    participants = db.relationship('Participant', backref='race', lazy=True)
    bets = db.relationship('Bet', backref='race', lazy=True)

    __table_args__ = (
        db.Index('ix_race_status_finished', 'status', 'finished_at'),
    )

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji      = db.Column(db.String(10), default='🐷')
    avatar_url = db.Column(db.String(500), nullable=True)
    odds = db.Column(db.Float, nullable=False)
    win_probability = db.Column(db.Float, nullable=False)
    finish_position = db.Column(db.Integer, nullable=True)
    pig_id = db.Column(db.Integer, db.ForeignKey('pig.id'), nullable=True)
    strategy = db.Column(db.Integer, default=50)  # 0 (Economy) to 100 (Full Attack)
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
        default='{"phase_1": 35, "phase_2": 50, "phase_3": 80}',
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @staticmethod
    def build_strategy_profile(phase_1=35, phase_2=50, phase_3=80) -> str:
        return json.dumps({
            'phase_1': int(phase_1),
            'phase_2': int(phase_2),
            'phase_3': int(phase_3),
        })

    @property
    def strategy_segments(self) -> dict:
        default_profile = {'phase_1': 35, 'phase_2': 50, 'phase_3': 80}
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

class GrainMarket(db.Model):
    """Singleton — etat partage de la Bourse aux Grains (une seule ligne, id=1)."""
    id = db.Column(db.Integer, primary_key=True)
    cursor_x = db.Column(db.Integer, default=3)           # 1-5 : axe prix
    cursor_y = db.Column(db.Integer, default=3)           # 1-5 : axe qualite
    vitrine_grain = db.Column(db.String(20), nullable=True)   # cle cereal bloquee (ex: 'mais')
    vitrine_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_move_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_move_at = db.Column(db.DateTime, nullable=True)
    last_purchase_at = db.Column(db.DateTime, nullable=True)
    total_transactions = db.Column(db.Integer, default=0)

    vitrine_user = db.relationship('User', foreign_keys=[vitrine_user_id])
    last_move_user = db.relationship('User', foreign_keys=[last_move_user_id])


class MarketHistory(db.Model):
    """Historique des prix de la Bourse."""
    id = db.Column(db.Integer, primary_key=True)
    cereal_key = db.Column(db.String(20), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    surcharge = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Cochon en vente
    pig_name = db.Column(db.String(80), nullable=False)
    pig_emoji      = db.Column(db.String(10), default='🐷')
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


class UserNotification(db.Model):
    __tablename__ = 'user_notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default='info')
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(280), nullable=False)
    event_key = db.Column(db.String(120), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))

# ══════════════════════════════════════════════════════════════════════════════
# Tables de données de jeu (éditables via l'admin sans redémarrage)
# ══════════════════════════════════════════════════════════════════════════════

class CerealItem(db.Model):
    """Céréale achetable pour nourrir un cochon."""
    __tablename__ = 'cereal_item'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(30), unique=True, nullable=False)       # 'mais', 'orge'...
    name = db.Column(db.String(50), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='🌾')
    cost = db.Column(db.Float, nullable=False, default=5.0)
    description = db.Column(db.String(200), default='')
    hunger_restore = db.Column(db.Float, default=20.0)
    energy_restore = db.Column(db.Float, default=5.0)
    weight_delta = db.Column(db.Float, default=0.0)
    valeur_fourragere = db.Column(db.Float, default=100.0)
    # Stats individuelles (plus simple qu'un JSON pour les formulaires admin)
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    # Saisonnalité & activation
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)   # None = toujours dispo
    available_until = db.Column(db.DateTime, nullable=True)   # None = pas de fin
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        """Retourne un dict identique au format data.CEREALS[key]."""
        stats = {}
        for s in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            v = getattr(self, f'stat_{s}') or 0.0
            if v:
                stats[s] = v
        return {
            'name': self.name, 'emoji': self.emoji, 'cost': self.cost,
            'description': self.description or '',
            'hunger_restore': self.hunger_restore or 0,
            'energy_restore': self.energy_restore or 0,
            'stats': stats,
            'weight_delta': self.weight_delta or 0,
            'valeur_fourragere': self.valeur_fourragere or 100,
        }


class TrainingItem(db.Model):
    """Entraînement disponible pour un cochon."""
    __tablename__ = 'training_item'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='💪')
    description = db.Column(db.String(200), default='')
    energy_cost = db.Column(db.Integer, default=25)
    hunger_cost = db.Column(db.Integer, default=10)
    weight_delta = db.Column(db.Float, default=0.0)
    min_happiness = db.Column(db.Integer, default=20)
    happiness_bonus = db.Column(db.Integer, default=0)
    # Stats
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    # Activation
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        """Retourne un dict identique au format data.TRAININGS[key]."""
        stats = {}
        for s in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            v = getattr(self, f'stat_{s}') or 0.0
            if v:
                stats[s] = v
        d = {
            'name': self.name, 'emoji': self.emoji,
            'description': self.description or '',
            'energy_cost': self.energy_cost or 0,
            'hunger_cost': self.hunger_cost or 0,
            'stats': stats,
            'weight_delta': self.weight_delta or 0,
            'min_happiness': self.min_happiness or 0,
        }
        if self.happiness_bonus:
            d['happiness_bonus'] = self.happiness_bonus
        return d


class SchoolLessonItem(db.Model):
    """Cours de l'école des groins."""
    __tablename__ = 'school_lesson_item'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='📚')
    description = db.Column(db.String(300), default='')
    question = db.Column(db.String(300), nullable=False)
    # Réponses stockées en JSON : [{text, correct, feedback}, ...]
    answers_json = db.Column(db.Text, nullable=False, default='[]')
    # Stats (bonne réponse)
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    # XP & coûts
    xp = db.Column(db.Integer, default=20)
    wrong_xp = db.Column(db.Integer, default=5)
    energy_cost = db.Column(db.Integer, default=10)
    hunger_cost = db.Column(db.Integer, default=4)
    min_happiness = db.Column(db.Integer, default=15)
    happiness_bonus = db.Column(db.Integer, default=5)
    wrong_happiness_penalty = db.Column(db.Integer, default=5)
    # Activation
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    @property
    def answers(self):
        """Liste des réponses parsée depuis le JSON."""
        try:
            return json.loads(self.answers_json) if self.answers_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @answers.setter
    def answers(self, value):
        self.answers_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        """Retourne un dict identique au format data.SCHOOL_LESSONS[key]."""
        stats = {}
        for s in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            v = getattr(self, f'stat_{s}') or 0.0
            if v:
                stats[s] = v
        return {
            'name': self.name, 'emoji': self.emoji,
            'description': self.description or '',
            'question': self.question,
            'answers': self.answers,
            'stats': stats,
            'xp': self.xp or 0,
            'wrong_xp': self.wrong_xp or 0,
            'energy_cost': self.energy_cost or 0,
            'hunger_cost': self.hunger_cost or 0,
            'min_happiness': self.min_happiness or 0,
            'happiness_bonus': self.happiness_bonus or 0,
            'wrong_happiness_penalty': self.wrong_happiness_penalty or 0,
        }


class HangmanWordItem(db.Model):
    """Mot utilisable dans le mini-jeu Cochon Pendu."""
    __tablename__ = 'hangman_word_item'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    slogan = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prix_truffes = db.Column(db.Float, default=0.0)
    prix_glands = db.Column(db.Float, default=0.0)
    type_effet = db.Column(db.String(50), nullable=True)
    valeur_effet = db.Column(db.Float, nullable=True)
    fiabilite = db.Column(db.Float, default=100.0)

    shop = db.relationship('Shop', backref=db.backref('items', lazy=True))

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref=db.backref('inventory_items', lazy=True))
    item = db.relationship('Item')

class MarketplaceListing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    prix_demande = db.Column(db.Float, nullable=False)
    date_mise_en_vente = db.Column(db.DateTime, default=datetime.utcnow)

    seller = db.relationship('User', backref=db.backref('market_listings', lazy=True))
    inventory_item = db.relationship('InventoryItem')


class PigAvatar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    filename = db.Column(db.String(100), nullable=False, unique=True)
    format = db.Column(db.String(10), nullable=False, default='png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuthEventLog(db.Model):
    """Journal des événements de connexion/authentification."""
    __tablename__ = 'auth_event_log'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(40), nullable=False)
    is_success = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    username_attempt = db.Column(db.String(80), nullable=True, index=True)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    user_agent = db.Column(db.String(300), nullable=True)
    route = db.Column(db.String(120), nullable=True)
    details = db.Column(db.String(255), nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('auth_events', lazy=True))

    __table_args__ = (
        db.Index('ix_auth_event_type_time', 'event_type', 'occurred_at'),
    )


# ──────────────────────────────────────────────────────────
# 🐷 GROIN POKER — modèles multijoueur
# ──────────────────────────────────────────────────────────

class PokerTable(db.Model):
    """Une table de poker — peut être en lobby, en vote, en jeu ou terminée."""
    __tablename__ = 'poker_table'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='lobby', nullable=False)
    # lobby | voting | playing | finished
    phase = db.Column(db.String(20), default='preflop', nullable=True)
    # preflop | flop | turn | river | showdown

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
    """Un joueur assis à une table de Groin Poker."""
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
    # waiting | active | spectator | left

    hole_json = db.Column(db.Text, default='[]')
    vote = db.Column(db.Integer, nullable=True)  # vote buy-in

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('poker_seats', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('table_id', 'seat', name='uq_poker_table_seat'),
    )


class PokerHandHistory(db.Model):
    """Historique des mains jouées."""
    __tablename__ = 'poker_hand_history'

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('poker_table.id'), nullable=False, index=True)
    hand_number = db.Column(db.Integer, nullable=False)
    pot = db.Column(db.Float, default=0.0)
    winner_ids = db.Column(db.Text, default='[]')
    hand_results = db.Column(db.Text, default='{}')
    community_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    """Messages du chat global."""
    __tablename__ = 'chat_message'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))
    replies = db.relationship('ChatMessage', backref=db.backref('parent', remote_side=[id]), lazy=True)

    def __repr__(self):
        return f'<ChatMessage {self.id} by {self.username}>'

    def to_dict(self):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'parent_id': self.parent_id
        }
        if self.parent:
            data['parent_context'] = {
                'username': self.parent.username,
                'message': self.parent.message[:50] + ('...' if len(self.parent.message) > 50 else '')
            }
        return data
