import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.accounts.models import User


def seeding_enabled(force: bool) -> bool:
    if force:
        return True
    if User.objects.exists():
        return False
    flag = os.environ.get("SEED_DEMO_DATA", "true").lower()
    return flag in ("1", "true", "yes", "on")


class Command(BaseCommand):
    help = (
        "Charge les données de démo (établissements, comptes, plaintes) "
        "si la base ne contient encore aucun utilisateur."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Exécuter le seed même si des utilisateurs existent déjà.",
        )

    def handle(self, *args, **options):
        if not seeding_enabled(options["force"]):
            self.stdout.write(
                self.style.WARNING(
                    f"{User.objects.count()} utilisateur(s) déjà présent(s) — seed ignoré."
                )
            )
            return

        self.stdout.write("Chargement des données de démo…")
        call_command("seed_facilities")
        call_command("seed_data")
        self.stdout.write(self.style.SUCCESS("Données de démo chargées."))
