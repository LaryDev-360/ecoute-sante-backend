#!/usr/bin/env bash
set -o errexit

./scripts/render_migrate.sh

echo "Starting gunicorn on port ${PORT}..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --timeout 120
