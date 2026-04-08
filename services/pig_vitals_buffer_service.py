from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from flask import current_app, has_app_context

from config.game_rules import PIG_DEFAULTS
from extensions import db
from models import Pig

_buffer_lock = RLock()
_buffered_vitals = {}


def _utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class PigVitalsSnapshot:
    pig_id: int
    queued_at: datetime
    last_updated: datetime | None
    hunger: float
    energy: float
    happiness: float
    freshness: float
    weight_kg: float
    ever_bad_state: bool


def get_vitals_batch_window_seconds():
    default_value = 60
    if has_app_context():
        return max(1, int(current_app.config.get('PIG_VITALS_COMMIT_INTERVAL_SECONDS', default_value)))
    return default_value


def build_pig_vitals_snapshot(pig, queued_at=None):
    return PigVitalsSnapshot(
        pig_id=int(pig.id),
        queued_at=queued_at or _utcnow_naive(),
        last_updated=getattr(pig, 'last_updated', None),
        hunger=float(getattr(pig, 'hunger', PIG_DEFAULTS.hunger) or PIG_DEFAULTS.hunger),
        energy=float(getattr(pig, 'energy', PIG_DEFAULTS.energy) or PIG_DEFAULTS.energy),
        happiness=float(getattr(pig, 'happiness', PIG_DEFAULTS.happiness) or PIG_DEFAULTS.happiness),
        freshness=float(getattr(pig, 'freshness', PIG_DEFAULTS.freshness) or PIG_DEFAULTS.freshness),
        weight_kg=float(getattr(pig, 'weight_kg', PIG_DEFAULTS.weight_kg) or PIG_DEFAULTS.weight_kg),
        ever_bad_state=bool(getattr(pig, 'ever_bad_state', False)),
    )


def get_buffered_pig_vitals_snapshot(pig_id):
    with _buffer_lock:
        return _buffered_vitals.get(int(pig_id))


def apply_buffered_vitals_to_pig(pig):
    if not pig or not getattr(pig, 'id', None):
        return pig

    snapshot = get_buffered_pig_vitals_snapshot(pig.id)
    if not snapshot:
        return pig
    if pig.last_updated and snapshot.last_updated and pig.last_updated > snapshot.last_updated:
        return pig

    pig.hunger = snapshot.hunger
    pig.energy = snapshot.energy
    pig.happiness = snapshot.happiness
    pig.freshness = snapshot.freshness
    pig.weight_kg = snapshot.weight_kg
    pig.ever_bad_state = snapshot.ever_bad_state
    pig.last_updated = snapshot.last_updated
    return pig


def queue_buffered_pig_vitals(pig, queued_at=None):
    snapshot = build_pig_vitals_snapshot(pig, queued_at=queued_at)
    with _buffer_lock:
        current = _buffered_vitals.get(snapshot.pig_id)
        if current and current.last_updated and snapshot.last_updated and current.last_updated > snapshot.last_updated:
            return current
        _buffered_vitals[snapshot.pig_id] = snapshot
    return snapshot


def discard_buffered_pig_vitals(pig_id):
    with _buffer_lock:
        _buffered_vitals.pop(int(pig_id), None)


def clear_buffered_pig_vitals():
    with _buffer_lock:
        _buffered_vitals.clear()


def flush_buffered_pig_vitals(pig_ids=None, due_only=False, now=None):
    now = now or _utcnow_naive()
    due_after_seconds = get_vitals_batch_window_seconds()

    with _buffer_lock:
        candidate_ids = set(int(pig_id) for pig_id in pig_ids) if pig_ids else set(_buffered_vitals.keys())
        snapshots = {
            pig_id: snapshot
            for pig_id, snapshot in _buffered_vitals.items()
            if pig_id in candidate_ids
            and (
                not due_only
                or (now - snapshot.queued_at).total_seconds() >= due_after_seconds
            )
        }

    if not snapshots:
        return 0

    db_rows = db.session.query(Pig.id, Pig.last_updated).filter(Pig.id.in_(snapshots.keys())).all()
    db_last_updated_by_id = {pig_id: last_updated for pig_id, last_updated in db_rows}
    mappings = []
    processed_ids = set()

    for pig_id, snapshot in snapshots.items():
        db_last_updated = db_last_updated_by_id.get(pig_id)
        processed_ids.add(pig_id)
        if pig_id not in db_last_updated_by_id:
            continue
        if db_last_updated and snapshot.last_updated and db_last_updated > snapshot.last_updated:
            continue
        mappings.append({
            'id': pig_id,
            'hunger': snapshot.hunger,
            'energy': snapshot.energy,
            'happiness': snapshot.happiness,
            'freshness': snapshot.freshness,
            'weight_kg': snapshot.weight_kg,
            'ever_bad_state': snapshot.ever_bad_state,
            'last_updated': snapshot.last_updated,
        })

    if mappings:
        db.session.bulk_update_mappings(Pig, mappings)
    db.session.commit()

    with _buffer_lock:
        for pig_id in processed_ids:
            current_snapshot = _buffered_vitals.get(pig_id)
            if current_snapshot == snapshots.get(pig_id):
                _buffered_vitals.pop(pig_id, None)

    return len(mappings)


def flush_due_buffered_pig_vitals(now=None):
    return flush_buffered_pig_vitals(due_only=True, now=now)
