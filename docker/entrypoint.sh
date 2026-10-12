#!/bin/sh
# Container entrypoint: apply database migrations, then run the requested command.
# Set SKIP_MIGRATIONS=1 on containers that must not migrate (e.g. the Celery worker).
set -e

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
fi

exec "$@"
