# One Dockerfile, two targets:
#   dev  - test tools + Django dev server (docker-compose.yml)
#   prod - runtime deps only, static files collected at build, gunicorn (docker-compose.prod.yml)

FROM python:3.15-slim AS base
# No .pyc files in the image; logs go straight to `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
# Dependencies first, so this layer stays cached until requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Don't run the app as root.
RUN useradd --create-home appuser

FROM base AS dev
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
USER appuser
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS prod
COPY . .
# Collect and fingerprint static files at build time. The key below exists only for this build
# step; the running container must get a real DJANGO_SECRET_KEY from the environment.
RUN DJANGO_SECRET_KEY=build-only-not-secret DJANGO_STATIC_MANIFEST=true \
    python manage.py collectstatic --noinput \
 && chown -R appuser:appuser /app/staticfiles
USER appuser
EXPOSE 8000
# migrate, (optionally) reset the public demo, then gunicorn on $PORT. See bin/start.sh.
CMD ["sh", "bin/start.sh"]
