# RestoCore

<!-- CI badge: fill in OWNER/REPO after the GitHub repo exists, then uncomment.
[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
-->

All-in-one restaurant management system: public site and bookings, inventory, point of sale,
kitchen board, staff scheduling, attendance, leave, and a demo payroll. Plus a read-only MCP server
so an AI assistant can answer questions about the restaurant.

*"Where we RESTOre your confidence in managing."*

Portfolio project. Built with Django 5.2, PostgreSQL 17, Docker Compose and GitHub Actions.
Free to build and run. **All data is fake** (generated with Faker).

## Quickstart

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
[Git](https://git-scm.com/downloads). Nothing else; Python runs inside the container.

```bash
git clone <repo-url> restocore
cd restocore
cp .env.example .env                               # Windows cmd: copy .env.example .env
docker compose up --build                          # applies migrations, starts the app
docker compose run --rm web python manage.py seed_demo   # in a second terminal: fake demo data
```

Open <http://127.0.0.1:8000/>. Staff login is at <http://127.0.0.1:8000/accounts/login/>.

| Username  | Role    | Sees |
|-----------|---------|------|
| `owner`   | Owner   | Everything, including payroll and `/admin/` |
| `manager` | Manager | Everything except payroll |
| `cashier` | Cashier | Point of sale, orders |
| `kitchen` | Kitchen | Kitchen board, inventory (view + stock moves) |
| `staff`   | Staff   | Bookings |

Every role also has **My work**: own shifts, clock in/out, leave requests. Password for all demo
accounts: `restocore-demo` (set by `DEMO_PASSWORD` in `.env`). To start over:
`docker compose down -v` (deletes the database volume), then run the two commands again.

## What it does

| Module | Highlights |
|--------|-----------|
| **Website** | Home page, public menu (only available items), "Book a table" form. |
| **Bookings** | 30-minute slots inside opening hours, per-slot seat capacity, honeypot spam check, status workflow (pending → confirmed → seated → completed, or cancelled / no-show), staff phone bookings, filters and search. |
| **Inventory** | Items with reorder levels, an append-only stock ledger (received, waste, stock count, sales, voids), low-stock alerts. |
| **Sales** | Menu with per-portion recipes, POS checkout (cash or card, tax, change), kitchen board (queued → preparing → ready → served), printable receipts, manager-only voids. |
| **Staff** | Employees linked to logins and roles, weekly schedule with overlap and leave checks, clock in/out, leave requests with approval rules. |
| **Payroll (demo)** | Pay periods from attendance hours + approved paid leave, configurable deduction rates, draft → finalized (locked). |
| **Dashboard** | Role-aware: sales today and last 7 days, bookings, kitchen queue, low stock, pending leave, who is on shift. |
| **API + MCP** | Token-protected read-only JSON API and an MCP server with 5 read-only tools. See [docs/mcp.md](docs/mcp.md). |

## Branding and themes

- The café name comes from `RESTAURANT_NAME` and the currency symbol from `CURRENCY_SYMBOL` in `.env`.
- The public site and staff area both have light and dark themes (toggle in the navbar; defaults
  to the visitor's system setting).
- **Local logo override:** put a template at `local/templates/brand/mark.html` and it replaces the
  default cup mark everywhere; `local/templates/brand/favicon.svg` does the same for the browser-tab
  icon (served at `/favicon.svg`). The `local/` folder is gitignored, so real third-party logos used
  for a local demo are never committed.

## Tests, lint, and checks

```bash
docker compose run --rm web pytest                    # 250+ tests
docker compose run --rm web ruff check .
docker compose run --rm web ruff format --check .
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

Tests cover the business rules (services), every view, **one access test per role** for every
staff page, and a real two-thread race test for booking capacity. CI runs lint, formatting, the
Django checks, the migration drift check, the tests against a real Postgres, and
`manage.py check --deploy` in HTTPS mode on every push to `main` and every pull request. It also
builds both Docker images (`dev` and `prod`).

Frontend quality was checked in a real browser (Playwright): every page at 11 screen widths from
320 px to 1920 px with no horizontal scrolling, and an axe-core accessibility audit of every page in
light and dark mode with zero violations.

## Production-style run (locally)

The same app, built as the lean production image: gunicorn, no test tools, static files collected
and fingerprinted at build time and served by WhiteNoise, no source bind-mount, DEBUG off.

```bash
docker compose -f docker-compose.prod.yml -p restocore-prod up --build -d
docker compose -f docker-compose.prod.yml -p restocore-prod exec web python manage.py seed_demo
# open http://127.0.0.1:8080/
```

For a real deployment, serve it behind HTTPS and set `DJANGO_HTTPS=true`, a real
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. With those set,
`python manage.py check --deploy` passes (CI verifies this).

## Status

- [x] 0. Foundation: Docker Compose, env-based settings, ruff, pytest, CI
- [x] 1. Accounts and roles
- [x] 2. Public front page + bookings
- [x] 3. Inventory, then sales
- [x] 4. Staff, then payroll
- [x] 5. MCP server (read-only)
- [ ] 6. Deploy: production image, prod compose and deploy checks are ready; a free host is not chosen yet
## Design decisions

- **Modular monolith.** One Django project, one app per module (`bookings`, `inventory`, `sales`,
  `staff`, `payroll`, …). Writes go through each app's `services.py`, reads through `selectors.py`.
  An app never queries another app's models directly; for example, sales calls
  `inventory.services.deduct_for_sale()`.
- **Orders and stock commit together.** Checkout creates the order and deducts every ingredient in
  one `transaction.atomic()` block, with row locks (`select_for_update`, in id order) so two
  cashiers cannot oversell. If any ingredient is short, nothing is saved. Voids put back exactly
  what the ledger says was taken.
- **Roles are Django Groups,** created by a data migration. Every staff view declares its allowed
  roles (`RoleRequiredMixin`), and the role check runs *before* any object lookup, so a user without
  access gets 403 rather than learning which ids exist. Sensitive rules live in services too: only an
  Owner can create or edit Owners and Managers, nobody approves their own leave.
- **Money is `DecimalField`,** rounded half-up to cents. Orders and payslips store snapshots
  (price, name, hourly rate), so later edits never change history.
- **Config from environment variables.** The same image runs in dev, CI and prod. The app refuses
  to start without `DJANGO_SECRET_KEY`, and `DEBUG` is off unless explicitly enabled. Tax rate,
  restaurant name, time zone and API token are all env settings.
- **Times are stored in UTC; the restaurant's local time zone comes from `DJANGO_TIME_ZONE`.**
- **Payroll is a labelled demo.** Deduction rates are placeholders stored in the database and editable
  by the Owner; no real country's rules are implied.
- **Server-rendered templates, progressive enhancement.** Hand-written CSS and one small vanilla JS
  file, no build step. Every page works without JavaScript; JS adds motion (scroll reveals, count-ups,
  a cursor-following menu preview), the POS live total (the server always recalculates), time-slot
  chips on the booking form, and turning tables into cards on phones. Animations respect
  prefers-reduced-motion.
- **Responsive and accessible by default.** Mobile-first layouts with safe-area support for notched
  phones, 16 px form fields on phones (no iOS zoom), larger touch targets, a sticky POS checkout bar,
  and WCAG AA contrast in both themes.
- **Non-root container; Postgres not published to the host; web bound to `127.0.0.1`.**
- **Postgres everywhere.** Dev, CI and prod use the same database engine.
- **Custom user model before the first migration,** so it can grow without a painful swap.

## Project layout

```
config/       settings, URLs, health check
core/         roles, role-check mixin, base layouts, partials, CSS (shared by every app)
accounts/     custom User, role groups, login
website/      public pages            bookings/   public form + staff management
inventory/    items and stock ledger  sales/      menu, POS, orders, kitchen
staff/        employees, shifts, attendance, leave
payroll/      demo payroll            dashboard/  dashboard + seed_demo command
api/          read-only JSON API      mcp_server/ MCP server (separate requirements)
```
