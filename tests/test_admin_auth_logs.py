import unittest

from app import create_app
from extensions import db
from models import AuthEventLog, User


class AdminAuthLogsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()

    def test_admin_auth_logs_requires_admin(self):
        response = self.client.get('/admin/auth-logs')
        self.assertEqual(response.status_code, 302)

    def test_admin_auth_logs_page_is_accessible_for_admin(self):
        with self.app.app_context():
            admin = User.query.filter_by(username='auth-log-admin').first()
            if admin is None:
                admin = User(username='auth-log-admin', password_hash='x', is_admin=True)
                db.session.add(admin)
                db.session.flush()
                db.session.add(AuthEventLog(event_type='login', is_success=True, user_id=admin.id, ip_address='127.0.0.1'))
                db.session.commit()
            admin_id = admin.id

        with self.client.session_transaction() as session:
            session['user_id'] = admin_id

        response = self.client.get('/admin/auth-logs')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Journal des connexions', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
