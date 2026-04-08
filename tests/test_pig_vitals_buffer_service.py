from datetime import UTC, datetime, timedelta
import unittest

from extensions import db
from models import Pig, User
from services.pig_service import get_pig_record, update_pig_vitals
from services.pig_vitals_buffer_service import (
    clear_buffered_pig_vitals,
    flush_buffered_pig_vitals,
    get_buffered_pig_vitals_snapshot,
    queue_buffered_pig_vitals,
)
from tests.support import build_test_app, reset_database


class PigVitalsBufferServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        clear_buffered_pig_vitals()
        reset_database(self.app)

    def _create_pig(self):
        with self.app.app_context():
            user = User(username='Keeper', password_hash='x')
            db.session.add(user)
            db.session.flush()
            original_last_updated = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
            pig = Pig(
                user_id=user.id,
                name='Buffer',
                hunger=100.0,
                energy=50.0,
                happiness=80.0,
                freshness=100.0,
                weight_kg=112.0,
                last_updated=original_last_updated,
                last_interaction_at=original_last_updated,
            )
            db.session.add(pig)
            db.session.commit()
            return pig.id, original_last_updated

    def test_update_pig_vitals_buffers_without_immediate_db_commit(self):
        pig_id, original_last_updated = self._create_pig()

        with self.app.app_context():
            pig = update_pig_vitals(pig_id)
            snapshot = get_buffered_pig_vitals_snapshot(pig_id)

            self.assertIsNotNone(snapshot)
            self.assertGreater(snapshot.last_updated, original_last_updated)
            self.assertLess(pig.hunger, 100.0)

            db.session.remove()
            persisted = db.session.get(Pig, pig_id)
            self.assertEqual(original_last_updated, persisted.last_updated)
            self.assertEqual(100.0, persisted.hunger)

    def test_get_pig_record_rehydrates_buffered_values_before_flush(self):
        pig_id, _original_last_updated = self._create_pig()

        with self.app.app_context():
            update_pig_vitals(pig_id)
            snapshot = get_buffered_pig_vitals_snapshot(pig_id)
            db.session.remove()

            hydrated = get_pig_record(pig_id)

            self.assertEqual(snapshot.last_updated, hydrated.last_updated)
            self.assertEqual(snapshot.hunger, hydrated.hunger)
            self.assertEqual(snapshot.energy, hydrated.energy)

    def test_flush_buffered_pig_vitals_persists_snapshot(self):
        pig_id, _original_last_updated = self._create_pig()

        with self.app.app_context():
            update_pig_vitals(pig_id)
            snapshot = get_buffered_pig_vitals_snapshot(pig_id)

            updated_count = flush_buffered_pig_vitals(pig_ids=[pig_id])

            self.assertEqual(1, updated_count)
            self.assertIsNone(get_buffered_pig_vitals_snapshot(pig_id))
            db.session.remove()
            persisted = db.session.get(Pig, pig_id)
            self.assertEqual(snapshot.last_updated, persisted.last_updated)
            self.assertEqual(snapshot.hunger, persisted.hunger)

    def test_flush_skips_stale_snapshot_when_database_is_newer(self):
        pig_id, _original_last_updated = self._create_pig()

        with self.app.app_context():
            pig = db.session.get(Pig, pig_id)
            pig.hunger = 60.0
            pig.last_updated = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=20)
            queue_buffered_pig_vitals(
                pig,
                queued_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
            )

            pig.hunger = 85.0
            pig.last_updated = datetime.now(UTC).replace(tzinfo=None)
            db.session.commit()

            updated_count = flush_buffered_pig_vitals(pig_ids=[pig_id])

            self.assertEqual(0, updated_count)
            self.assertIsNone(get_buffered_pig_vitals_snapshot(pig_id))
            db.session.remove()
            persisted = db.session.get(Pig, pig_id)
            self.assertEqual(85.0, persisted.hunger)


if __name__ == '__main__':
    unittest.main()
