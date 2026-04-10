"""Veterinary, abattoir and pig death helpers."""

from datetime import datetime, timedelta

from models import Pig
from services.pig_power_service import get_pig_settings
from services.pig_service import kill_pig, retire_pig
from utils.time_utils import is_weekend_truce_active


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
    if is_weekend_truce_active():
        return
    now = datetime.utcnow()
    _ps = get_pig_settings()
    grace_delta = timedelta(minutes=_ps.vet_grace_minutes)
    injured_pigs = Pig.query.filter_by(is_injured=True, is_alive=True).all()
    for pig in injured_pigs:
        if pig.vet_deadline and now > pig.vet_deadline + grace_delta:
            kill_pig(pig, cause='blessure', commit=False)


def get_vet_window_seconds():
    return max(60, int(get_pig_settings().vet_response_minutes) * 60)


def get_vet_care_costs(base_energy_cost, base_happiness_cost, seconds_left):
    total_window = get_vet_window_seconds()
    remaining_ratio = max(0.0, min(1.0, float(seconds_left or 0) / float(total_window)))
    elapsed_ratio = 1.0 - remaining_ratio
    return {
        'energy_cost': round(float(base_energy_cost) * (1.0 + elapsed_ratio), 1),
        'happiness_cost': round(float(base_happiness_cost) * (1.0 + (elapsed_ratio * 2.0)), 1),
        'severity_ratio': round(elapsed_ratio, 3),
    }


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
