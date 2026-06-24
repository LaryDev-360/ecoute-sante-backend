from django.db import connection


def get_database_health() -> dict:
    """Return connection info and whether Django migrations have been applied."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]

    table_names = set(connection.introspection.table_names())
    migrated = "django_migrations" in table_names

    return {
        "database": db_name,
        "migrations_applied": migrated,
        "table_count": len(table_names),
        "ready": migrated and "accounts_user" in table_names,
    }
