"""Veterinary, abattoir and pig death helpers."""

from datetime import datetime
import random

from extensions import db
from models import Pig
from data import CHARCUTERIE, CHARCUTERIE_PREMIUM, EPITAPHS


def get_first_injured_pig(user_id):
    if not user_id:
        return None
    return (
        Pig.query
        .filter_by(user_id=user_id, is_alive=True, is_injured=True)
        .order_by(Pig.vet_deadline.asc(), Pig.id.asc())
        .first()
    )


def check_vet_deadlines():
    now = datetime.utcnow()
    injured_pigs = Pig.query.filter_by(is_injured=True, is_alive=True).all()
    for pig in injured_pigs:
        if pig.vet_deadline and now > pig.vet_deadline:
            pig.kill(cause='blessure')


def send_to_abattoir(pig, cause='abattoir', commit=True):
    charcuterie = random.choice(CHARCUTERIE)
    epitaph_template = random.choice(EPITAPHS)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = cause
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = epitaph_template.format(name=pig.name, wins=pig.races_won)
    pig.challenge_mort_wager = 0
    if commit:
        db.session.commit()


def retire_pig_old_age(pig, commit=True):
    charcuterie = random.choice(CHARCUTERIE_PREMIUM)
    pig.is_alive = False
    pig.is_injured = False
    pig.vet_deadline = None
    pig.death_date = datetime.utcnow()
    pig.death_cause = 'vieillesse'
    pig.charcuterie_type = charcuterie['name']
    pig.charcuterie_emoji = charcuterie['emoji']
    pig.epitaph = (
        f"{pig.name} a pris sa retraite après {pig.races_entered} courses glorieuses. "
        "Un cochon bien vieilli fait le meilleur jambon."
    )
    pig.challenge_mort_wager = 0
    db.session.commit()


def get_dead_pigs_abattoir():
    return Pig.query.filter_by(is_alive=False).order_by(Pig.death_date.desc()).all()


def get_legendary_pigs():
    return Pig.query.filter(
        Pig.is_alive == False,
        Pig.races_won >= 3,
    ).order_by(Pig.races_won.desc()).all()
