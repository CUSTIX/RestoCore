#!/bin/sh
# Start the production container: apply migrations, optionally reset the public demo, then serve.
# Migrating here (not in a separate release step) keeps one container doing everything, which
# fits a single small instance such as a free hosting plan.
set -e

python manage.py migrate --noinput

# Public demo only: wipe and reseed so every visitor gets clean demo data. Both flags are required
# so a copied environment file can never flush a real database by accident.
if [ "${DEMO_RESET_ON_START:-false}" = "true" ] && [ "${DEMO_MODE:-false}" = "true" ]; then
  python manage.py seed_demo --reset

  # The live demo is kept awake (.github/workflows/keep-awake.yml), so it rarely restarts. Reset
  # it once a day as well, at DEMO_RESET_HOUR local time, in a background loop next to gunicorn.
  # The reset is one transaction, so visitors never see an empty database.
  if [ -n "${DEMO_RESET_HOUR:-}" ]; then
    if python bin/seconds_until_hour.py "$DEMO_RESET_HOUR" > /dev/null; then
      (
        while true; do
          sleep "$(python bin/seconds_until_hour.py "$DEMO_RESET_HOUR")"
          python manage.py seed_demo --reset || echo "Nightly demo reset failed" >&2
        done
      ) &
    else
      echo "Nightly demo reset disabled: DEMO_RESET_HOUR='$DEMO_RESET_HOUR' is not a whole hour 0-23." >&2
    fi
  fi
elif [ "${DEMO_RESET_ON_START:-false}" = "true" ]; then
  echo "DEMO_RESET_ON_START ignored: it only works together with DEMO_MODE=true." >&2
fi

# PORT is set by most hosts (Render, etc.); WEB_CONCURRENCY sizes the worker pool to the RAM.
# Threads keep the site answering while a slow request (the AI assistant) is in flight; recycling
# workers now and then caps memory growth on a small instance. The access log records the path
# but not the query string: guest searches and the self-order token travel in the query.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-3}" \
  --worker-class gthread --threads 4 \
  --worker-tmp-dir /dev/shm \
  --max-requests 1000 --max-requests-jitter 100 \
  --timeout 75 --graceful-timeout 30 \
  --access-logfile - --error-logfile - \
  --access-logformat '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)s'
