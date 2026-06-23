#!/usr/bin/env bash
# Runs migrations then starts Gunicorn (Render web service).
set -o errexit

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set."
  exit 1
fi

echo "Applying database migrations (start)..."
python manage.py migrate --noinput
python manage.py db_status

echo "Starting gunicorn on port ${PORT}..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120
