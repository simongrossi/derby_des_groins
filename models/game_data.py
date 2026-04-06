from datetime import datetime
import json

from extensions import db
from models.user import User

class AcademieScore(db.Model):
    __tablename__ = 'academie_score'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word = db.Column(db.String(80), nullable=False)
    time_taken = db.Column(db.Float, nullable=False)
    errors = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('academie_scores', lazy=True, cascade='all, delete-orphan'))



class CerealItem(db.Model):
    __tablename__ = 'cereal_item'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='🌾')
    cost = db.Column(db.Float, nullable=False, default=5.0)
    description = db.Column(db.String(200), default='')
    hunger_restore = db.Column(db.Float, default=20.0)
    energy_restore = db.Column(db.Float, default=5.0)
    weight_delta = db.Column(db.Float, default=0.0)
    valeur_fourragere = db.Column(db.Float, default=100.0)
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        stats = {}
        for stat_name in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            stat_value = getattr(self, f'stat_{stat_name}') or 0.0
            if stat_value:
                stats[stat_name] = stat_value
        return {
            'name': self.name,
            'emoji': self.emoji,
            'cost': self.cost,
            'description': self.description or '',
            'hunger_restore': self.hunger_restore or 0,
            'energy_restore': self.energy_restore or 0,
            'stats': stats,
            'weight_delta': self.weight_delta or 0,
            'valeur_fourragere': self.valeur_fourragere or 100,
        }


class TrainingItem(db.Model):
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
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        stats = {}
        for stat_name in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            stat_value = getattr(self, f'stat_{stat_name}') or 0.0
            if stat_value:
                stats[stat_name] = stat_value
        data = {
            'name': self.name,
            'emoji': self.emoji,
            'description': self.description or '',
            'energy_cost': self.energy_cost or 0,
            'hunger_cost': self.hunger_cost or 0,
            'stats': stats,
            'weight_delta': self.weight_delta or 0,
            'min_happiness': self.min_happiness or 0,
        }
        if self.happiness_bonus:
            data['happiness_bonus'] = self.happiness_bonus
        return data


class SchoolLessonItem(db.Model):
    __tablename__ = 'school_lesson_item'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10), nullable=False, default='📚')
    description = db.Column(db.String(300), default='')
    question = db.Column(db.String(300), nullable=False)
    answers_json = db.Column(db.Text, nullable=False, default='[]')
    stat_vitesse = db.Column(db.Float, default=0.0)
    stat_endurance = db.Column(db.Float, default=0.0)
    stat_agilite = db.Column(db.Float, default=0.0)
    stat_force = db.Column(db.Float, default=0.0)
    stat_intelligence = db.Column(db.Float, default=0.0)
    stat_moral = db.Column(db.Float, default=0.0)
    xp = db.Column(db.Integer, default=20)
    wrong_xp = db.Column(db.Integer, default=5)
    energy_cost = db.Column(db.Integer, default=10)
    hunger_cost = db.Column(db.Integer, default=4)
    min_happiness = db.Column(db.Integer, default=15)
    happiness_bonus = db.Column(db.Integer, default=5)
    wrong_happiness_penalty = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime, nullable=True)
    available_until = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    @property
    def answers(self):
        try:
            return json.loads(self.answers_json) if self.answers_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    @answers.setter
    def answers(self, value):
        self.answers_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        stats = {}
        for stat_name in ('vitesse', 'endurance', 'agilite', 'force', 'intelligence', 'moral'):
            stat_value = getattr(self, f'stat_{stat_name}') or 0.0
            if stat_value:
                stats[stat_name] = stat_value
        return {
            'name': self.name,
            'emoji': self.emoji,
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
    __tablename__ = 'hangman_word_item'

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
