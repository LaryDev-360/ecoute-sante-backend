#!/usr/bin/env bash
set -o errexit

pip install -r requirements/prod.txt
python manage.py collectstatic --noinput

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set — migrations cannot run."
  echo "Set DATABASE_URL in Render → Environment (Neon connection string)."
  exit 1
fi

echo "Running database migrations (build)..."
python manage.py migrate --noinput
python manage.py db_status
