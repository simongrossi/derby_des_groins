import unittest

from app import create_app

from exceptions import ValidationError


class AdminNotificationServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_send_test_smtp_email_requires_address(self):
        from services.admin_notification_service import send_test_smtp_email

        with self.assertRaises(ValidationError) as context:
            send_test_smtp_email('')

        self.assertIn('Adresse email requise', str(context.exception))


if __name__ == '__main__':
    unittest.main()
