from django.contrib.auth import get_user_model
from django.test import TestCase


class StaffTestCase(TestCase):
    """Existing CRUD scenarios now run with an authorized clinic administrator."""
    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_superuser("crud_admin", password="Test-Clinic-987!")
        self.client.force_login(self.staff)
