#!/usr/bin/env bash
# Runs migrations then starts Gunicorn (Render web service).
# Ensures Neon/Postgres schema exists even if preDeployCommand was not configured.
set -o errexit

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting gunicorn on port ${PORT}..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120
