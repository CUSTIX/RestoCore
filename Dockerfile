FROM python:3.12-slim

# No .pyc files in the image; logs go straight to `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Don't run the app as root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Dev server. Production (step 6) will switch to gunicorn.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
