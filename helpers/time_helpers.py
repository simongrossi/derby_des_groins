"""Time-related utility helpers."""

from datetime import datetime


def get_cooldown_remaining(last_action, minutes):
    if not last_action:
        return 0
    elapsed = (datetime.utcnow() - last_action).total_seconds()
    return max(0, int(minutes * 60 - elapsed))


def format_duration_short(total_seconds):
    total_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    if minutes and seconds:
        return f"{minutes}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def get_seconds_until(deadline):
    if not deadline:
        return 0
    return max(0, int((deadline - datetime.utcnow()).total_seconds()))
