# RestoCore

> **Where we RESTOre your confidence in managing.**

RestoCore is a modular-monolith restaurant management system. It combines a public restaurant website with role-based internal modules for bookings, staff operations, payroll, inventory, orders, POS workflows, and reporting.

## Foundation scope

This branch establishes the project foundation only:

- Python 3.12 and Django 5.2 LTS
- split settings for development, testing, staging, and production
- a custom user model before the first application migration
- business modules under `apps/`
- reusable template layouts and shared UI partials
- PostgreSQL-oriented environment configuration
- uv, Ruff, pytest-django, and pre-commit tooling
- basic home and health-check endpoints

Docker, Celery, CI/CD, authentication screens, permissions, and restaurant business features are intentionally separate changes.

## Repository structure

```text
apps/                 Django business modules
config/               Settings, URL routing, ASGI, and WSGI
config/settings/      Environment-specific settings
static/               Source-controlled static assets
templates/            Layouts, reusable components, and pages
tests/                Cross-application project tests
docs/                 Architecture records and operating docs
manage.py              Django management entry point
pyproject.toml         Dependencies and tool configuration
```

## Local setup

Requirements:

- Python 3.12
- uv
- PostgreSQL

```bash
git clone https://github.com/CUSTIX/RestoCore.git
cd RestoCore
cp .env.example .env
uv sync --all-groups
uv run python manage.py migrate
uv run python manage.py runserver
```

On Windows PowerShell, copy the environment file with:

```powershell
Copy-Item .env.example .env
```

Open `http://127.0.0.1:8000/`. The process-level health endpoint is `http://127.0.0.1:8000/healthz/`.

The test suite uses an isolated SQLite database for speed. Development, staging, and production are configured for PostgreSQL so database-specific behavior is not hidden during feature work.

## Quality checks

```bash
make check
```

On Windows without `make`, run the equivalent commands:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test
uv run python manage.py check --settings=config.settings.test
uv run pytest
```

Install the Git hooks after synchronizing dependencies:

```bash
make pre-commit
```

## Engineering rules

- Keep business modules inside `apps/`; `config/` contains configuration only.
- Put shared technical infrastructure in `apps/core`, not unrelated business entities.
- Prefer permission checks over role-name checks when authorization is introduced.
- Put shared page chrome in `templates/layouts/` and reusable fragments in `templates/components/`.
- Do not add generic service or repository layers until a concrete use case requires them.
- Store money as integer centavos or `Decimal`, never floating-point values.
- Store timestamps with timezone support and display them in `Asia/Manila`.
