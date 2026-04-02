from datetime import datetime, timedelta

from flask import request

from extensions import db
from models import AuthEventLog


def _extract_client_ip() -> str:
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        first_ip = forwarded_for.split(',')[0].strip()
        if first_ip:
            return first_ip
    return (request.headers.get('X-Real-IP') or request.remote_addr or '0.0.0.0').strip()


def log_auth_event(
    *,
    event_type: str,
    is_success: bool,
    user_id: int | None = None,
    username_attempt: str | None = None,
    details: str | None = None,
) -> None:
    """Persiste un événement d'auth pour audit et sécurité."""
    entry = AuthEventLog(
        event_type=event_type,
        is_success=bool(is_success),
        user_id=user_id,
        username_attempt=(username_attempt or None),
        ip_address=_extract_client_ip(),
        user_agent=(request.user_agent.string[:300] if request.user_agent else None),
        route=request.path[:120] if request.path else None,
        details=details[:255] if details else None,
    )
    db.session.add(entry)
    db.session.flush()


def purge_old_auth_events(retention_days: int) -> int:
    """Supprime les logs auth plus anciens que la fenêtre de rétention."""
    safe_days = max(1, int(retention_days or 1))
    threshold = datetime.utcnow() - timedelta(days=safe_days)
    deleted = AuthEventLog.query.filter(AuthEventLog.occurred_at < threshold).delete(synchronize_session=False)
    db.session.commit()
    return int(deleted or 0)
