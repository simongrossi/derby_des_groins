import io
import unittest

from app import create_app

from exceptions import ValidationError


class AdminAvatarServiceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')

    def test_create_avatar_requires_name(self):
        from services.admin_avatar_service import create_avatar

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                create_avatar('', '<svg></svg>', None)

        self.assertIn("Nom d'avatar requis", str(context.exception))

    def test_create_avatar_rejects_invalid_svg(self):
        from services.admin_avatar_service import create_avatar

        with self.app.app_context():
            with self.assertRaises(ValidationError) as context:
                create_avatar('Badge', 'not-svg', None)

        self.assertIn('Le code SVG doit commencer', str(context.exception))


if __name__ == '__main__':
    unittest.main()
