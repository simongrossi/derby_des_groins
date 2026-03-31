"""Database utility helpers — row-level locking."""

from extensions import db


def supports_row_level_locking():
    try:
        return db.engine.dialect.name != 'sqlite'
    except Exception:
        return False


def apply_row_lock(query):
    if supports_row_level_locking():
        return query.with_for_update()
    return query
