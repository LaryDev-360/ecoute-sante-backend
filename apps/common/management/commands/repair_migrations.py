from django.core.management.base import BaseCommand

from apps.common.migration_repair import repair_migration_state, schema_is_ready


class Command(BaseCommand):
    help = (
        "Repair inconsistent migration history (e.g. accounts_user missing "
        "but django_migrations records exist) before running migrate."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit with code 1 if repair would be needed.",
        )

    def handle(self, *args, **options):
        if schema_is_ready():
            self.stdout.write(self.style.SUCCESS("Migration state OK."))
            return

        if options["check"]:
            self.stderr.write(
                self.style.WARNING("Migration state inconsistent — repair required.")
            )
            raise SystemExit(1)

        result = repair_migration_state()
        self.stdout.write(self.style.WARNING(f"Migration repair: {result}"))
