"""Helpers for detecting and repairing broken migration state on deploy."""

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

APPS_AFTER_ACCOUNTS = (
    "sessions",
    "complaints",
    "audit",
    "facilities",
    "admin",
    "accounts",
)


def list_public_tables() -> set[str]:
    return set(connection.introspection.table_names())


def migration_history_exists() -> bool:
    return "django_migrations" in list_public_tables()


def schema_is_ready() -> bool:
    tables = list_public_tables()
    return "accounts_user" in tables and "django_migrations" in tables


def reset_public_schema() -> None:
    """Drop and recreate public schema (safe when DB has no real data)."""
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE")
        cursor.execute("CREATE SCHEMA public")
        cursor.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
        cursor.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER")


def clear_migration_records_for_apps(apps: tuple[str, ...]) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM django_migrations WHERE app = ANY(%s)",
            [list(apps)],
        )
        return cursor.rowcount


def repair_migration_state() -> str:
    """
    Fix deploy state where django_migrations says accounts ran but accounts_user
    is missing (common after a failed Render/Neon deploy).

    Returns a short status message for logs.
    """
    tables = list_public_tables()

    if "accounts_user" in tables:
        return "schema_ok"

    if not migration_history_exists():
        return "fresh_database"

    applied = MigrationRecorder(connection).applied_migrations()
    if not applied:
        return "fresh_database"

    # Only django_migrations (or empty schema) — full reset is safest.
    if tables <= {"django_migrations"}:
        reset_public_schema()
        return "reset_empty_schema"

    # Partial deploy: migration rows exist but core user table is missing.
    deleted = clear_migration_records_for_apps(APPS_AFTER_ACCOUNTS)
    if deleted:
        return f"cleared_migration_records:{deleted}"

    # Tables exist without accounts_user — reset everything.
    reset_public_schema()
    return "reset_inconsistent_schema"
