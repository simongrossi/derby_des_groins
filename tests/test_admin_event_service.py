import unittest

from app import create_app

from exceptions import ValidationError
from models import Pig, User


class AdminEventServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_trigger_admin_event_rejects_unknown_event(self):
        from services.admin_event_service import trigger_admin_event

        actor = User(id=1, username='Admin', is_admin=True)

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                trigger_admin_event(actor, 'nope')

        self.assertIn('Evenement inconnu', str(context.exception))

    def test_heal_admin_pig_rejects_healthy_pig(self):
        from services.admin_pig_service import heal_admin_pig

        pig = Pig(id=2, name='Rosette', is_injured=False)

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                heal_admin_pig(pig)

        self.assertIn("n'est pas blesse", str(context.exception))


if __name__ == '__main__':
    unittest.main()
