"""Veterinary, abattoir and pig death helpers."""

from datetime import datetime

from models import Pig
from services.pig_service import kill_pig, retire_pig


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
            kill_pig(pig, cause='blessure', commit=False)


def send_to_abattoir(pig, cause='abattoir', commit=True):
    kill_pig(pig, cause=cause, commit=commit)


def retire_pig_old_age(pig, commit=True):
    retire_pig(pig, commit=commit)


def get_dead_pigs_abattoir():
    return Pig.query.filter_by(is_alive=False).order_by(Pig.death_date.desc()).all()


def get_legendary_pigs():
    return Pig.query.filter(
        Pig.is_alive == False,
        Pig.races_won >= 3,
    ).order_by(Pig.races_won.desc()).all()
