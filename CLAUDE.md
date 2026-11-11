# RestoCore

All-in-one restaurant management system. "Where we RESTOre your confidence in managing."

## Goal (read this first)

This is a **portfolio project**. A hiring manager should be able to:
1. Clone the repo, run `docker compose up`, and see it work.
2. Click through a live or recorded demo.
3. Read the README and see clear decisions, tests, and CI.

So: **a small thing that works end to end beats a big thing that is half built.**
Secondary goal: the owner is learning **DevOps** (Docker, CI/CD, deploy) and **MCP** (an MCP server for RestoCore). Explain the *why* briefly when you do DevOps or MCP work.

Everything must be **free to build and run**. No paid services, no paid APIs.

## Stack

- Django + PostgreSQL
- Docker + Docker Compose (dev and prod parity)
- pytest + pytest-django, ruff
- GitHub Actions for CI (public repo)
- Server-rendered Django templates first. Add JS only where it clearly helps.

## How the app is organized

One domain, one Django project, one app per module (a "modular monolith"):

```
/                 public front page, menu, booking form
/app/...          staff area (role-gated)
/admin/           Django admin
/api/...          later, for the MCP server
```

Planned apps: `accounts`, `website`, `bookings`, `inventory`, `sales`, `staff`, `payroll`.

Roles: Owner, Manager, Cashier, Kitchen, Staff. Use Django Groups and permissions. Every staff view must check the role.

## Build order (trunk first, leaves later)

0. Foundation: repo, Docker Compose, settings from env, ruff, pytest, CI.
1. Accounts and roles (custom user model **before the first migration**).
2. Public front page + bookings (first full vertical slice).
3. Inventory, then sales (orders deduct stock in one transaction).
4. Staff (schedules, attendance, leave requests), then payroll.
5. MCP server (read-only tools).
6. Deploy.

Detailed features (for example leave approval rules) come after the module's trunk works. Do not build leaves early.

## Commands

```
cp .env.example .env             # first time only (Windows cmd: copy .env.example .env)
docker compose up --build        # run the app (applies migrations on start)
docker compose run --rm web python manage.py seed_demo   # fake demo data, logins per role
docker compose run --rm web pytest
docker compose run --rm web ruff check .
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml -p restocore-prod up --build -d   # production-style stack on :8080
```

Dependencies: runtime packages go in `requirements.txt`; test/lint tools in `requirements-dev.txt`.

If a command here is wrong or missing, fix this file in the same change.

## Rules for code

- Keep it simple. Don't build abstractions for needs that don't exist yet. When the same thing is needed a second time, extract it into `core` and reuse it.
- Business logic goes in `services.py` inside each app, not in views or templates.
- An app does not reach into another app's models. Call that app's service.
- Money is `DecimalField`. Never float.
- Use `select_related` / `prefetch_related` to avoid N+1 queries.
- Use `transaction.atomic()` when several writes must succeed together.
- Config and secrets come from environment variables. Commit `.env.example` only, never `.env`.
- Demo data comes from seed scripts with fake data (Faker). Never real names or real payroll data.
- Payroll rules are country-specific. Keep rates configurable and label payroll as a demo.

## Consistency and reuse

- Every app uses the same layout: `models.py`, `services.py`, `selectors.py` (read queries), `forms.py`, `views.py`, `urls.py`, `admin.py`, `templates/<app>/`, `tests/`.
- Shared code lives in a `core` app: an abstract base model (created/updated timestamps), role-check mixins, one base layout template, and template partials (buttons, form fields, tables, alerts, pagination). Create `core` when the first shared piece is needed, not before.
- Before writing a template, helper or mixin, check `core` and the existing apps and reuse what's there.
- Naming is uniform: singular PascalCase models, URL names as `app:action`, templates as `app/model_action.html`, test files that mirror the module they test.
- Every module follows the same flow: role-gated view, then form, then service call, then a test per role.
- Scalable by design, without premature optimization: a stateless web container, all config from env, all state in Postgres (no local files), indexes on foreign keys and filtered fields, and pagination on every list.

## Security (always)

- Validate input with Django forms or serializers.
- Check permissions on every view, including object-level access.
- `DEBUG=False` outside local dev. Run `python manage.py check --deploy` before any deploy.
- Never put secrets, keys, or personal data in the repo, logs, or screenshots.

## How to work

- **Don't overthink.** For a small change, just do it. For a change touching 3+ files, write a short plan first (5 lines max), then do it.
- Look at the existing code before adding new code. Follow the patterns already there.
- Change only what was asked. Do not refactor or reformat unrelated code.
- If something is ambiguous and a wrong guess is expensive, ask one short question. Otherwise pick the simplest option and say what you picked.
- Work in small steps. After each step, run the tests.
- Be direct and brief. Explain *why*, not just *what*.

## Git rules

- Stage explicit file paths only. Never `git add -A` or `git add .`.
- Show me the diff before every commit.
- Commit messages: short, imperative, one change per commit.
- **Never push without me confirming in that moment.** Push is always a separate step.
- Never delete CI logs or workflow runs before reading the error.

## Definition of done

A change is done when:
- It works and tests pass (`pytest`, `ruff check`).
- New behavior has a test, including a failure case. Permission changes have a test per role.
- Migrations are included and reviewed. Back up data before running destructive ones.
- The README or docs are updated if setup, architecture, or behavior changed.

## Project skills

Skills live in `.claude/skills/`. Use them when they match the task. Planned: `restocore-add-module`, `django-migration-safety`, `django-security-review`, `codex-handoff`.

## Not now

Real payments, real customer data, paid hosting, mobile apps, and anything not in the build order above.
