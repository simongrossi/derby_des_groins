from models import UserNotification
from extensions import db


def push_user_notification(user_id: int, title: str, message: str, category: str = 'info', event_key: str | None = None):
    """Create a user-facing real-time toast notification.

    event_key can be used to deduplicate periodic/critical events.
    """
    if not user_id or not title or not message:
        return None

    if event_key:
        already_exists = UserNotification.query.filter_by(user_id=user_id, event_key=event_key).first()
        if already_exists:
            return already_exists

    notif = UserNotification(
        user_id=user_id,
        category=category or 'info',
        title=title[:120],
        message=message[:280],
        event_key=event_key,
    )
    db.session.add(notif)
    return notif
