"""Market unlock helpers."""

from datetime import datetime
import math

from models import Pig


def get_market_unlock_progress(user):
    total_races = sum(p.races_entered for p in Pig.query.filter_by(user_id=user.id).all())
    account_age_hours = (
        (datetime.utcnow() - user.created_at).total_seconds() / 3600
    ) if user.created_at else 0
    unlocked = account_age_hours >= 24 or total_races >= 3
    return unlocked, total_races, account_age_hours


def get_market_lock_reason(user):
    unlocked, total_races, account_age_hours = get_market_unlock_progress(user)
    if unlocked:
        return None
    remaining_races = max(0, 3 - total_races)
    remaining_hours = max(0, int(math.ceil(24 - account_age_hours)))
    return (
        f"Le marché se débloque après 3 courses disputées ou 24h d'ancienneté. "
        f"Il te reste {remaining_races} course(s) ou environ {remaining_hours}h."
    )
