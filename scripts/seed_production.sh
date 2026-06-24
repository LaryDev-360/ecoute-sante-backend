#!/usr/bin/env bash
# Seed the production Neon database from your machine (no Render Shell required).
#
# Usage:
#   export DATABASE_URL='postgresql://user:pass@ep-xxx.region.aws.neon.tech/ecoute_sante?sslmode=require'
#   ./scripts/seed_production.sh
#
# Copy DATABASE_URL from Render → Environment (same value as the web service).
set -o errexit

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: Set DATABASE_URL to your Neon connection string."
  echo "  export DATABASE_URL='postgresql://.../ecoute_sante?sslmode=require'"
  exit 1
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
export SECRET_KEY="${SECRET_KEY:-local-seed-only}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost}"

if [[ "${DATABASE_URL}" == *"-pooler."* ]]; then
  export DATABASE_URL="${DATABASE_URL//-pooler./.}"
  echo "Using direct Neon endpoint (pooler disabled)."
fi

PYTHON="${PYTHON:-python3}"
if [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
fi

echo "Seeding production database…"
"$PYTHON" manage.py seed_if_empty "$@"
echo "Done."
