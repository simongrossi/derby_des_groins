import unittest

from app import create_app

from exceptions import ValidationError
from models import User


class AdminUserServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_toggle_admin_status_rejects_self_edit(self):
        from services.admin_user_service import toggle_admin_status

        actor = User(id=1, username='Admin', is_admin=True)

        with self.assertRaises(ValidationError) as context:
            toggle_admin_status(actor, actor)

        self.assertIn('propres droits admin', str(context.exception))

    def test_reset_user_password_rejects_short_password(self):
        from services.admin_user_service import reset_user_password

        target = User(id=2, username='Player')

        with self.assertRaises(ValidationError) as context:
            reset_user_password(target, '123')

        self.assertIn('Mot de passe trop court', str(context.exception))


if __name__ == '__main__':
    unittest.main()
