from datetime import datetime, timedelta
import json
import random

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
    bets = db.relationship('Bet', backref='user', lazy=True)
    balance_transactions = db.relationship('BalanceTransaction', backref='user', lazy=True)
    course_plans = db.relationship('CoursePlan', backref='user', lazy=True)
    trophies = db.relationship('Trophy', backref='user', lazy=True, cascade='all, delete-orphan')

    # ── Méthodes métier ─────────────────────────────────────────────────

    def can_afford(self, amount: float) -> bool:
        """Vérifie si l'utilisateur a assez de BitGroins."""
        return (self.balance or 0.0) >= amount

    def pay(self, amount: float, reason_code: str = 'debit',
            reason_label: str = 'Débit BitGroins', details: str = None,
            reference_type: str = None, reference_id: int = None) -> bool:
        """Débite le solde de manière atomique (SQL UPDATE + transaction).
        Renvoie False si le solde est insuffisant."""
        from services.finance_service import debit_user_balance
        return debit_user_balance(
            self.id, amount,
            reason_code=reason_code, reason_label=reason_label,
            details=details, reference_type=reference_type,
            reference_id=reference_id,
        )

    def earn(self, amount: float, reason_code: str = 'credit',
             reason_label: str = 'Crédit BitGroins', details: str = None,
             reference_type: str = None, reference_id: int = None) -> bool:
        """Crédite le solde de manière atomique (SQL UPDATE + transaction)."""
        from services.finance_service import credit_user_balance
        return credit_user_balance(
            self.id, amount,
            reason_code=reason_code, reason_label=reason_label,
            details=details, reference_type=reference_type,
            reference_id=reference_id,
        )

    def claim_daily_reward(self) -> float:
        """Verse la prime de pointage journalière si elle n'a pas encore été
        réclamée aujourd'hui. Renvoie le montant crédité (0 si déjà perçue)."""
        from data import DAILY_LOGIN_REWARD
        today = datetime.utcnow().date()
        if self.last_daily_reward_at and self.last_daily_reward_at.date() >= today:
            return 0.0
        # Marquer AVANT earn() pour eviter le double-credit en cas de race condition
        self.last_daily_reward_at = datetime.utcnow()
        db.session.flush()  # Persiste le timestamp dans la transaction
        self.earn(
            DAILY_LOGIN_REWARD,
            reason_code='daily_reward',
            reason_label='Prime de pointage journalière',
        )
        # Refresh le solde en memoire (earn() fait un SQL UPDATE atomique)
        db.session.refresh(self)
        return DAILY_LOGIN_REWARD

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
        from services.race_service import get_user_weekly_bet_count
        from data import WEEKLY_BACON_TICKETS
        # Utiliser datetime.utcnow() pour correspondre aux dates de paris en DB
        count = get_user_weekly_bet_count(self, datetime.utcnow())
        return max(0, WEEKLY_BACON_TICKETS - count)


class Pig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False, default='Mon Cochon')
    emoji = db.Column(db.String(10), default='🐷')
    avatar_id = db.Column(db.Integer, db.ForeignKey('pig_avatar.id'), nullable=True)
    avatar = db.relationship('PigAvatar', lazy='joined')

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
    freshness = db.Column(db.Float, default=100.0)
    ever_bad_state = db.Column(db.Boolean, default=False)

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
    last_interaction_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    comeback_bonus_ready = db.Column(db.Boolean, default=False)

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
        return max(0, (self.max_races or 80) - self.races_entered)

    @property
    def can_race(self) -> bool:
        """Le cochon est-il apte à courir ?"""
        return (self.is_alive and not self.is_injured
                and self.energy > 20 and self.hunger > 20)

    @property
    def can_train(self) -> bool:
        """Le cochon peut-il s'entraîner ? (vivant, pas blessé)"""
        return self.is_alive and not self.is_injured

    @property
    def can_school(self) -> bool:
        """Le cochon peut-il aller à l'école ? (vivant, pas blessé)"""
        return self.is_alive and not self.is_injured

    @property
    def ideal_weight(self) -> float:
        """Poids de forme calculé à partir des stats."""
        from services.pig_service import calculate_target_weight_kg
        return calculate_target_weight_kg(self)

    @property
    def power(self) -> float:
        """Puissance de course effective (stats + condition + poids)."""
        from helpers import calculate_pig_power
        return round(calculate_pig_power(self), 1)

    # ── Méthodes de mutation d'état ─────────────────────────────────────

    def apply_stat_boosts(self, stats: dict):
        """Applique un dictionnaire {stat_name: boost_value} en capant à 100."""
        for stat, boost in stats.items():
            current = getattr(self, stat, None)
            if current is not None:
                setattr(self, stat, min(100, current + boost))

    def adjust_weight(self, delta: float) -> float:
        """Modifie le poids avec clamping min/max. Renvoie le nouveau poids."""
        from data import MIN_PIG_WEIGHT_KG, MAX_PIG_WEIGHT_KG, DEFAULT_PIG_WEIGHT_KG
        w = (self.weight_kg or DEFAULT_PIG_WEIGHT_KG) + delta
        self.weight_kg = round(min(MAX_PIG_WEIGHT_KG, max(MIN_PIG_WEIGHT_KG, w)), 1)
        return self.weight_kg

    def check_level_up(self):
        """Monte de niveau tant que l'XP le permet (+10 bonheur par level)."""
        from helpers import xp_for_level
        while self.xp >= xp_for_level(self.level + 1):
            self.level += 1
            self.happiness = min(100, self.happiness + 10)

    def reset_freshness(self):
        """Remet la fraicheur a fond apres une interaction positive."""
        self.freshness = 100.0

    def register_positive_interaction(self, interacted_at: datetime | None = None):
        """Enregistre une interaction joueur et prepare le bonus de retrouvailles."""
        interaction_time = interacted_at or datetime.utcnow()
        previous_interaction = self.last_interaction_at or self.last_updated or self.created_at
        if previous_interaction and (interaction_time - previous_interaction).total_seconds() > 3 * 24 * 3600:
            self.comeback_bonus_ready = True
        self.last_interaction_at = interaction_time
        self.last_updated = interaction_time
        self.reset_freshness()

    def award_longevity_trophies(self):
        """Attribue un trophee par mois reel de vie."""
        if not self.owner or not self.created_at:
            return
        months_alive = max(0, (datetime.utcnow() - self.created_at).days // 30)
        for month_index in range(1, months_alive + 1):
            Trophy.award(
                user_id=self.owner.id,
                code=f'ancient_one_month_{month_index}',
                label="L'Ancien",
                emoji='🕰️',
                description=f"{self.name} a traverse {month_index} mois reel(s) de bureau sans quitter la porcherie.",
                pig_name=self.name,
            )

    def mark_bad_state_if_needed(self):
        """Memorise si le cochon est deja passe par un mauvais etat."""
        if (self.hunger or 0) < 20 or (self.energy or 0) < 20:
            self.ever_bad_state = True

    def maybe_award_memorial_trophies(self):
        """Attribue les trophees memoriels lies a la fin de carriere."""
        if not self.owner:
            return
        if self.created_at and (datetime.utcnow() - self.created_at).days >= 30:
            Trophy.award(
                user_id=self.owner.id,
                code='office_elder',
                label="L'Ancien du Bureau",
                emoji='🗄️',
                description='Un cochon a tenu plus de 30 jours reels avant son post-mortem.',
                pig_name=self.name,
            )
        if self.created_at and (datetime.utcnow() - self.created_at).days >= 90:
            Trophy.award(
                user_id=self.owner.id,
                code='office_pillar',
                label='Le Pilier de Bureau',
                emoji='🪑',
                description='Un cochon a tenu plus de 3 mois reels avant de quitter la piste.',
                pig_name=self.name,
            )
        if (self.max_races and self.races_entered >= self.max_races and not self.ever_bad_state):
            Trophy.award(
                user_id=self.owner.id,
                code='golden_retirement',
                label='Retraite Doree',
                emoji='☕',
                description="Atteindre la limite de courses sans jamais tomber en mauvais etat.",
                pig_name=self.name,
            )
        winning_track_profiles = self.get_winning_track_profiles()
        if len(winning_track_profiles) >= 3:
            Trophy.award(
                user_id=self.owner.id,
                code='segment_expert',
                label='Expert des Segments',
                emoji='🧭',
                description='Ce cochon a gagne sur 3 profils de piste differents.',
                pig_name=self.name,
            )
        if (self.school_sessions_completed or 0) > 20:
            Trophy.award(
                user_id=self.owner.id,
                code='iron_memory',
                label='Memoire de Fer',
                emoji='🧠',
                description="Plus de 20 passages a l'ecole porcine avant la fin de carriere.",
                pig_name=self.name,
            )

    def get_winning_track_profiles(self) -> set[str]:
        if not self.id:
            return set()
        winning_rows = (
            db.session.query(Race.replay_json)
            .join(Participant, Participant.race_id == Race.id)
            .filter(
                Participant.pig_id == self.id,
                Participant.finish_position == 1,
                Race.status == 'finished',
            )
            .all()
        )
        profiles = set()
        for (replay_json,) in winning_rows:
            if not replay_json:
                continue
            try:
                replay = json.loads(replay_json)
            except (TypeError, ValueError):
                continue
            if isinstance(replay, dict) and replay.get('track_profile'):
                profiles.add(replay['track_profile'])
        return profiles

    def feed(self, cereal: dict):
        """Nourrir le cochon avec une céréale (dict issu de data.CEREALS).
        Met à jour faim, énergie, poids, stats et timestamps."""
        self.hunger = min(100, self.hunger + cereal['hunger_restore'])
        self.energy = min(100, self.energy + cereal.get('energy_restore', 0))
        self.adjust_weight(cereal.get('weight_delta', 0.0))
        self.apply_stat_boosts(cereal.get('stats', {}))
        self.last_fed_at = datetime.utcnow()
        self.register_positive_interaction(self.last_fed_at)
        self.mark_bad_state_if_needed()

    def train(self, training: dict):
        """Entraîner le cochon (dict issu de data.TRAININGS).
        Consomme énergie/faim, modifie poids, stats et bonheur."""
        self.energy = max(0, min(100, self.energy - training['energy_cost']))
        self.hunger = max(0, self.hunger - training.get('hunger_cost', 0))
        self.adjust_weight(training.get('weight_delta', 0.0))
        if 'happiness_bonus' in training:
            self.happiness = min(100, self.happiness + training['happiness_bonus'])
        self.apply_stat_boosts(training.get('stats', {}))
        self.register_positive_interaction(datetime.utcnow())
        self.mark_bad_state_if_needed()

    def study(self, lesson: dict, correct: bool) -> str:
        """Suivre un cours (dict issu de data.SCHOOL_LESSONS).
        Renvoie 'success' ou 'warning' selon la réponse."""
        self.energy = max(0, self.energy - lesson['energy_cost'])
        self.hunger = max(0, self.hunger - lesson['hunger_cost'])
        self.last_school_at = datetime.utcnow()
        self.school_sessions_completed = (self.school_sessions_completed or 0) + 1

        if correct:
            self.apply_stat_boosts(lesson.get('stats', {}))
            self.xp += lesson['xp']
            self.happiness = min(100, self.happiness + lesson.get('happiness_bonus', 0))
            category = 'success'
        else:
            self.xp += lesson.get('wrong_xp', 0)
            self.happiness = max(0, self.happiness - lesson.get('wrong_happiness_penalty', 0))
            category = 'warning'

        self.register_positive_interaction(datetime.utcnow())
        self.mark_bad_state_if_needed()
        self.check_level_up()
        return category

    def heal(self):
        """Soigne le cochon : retire blessure et deadline vétérinaire."""
        self.is_injured = False
        self.vet_deadline = None

    def injure(self, deadline: datetime):
        """Blesse le cochon avec une deadline vétérinaire."""
        self.is_injured = True
        self.vet_deadline = deadline

    def kill(self, cause: str = 'abattoir'):
        """Tue le cochon et le transforme en charcuterie."""
        from data import CHARCUTERIE, EPITAPHS
        charcuterie = random.choice(CHARCUTERIE)
        epitaph_template = random.choice(EPITAPHS)
        self.is_alive = False
        self.is_injured = False
        self.vet_deadline = None
        self.death_date = datetime.utcnow()
        self.death_cause = cause
        self.charcuterie_type = charcuterie['name']
        self.charcuterie_emoji = charcuterie['emoji']
        self.epitaph = epitaph_template.format(name=self.name, wins=self.races_won)
        self.challenge_mort_wager = 0
        self.maybe_award_memorial_trophies()

    def retire(self):
        """Retire le cochon pour vieillesse (charcuterie premium)."""
        from data import CHARCUTERIE_PREMIUM
        charcuterie = random.choice(CHARCUTERIE_PREMIUM)
        self.is_alive = False
        self.is_injured = False
        self.vet_deadline = None
        self.death_date = datetime.utcnow()
        self.death_cause = 'vieillesse'
        self.charcuterie_type = charcuterie['name']
        self.charcuterie_emoji = charcuterie['emoji']
        self.epitaph = (
            f"{self.name} a pris sa retraite après {self.races_entered} courses glorieuses. "
            f"Un cochon bien vieilli fait le meilleur jambon."
        )
        self.challenge_mort_wager = 0
        self.maybe_award_memorial_trophies()

    def update_vitals(self):
        """Décroissance Tamagotchi en fonction du temps écoulé.
        Appelé avant chaque interaction pour synchroniser l'état."""
        from utils.time_utils import calculate_weekend_truce_hours
        from data import DEFAULT_PIG_WEIGHT_KG

        now = datetime.utcnow()
        self.award_longevity_trophies()
        if not self.last_updated:
            self.last_updated = now
            return
        elapsed_hours = (now - self.last_updated).total_seconds() / 3600
        if elapsed_hours < 0.01:
            return
        truce_hours = calculate_weekend_truce_hours(self.last_updated, now)
        effective_hours = max(0.0, elapsed_hours - truce_hours)
        hours = min(effective_hours, 24)
        if effective_hours < 0.01:
            self.last_updated = now
            db.session.commit()
            return

        reference_interaction = self.last_interaction_at or self.last_updated
        if reference_interaction:
            grace_deadline = reference_interaction + timedelta(hours=48)
            if now > grace_deadline:
                elapsed_workdays = 0
                cursor = grace_deadline.date()
                while cursor <= now.date():
                    if cursor.weekday() < 5:
                        elapsed_workdays += 1
                    cursor += timedelta(days=1)
                self.freshness = max(0.0, 100.0 - (elapsed_workdays * 5.0))
            else:
                self.freshness = 100.0

        # Faim décroît avec le temps
        self.hunger = max(0, self.hunger - hours * 2)

        # Énergie dépend de la faim
        if self.hunger > 30:
            self.energy = min(100, self.energy + hours * 5)
        else:
            self.energy = max(0, self.energy - hours * 1)

        # Bonheur dépend de la faim
        if self.hunger < 15:
            self.happiness = max(0, self.happiness - hours * 3)
        elif self.hunger < 30:
            self.happiness = max(0, self.happiness - hours * 1)
        elif self.happiness < 60:
            self.happiness = min(60, self.happiness + hours * 0.3)

        # Poids fluctue selon faim/énergie
        current_weight = self.weight_kg or DEFAULT_PIG_WEIGHT_KG
        if self.hunger < 25:
            self.weight_kg = round(min(190.0, max(75.0, current_weight - hours * 0.25)), 1)
        elif self.hunger > 75 and self.energy < 45:
            self.weight_kg = round(min(190.0, max(75.0, current_weight + hours * 0.18)), 1)
        elif self.energy > 80 and self.hunger < 60:
            self.weight_kg = round(min(190.0, max(75.0, current_weight - hours * 0.08)), 1)

        self.mark_bad_state_if_needed()
        self.last_updated = now
        db.session.commit()



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
