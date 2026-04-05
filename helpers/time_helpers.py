"""Time-related utility helpers."""

from datetime import datetime


def get_cooldown_remaining(last_action, minutes):
    if not last_action:
        return 0
    elapsed = (datetime.utcnow() - last_action).total_seconds()
    return max(0, int(minutes * 60 - elapsed))


def format_duration_short(total_seconds):
    total_seconds = max(0, int(total_seconds))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{days}j {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes and seconds:
        return f"{minutes}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def get_seconds_until(deadline):
    if not deadline:
        return 0
    return max(0, int((deadline - datetime.utcnow()).total_seconds()))
