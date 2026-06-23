#!/usr/bin/env bash
# Shared migrate step for Render build/start.
set -o errexit

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set."
  exit 1
fi

# Neon pooler breaks DDL/migrations — use the direct endpoint.
if [[ "${DATABASE_URL}" == *"-pooler."* ]]; then
  export DATABASE_URL="${DATABASE_URL//-pooler./.}"
  echo "Using direct Neon endpoint for migrations (pooler disabled)."
fi

echo "Checking migration state..."
python manage.py repair_migrations

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Verifying database..."
python manage.py db_status

echo "Seeding demo data if database is empty..."
python manage.py seed_if_empty
