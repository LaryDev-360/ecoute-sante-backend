from io import StringIO

from django.core.management import call_command

from apps.accounts.models import User
from apps.common.tests.base import BaseAPITestCase


class SeedIfEmptyTests(BaseAPITestCase):
    def test_skips_when_users_exist(self):
        User.objects.create_user(
            username="existing",
            email="existing@test.bj",
            password="pass",
            role="ADMIN",
        )
        out = StringIO()
        call_command("seed_if_empty", stdout=out)
        self.assertIn("seed ignoré", out.getvalue())

    def test_force_runs_when_users_exist(self):
        User.objects.create_user(
            username="existing",
            email="existing@test.bj",
            password="pass",
            role="ADMIN",
        )
        out = StringIO()
        call_command("seed_if_empty", "--force", stdout=out)
        self.assertIn("Données de démo chargées", out.getvalue())
