import unittest

from app import create_app
from werkzeug.security import generate_password_hash

from exceptions import ValidationError
from models import User


class AuthServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_resolve_safe_next_url_accepts_internal_paths_only(self):
        from services.auth_service import resolve_safe_next_url

        self.assertEqual(resolve_safe_next_url('/profil'), '/profil')
        self.assertIsNone(resolve_safe_next_url('https://example.com/evil'))
        self.assertIsNone(resolve_safe_next_url('profil'))

    def test_change_user_password_rejects_short_password(self):
        from services.auth_service import change_user_password

        user = User(
            id=1,
            username='Tester',
            password_hash=generate_password_hash('ancienmotdepasse'),
        )

        with self.assertRaises(ValidationError) as context:
            change_user_password(
                user,
                'ancienmotdepasse',
                '123',
                '123',
            )

        self.assertIn('au moins', str(context.exception))


if __name__ == '__main__':
    unittest.main()
