import unittest

from extensions import db
from models import AuthEventLog, User
from services.auth_log_service import purge_old_auth_events
from tests.support import build_test_app, reset_database


class AuthLogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_test_app()

    def setUp(self):
        reset_database(self.app)
        self.client = self.app.test_client()

    def test_failed_login_logs_ip_and_metadata(self):
        response = self.client.post(
            '/login',
            data={'username': 'inconnu', 'password': 'bad-pass'},
            headers={'X-Forwarded-For': '203.0.113.7'},
        )

        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            event = AuthEventLog.query.filter_by(event_type='login', is_success=False).order_by(AuthEventLog.id.desc()).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.ip_address, '203.0.113.7')
            self.assertEqual(event.username_attempt, 'inconnu')
            self.assertEqual(event.route, '/login')

    def test_logout_logs_event(self):
        with self.app.app_context():
            user = User.query.filter_by(username='auth-log-test-user').first()
            if user is None:
                user = User(username='auth-log-test-user', password_hash='x')
                db.session.add(user)
                db.session.commit()
            user_id = int(user.id)

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            event = AuthEventLog.query.filter_by(event_type='logout', user_id=user_id).order_by(AuthEventLog.id.desc()).first()
            self.assertIsNotNone(event)
            self.assertTrue(event.is_success)

    def test_non_auth_request_is_logged_with_ip(self):
        response = self.client.get('/', headers={'X-Forwarded-For': '203.0.113.99'})
        self.assertIn(response.status_code, (200, 302))

        with self.app.app_context():
            event = AuthEventLog.query.filter_by(event_type='site_action').order_by(AuthEventLog.id.desc()).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.ip_address, '203.0.113.99')
            self.assertEqual(event.route, '/')

    def test_non_auth_request_logs_username_for_authenticated_user(self):
        with self.app.app_context():
            user = User.query.filter_by(username='auth-log-site-action-user').first()
            if user is None:
                user = User(username='auth-log-site-action-user', password_hash='x')
                db.session.add(user)
                db.session.commit()
            user_id = int(user.id)

        with self.client.session_transaction() as session:
            session['user_id'] = user_id

        response = self.client.get('/', headers={'X-Forwarded-For': '203.0.113.55'})
        self.assertIn(response.status_code, (200, 302))

        with self.app.app_context():
            event = (
                AuthEventLog.query
                .filter_by(event_type='site_action', user_id=user_id, ip_address='203.0.113.55')
                .order_by(AuthEventLog.id.desc())
                .first()
            )
            self.assertIsNotNone(event)
            self.assertEqual(event.username_attempt, 'auth-log-site-action-user')

    def test_purge_old_auth_logs_removes_expired_rows(self):
        with self.app.app_context():
            stale = AuthEventLog(
                event_type='login',
                is_success=False,
                ip_address='198.51.100.10',
                occurred_at=None,
            )
            db.session.add(stale)
            db.session.flush()
            stale_id = stale.id
            stale.occurred_at = stale.occurred_at.replace(year=2000)
            db.session.commit()

            deleted = purge_old_auth_events(30)
            self.assertGreaterEqual(deleted, 1)

            still_there = db.session.get(AuthEventLog, stale_id)
            self.assertIsNone(still_there)


if __name__ == '__main__':
    unittest.main()
