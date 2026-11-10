# RestoCore

<!-- CI badge: fill in OWNER/REPO after the GitHub repo exists, then uncomment.
[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
-->

All-in-one restaurant management system: public site and bookings, inventory, sales, staff, and payroll.

*"Where we RESTOre your confidence in managing."*

Portfolio project. Built with Django, PostgreSQL, Docker, and GitHub Actions. Free to build and run.

## Quickstart

Prerequisites:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with Compose)
- [Git](https://git-scm.com/downloads)

```bash
git clone <repo-url> restocore
cd restocore
cp .env.example .env          # Windows cmd: copy .env.example .env
docker compose up --build
```

Then open <http://127.0.0.1:8000/healthz/>. It should say `ok`.

`.env.example` holds placeholder values for local development only. Never commit your `.env`.

## Tests, lint, and checks

All commands run inside the container, so you need nothing installed besides Docker:

```bash
docker compose run --rm web pytest
docker compose run --rm web ruff check .
docker compose run --rm web python manage.py check
```

CI runs the same three on every push to `main` and every pull request, and also checks that the Docker image builds.

## Status

- [x] 0. Foundation: Docker Compose, env-based settings, ruff, pytest, CI
- [ ] 1. Accounts and roles
- [ ] 2. Public front page + bookings
- [ ] 3. Inventory, then sales
- [ ] 4. Staff, then payroll
- [ ] 5. MCP server (read-only)
- [ ] 6. Deploy

Later:

- [ ] Production compose must not bind-mount the source code (dev-only).
- [ ] Split requirements into app and dev files so the production image has no test tools.
- [ ] Production runs gunicorn, not the Django dev server.

## Design decisions

- **Modular monolith.** One Django project with one app per module. Apps talk to each other through
  `services.py`, not each other's models. Simple to run and deploy, with clean module boundaries.
- **Config from environment variables.** The same image runs in dev, CI, and prod. The app refuses to
  start without `DJANGO_SECRET_KEY`, and `DEBUG` is off unless explicitly enabled.
- **Non-root container.** The app runs as an unprivileged user inside the image.
- **Postgres is not published to the host.** Only the `web` container can reach it, over the internal
  Compose network.
- **Web is bound to localhost.** The dev server listens on `127.0.0.1` only, so it is not exposed to the LAN.
- **Times are stored in UTC; the restaurant's local time zone comes from `DJANGO_TIME_ZONE`.**
- **Postgres everywhere.** Dev, CI, and prod use the same database engine, so there are no "works on SQLite" surprises.
- **Custom user model before the first migration.** Swapping the user model after migrations exist is painful,
  so milestone 1 adds it before `migrate` is ever run. Until then the dev database is intentionally unmigrated.
