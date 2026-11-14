#!/bin/sh
# Start the production container: apply migrations, optionally reset the public demo, then serve.
# Migrating here (not in a separate release step) keeps one container doing everything, which
# fits a single small instance such as a free hosting plan.
set -e

python manage.py migrate --noinput

# Public demo only: wipe and reseed so every visitor gets clean demo data.
# On a free plan that sleeps when idle, this runs on every wake-up.
if [ "${DEMO_RESET_ON_START:-false}" = "true" ]; then
  python manage.py seed_demo --reset

  # The live demo is kept awake (.github/workflows/keep-awake.yml), so it rarely restarts. Reset
  # it once a day as well, at DEMO_RESET_HOUR local time, in a background loop next to gunicorn.
  # The reset is one transaction, so visitors never see an empty database.
  if [ -n "${DEMO_RESET_HOUR:-}" ]; then
    (
      while true; do
        sleep "$(python bin/seconds_until_hour.py "$DEMO_RESET_HOUR")"
        python manage.py seed_demo --reset || echo "Nightly demo reset failed" >&2
      done
    ) &
  fi
fi

# PORT is set by most hosts (Render, etc.); WEB_CONCURRENCY sizes the worker pool to the RAM.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-3}" \
  --timeout 75 \
  --access-logfile - --error-logfile -
