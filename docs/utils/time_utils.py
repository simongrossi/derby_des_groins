from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo('Europe/Paris')
WEEKEND_TRUCE_START = time(18, 0)
WEEKEND_TRUCE_END = time(8, 0)
WEEKEND_TRUCE_DURATION = timedelta(days=2, hours=14)


def get_paris_now():
    return datetime.now(PARIS_TZ)


def to_paris_time(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(PARIS_TZ)
    return dt.astimezone(PARIS_TZ)


def is_weekend_truce_active(moment=None):
    local_moment = to_paris_time(moment or datetime.utcnow())
    weekday = local_moment.weekday()
    local_time = local_moment.time()
    if weekday == 4 and local_time >= WEEKEND_TRUCE_START:
        return True
    if weekday in (5, 6):
        return True
    if weekday == 0 and local_time < WEEKEND_TRUCE_END:
        return True
    return False


def _next_weekend_truce_start(after_local):
    candidate_day = after_local.date()
    days_until_friday = (4 - after_local.weekday()) % 7
    candidate_day = candidate_day + timedelta(days=days_until_friday)
    candidate_start = datetime.combine(candidate_day, WEEKEND_TRUCE_START, tzinfo=PARIS_TZ)
    if candidate_start <= after_local:
        candidate_start += timedelta(days=7)
    return candidate_start


def _get_current_truce_window_start(local_moment):
    weekday = local_moment.weekday()
    if weekday == 4:
        delta_days = 0
    elif weekday == 5:
        delta_days = 1
    elif weekday == 6:
        delta_days = 2
    else:
        delta_days = 3
    return datetime.combine(
        local_moment.date() - timedelta(days=delta_days),
        WEEKEND_TRUCE_START,
        tzinfo=PARIS_TZ,
    )


def calculate_weekend_truce_hours(start_dt, end_dt):
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0.0

    start_local = to_paris_time(start_dt)
    end_local = to_paris_time(end_dt)
    overlap_seconds = 0.0

    if is_weekend_truce_active(start_local):
        truce_start = _get_current_truce_window_start(start_local)
        truce_end = truce_start + WEEKEND_TRUCE_DURATION
        overlap_seconds += (min(end_local, truce_end) - start_local).total_seconds()
        cursor = truce_end
    else:
        cursor = start_local

    while cursor < end_local:
        truce_start = _next_weekend_truce_start(cursor)
        if truce_start >= end_local:
            break
        truce_end = truce_start + WEEKEND_TRUCE_DURATION
        overlap_seconds += (min(end_local, truce_end) - truce_start).total_seconds()
        cursor = truce_end

    return max(0.0, overlap_seconds / 3600.0)
