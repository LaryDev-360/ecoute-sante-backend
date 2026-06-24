from django.core.management.base import BaseCommand
from django.db import connection

from apps.common.db_health import get_database_health


class Command(BaseCommand):
    help = "Affiche la base PostgreSQL cible et l'état des migrations."

    def handle(self, *args, **options):
        db = connection.settings_dict
        self.stdout.write(f"Engine: {db.get('ENGINE')}")
        self.stdout.write(f"Host: {db.get('HOST')}")
        self.stdout.write(f"Database: {db.get('NAME')}")
        self.stdout.write(f"User: {db.get('USER')}")

        try:
            health = get_database_health()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Connection failed: {exc}"))
            raise SystemExit(1) from exc

        self.stdout.write(f"Connected database: {health['database']}")
        self.stdout.write(f"Tables: {health['table_count']}")
        self.stdout.write(
            f"Migrations applied: {'yes' if health['migrations_applied'] else 'NO'}"
        )
        self.stdout.write(
            f"Schema ready: {'yes' if health['ready'] else 'NO — run migrate'}"
        )

        if not health["ready"]:
            raise SystemExit(1)
