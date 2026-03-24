"""Dynamic game data helpers — cereals, trainings, school lessons from DB."""

from datetime import datetime

from extensions import db
from models import CerealItem, TrainingItem, SchoolLessonItem
from data import CEREALS


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


def get_cereals_dict():
    """Retourne un dict {key: {...}} depuis la DB. Fallback sur data.CEREALS."""
    items = CerealItem.query.order_by(CerealItem.sort_order, CerealItem.id).all()
    if not items:
        return CEREALS
    return {c.key: c.to_dict() for c in items if _is_available(c)}


def get_trainings_dict():
    """Retourne un dict {key: {...}} depuis la DB."""
    from data import TRAININGS
    items = TrainingItem.query.order_by(TrainingItem.sort_order, TrainingItem.id).all()
    if not items:
        return TRAININGS
    return {t.key: t.to_dict() for t in items if _is_available(t)}


def get_school_lessons_dict():
    """Retourne un dict {key: {...}} depuis la DB."""
    from data import SCHOOL_LESSONS
    items = SchoolLessonItem.query.order_by(SchoolLessonItem.sort_order, SchoolLessonItem.id).all()
    if not items:
        return SCHOOL_LESSONS
    return {l.key: l.to_dict() for l in items if _is_available(l)}


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
