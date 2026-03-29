"""Dynamic game data helpers — cereals, trainings, school lessons from DB.

Uses in-memory cache with TTL since these items rarely change (admin only).
Call invalidate_game_data_cache() after any admin CRUD operation.
"""

import time
from datetime import datetime

from extensions import db
from models import CerealItem, TrainingItem, SchoolLessonItem
from data import CEREALS

# ── In-memory cache ───────────────────────────────────────────────────────
_game_data_cache = {}
_CACHE_TTL = 300  # 5 minutes — these change only when admin edits items


def invalidate_game_data_cache():
    """Clear all cached game data. Call after admin CRUD on items."""
    _game_data_cache.clear()


def _cached(key, loader):
    """Generic cache-or-load helper."""
    now = time.time()
    cached = _game_data_cache.get(key)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    value = loader()
    _game_data_cache[key] = (value, now)
    return value


# ── Availability check ────────────────────────────────────────────────────

def _is_available(item):
    """Verifie qu'un item est actif et dans sa fenetre de disponibilite."""
    if not item.is_active:
        return False
    now = datetime.utcnow()
    if item.available_from and now < item.available_from:
        return False
    if item.available_until and now > item.available_until:
        return False
    return True


# ── Public getters (cached) ───────────────────────────────────────────────

def get_cereals_dict():
    """Retourne un dict {key: {...}} depuis la DB. Fallback sur data.CEREALS."""
    def _load():
        items = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
        if not items:
            return CEREALS
        return {c.key: c.to_dict() for c in items if _is_available(c)}
    return _cached('cereals', _load)


def get_trainings_dict():
    """Retourne un dict {key: {...}} depuis la DB."""
    def _load():
        from data import TRAININGS
        items = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
        if not items:
            return TRAININGS
        return {t.key: t.to_dict() for t in items if _is_available(t)}
    return _cached('trainings', _load)


def get_school_lessons_dict():
    """Retourne un dict {key: {...}} depuis la DB."""
    def _load():
        from data import SCHOOL_LESSONS
        items = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
        if not items:
            return SCHOOL_LESSONS
        return {l.key: l.to_dict() for l in items if _is_available(l)}
    return _cached('school_lessons', _load)


def get_all_cereals_dict():
    """Comme get_cereals_dict() mais inclut les items inactifs (pour l'admin)."""
    items = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    return {c.key: c for c in items}


def get_all_trainings_dict():
    """Comme get_trainings_dict() mais inclut les items inactifs (pour l'admin)."""
    items = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    return {t.key: t for t in items}


def get_all_school_lessons_dict():
    """Comme get_school_lessons_dict() mais inclut les items inactifs (pour l'admin)."""
    items = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    return {l.key: l for l in items}
