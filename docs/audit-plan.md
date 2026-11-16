# RestoCore audit and enterprise-readiness plan

Status: **complete, plan only** (2026-11-15). No application code was changed for this audit. The
five review areas (security, correctness, UX and accessibility, operations, test quality) are merged
in section 2. Severity: critical, high, medium, low. Effort: S under 1 hour, M half a day, L a day or
more. Totals: 0 critical; **high:** COR-01, OPS-01, OPS-02 and five UX items (UX-01 to UX-05; UX-01
confirmed in code, UX-02, -03 and -05 read from code, UX-04 observed live); the rest medium and low.
Security review found no critical, high or medium issues.

## Progress (updated 2026-11-16)

Fixed, each with a test that failed first (where the finding was a bug), one commit per change:

- **Phase 0:** OPS-01, OPS-03, OPS-05, OPS-06, OPS-09, OPS-12, SEC-06, UX-01, UX-02, UX-03, UX-16, QA-18, QA-19, QA-25.
- **Phase 1:** COR-01 (payroll finalize), COR-03, COR-05, COR-06, COR-07, COR-08, COR-09, COR-13, SEC-01, SEC-03, SEC-04, SEC-05, SEC-07, SEC-08, SEC-10, OPS-04 (and SEC-02), OPS-02 in `render.yaml` (needs a Blueprint sync in Render, see below), OPS-10.
- **Phase 2 (started):** QA-01 (coverage floor 92%, measured 94.3%), QA-02 (fast hasher: suite 6 to 4 minutes), QA-04 and QA-05 (a role x URL x GET/POST matrix of 432 cases driven by the URLconf), QA-08, QA-16, part of QA-23.
- **Phase 3 (started, 2026-11-16):** UX-04 (form errors announced), UX-05 (checkout bar on tablets), UX-06 (no auto-reload while typing), UX-08 (skip link), UX-09 (errors stay on screen), UX-10 (New order on the receipt), UX-13 (friendly assistant off-state), UX-15 (44 px touch targets), UX-21 (main landmark on 403/404).
- One more bug found while fixing: `assistant/tests/test_tools.py::test_staff_tools` failed between midnight and 5 AM Manila (clock-dependent); now uses a fixed time.
- Abot got the same operations fixes before launch (`/livez/`, deploy after CI, nightly reset, heartbeat).

Suite: **1277 tests, 94.3% coverage**, about 4 to 6 minutes.

**Still open:** COR-02, COR-04, COR-10 to COR-12, COR-14 to COR-17 (need your decisions or are low value); UX-07, UX-11, UX-12, UX-14, UX-17 to UX-20, UX-22, UX-23; QA-03, QA-06, QA-07, QA-09 to QA-15, QA-17, QA-20 to QA-23 (rest), QA-26, QA-27; OPS-07, OPS-08, OPS-11, OPS-13 to OPS-15; SEC-09 done via OPS-01, SEC-11 (decision). Phase 5 upgrades (Django 6.1, Python 3.15).

**After the push, in the Render dashboard** (the Blueprint file is not applied automatically): sync the Blueprint (or set the health check path to `/livez/`, auto-deploy to "After CI checks pass", and add `DEMO_RESET_HOUR=4`).

## 1. Baseline (verified 2026-11-15)

| Check | Result |
| --- | --- |
| Tests | 667 pass (about 6 minutes) |
| Lint | `ruff check` and `ruff format --check` clean |
| Migrations | `makemigrations --check` clean |
| CI and CodeQL | green on `main` |
| Live headers | CSP, HSTS (1 year, subdomains), X-Frame-Options DENY, COOP/CORP same-origin, Permissions-Policy, Referrer-Policy all present |
| Edge | Cloudflare is in front of Render, so `CLIENT_IP_HEADER=HTTP_CF_CONNECTING_IP` is valid for the sign-in throttle |
| Keep-awake heartbeat | 4 successful scheduled runs so far |
| Architecture rule | Apps call each other only through selectors and services (no cross-app model imports found) |
| Money and time | No `FloatField` or `float()` in app code; no naive `datetime.now()` (one harmless `date.today()` used for slot arithmetic in `bookings/services.py:43`) |
| `mark_safe` | Two uses, both on trusted generated SVG (`core/templatetags/core.py:29`, `sales/views.py:365`) |

## 2. Findings

Five tables follow (operations, security, correctness, test quality, UX). Each row has an ID, severity,
file and line, what is wrong, the fix, and effort.

| ID | Area | Severity | Where | Problem | Fix | Test | Effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OPS-01 | Operations | high | `render.yaml:11`, `config/views.py:5-9` | Render's health check is `/healthz/`, which queries the database, so Neon may never auto-suspend (free compute hours could run out mid-month). A Neon outage also fails the check and can start a restart loop, and every restart migrates and reseeds | Set `healthCheckPath: /livez/`; keep `/healthz/` for compose and manual checks | Neon console shows near-zero compute overnight | S |
| OPS-02 | Operations | high | `render.yaml:10`, `ci.yml` | `autoDeploy: true` deploys every push to `main` even when CI is red; each deploy reseeds and signs visitors out. Dependabot merges deploy too | Render `autoDeployTrigger: checksPass` (confirm the field name), or `autoDeploy: false` plus a deploy hook called from a final CI job | Push a failing commit to a test service; confirm no deploy | S |
| OPS-03 | Operations | medium | `config/settings.py:176-187` | No `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS` or `connect_timeout`: every request opens a new TLS connection to Neon, and a request to a suspended database can hang up to the 75 s gunicorn timeout | `CONN_MAX_AGE=60`, `CONN_HEALTH_CHECKS=True`, `connect_timeout=10` when `DATABASE_URL` is set | Request after 6 minutes idle returns 200; connection reuse visible | S |
| OPS-04 | Operations | medium | `bin/start.sh:28-32`, `assistant/services.py:25,134`, `assistant/llm.py:23` | The assistant's 60 s time budget is checked only between model calls, so the worst case is about 85 s, over gunicorn's 75 s timeout (worker killed mid-request). With 2 sync workers, two slow questions block every worker, including the health check | `--worker-class gthread --threads 4`; `TIME_BUDGET=40`; add `--max-requests 1000 --max-requests-jitter 100 --worker-tmp-dir /dev/shm --graceful-timeout 30` | Two concurrent slow requests (mocked model): `/livez/` still answers | S |
| OPS-05 | Operations | medium | `bin/start.sh:17-23`, `bin/seconds_until_hour.py:20-23` | Confirmed by rehearsal: `DEMO_RESET_HOUR=abc` or `25` kills the nightly loop silently while gunicorn keeps running, so the reset never happens | Validate the hour once before starting the loop; log "nightly reset disabled" or fail fast | Rerun the rehearsal with bad values | S |
| OPS-06 | Operations | medium | `bin/start.sh:9-12` | The wipe-and-reseed runs on `DEMO_RESET_ON_START` alone; a copied environment file would flush whatever `DATABASE_URL` points at | Also require `DEMO_MODE=true` | Start with `DEMO_MODE` unset; confirm no reset | S |
| OPS-07 | Operations | medium | `docs/deploy.md` | No documented backup or restore plan (the data is fake and reseedable, but that is not written down) | Document: recovery is `seed_demo --reset`; optional `pg_dump`; Neon branch restore | Dry-run `pg_dump` against the compose database | S |
| OPS-08 | Operations | low | `bin/start.sh:7`, `seed_demo.py:309` | During a deploy the new instance's reset locks tables while the old one still serves; two simultaneous resets serialize safely | Document it; avoid deploying at 04:00 Manila | n/a | S |
| OPS-09 | Operations | low | `config/settings.py:236-241` | Log lines have no level, logger name or timestamp format; gunicorn worker lines use +0800 and the master uses UTC; every heartbeat ping is logged | Add a formatter; set `TZ=UTC` in the container | Check `docker logs` format | S |
| OPS-10 | Operations | low | `ci.yml:18,74,88` | No `timeout-minutes` on any job; no pip or Docker layer cache; Dependabot Actions PRs ungrouped, and each merge deploys and reseeds | `timeout-minutes: 15`; group Actions updates monthly | Next CI run | S |
| OPS-11 | Operations | low | `bookings/services.py:43-44` | `dt.date.today()` uses the process time zone, not `timezone.localdate()` (harmless today: only the times are used) | Use `timezone.localdate()`; optionally run CI once with an extreme `TZ` | CI matrix passes | S |
| OPS-12 | Operations | low | `.env.example`, `docs/deploy.md:43-55` | Missing from `.env.example`: `CURRENCY_SYMBOL`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_LOG_LEVEL`, `DJANGO_HSTS_*`, `DJANGO_HTTPS`, `DJANGO_STATIC_MANIFEST`, `WEB_CONCURRENCY`, `PORT`, `RESTOCORE_API_URL`. The deploy table omits `CLIENT_IP_HEADER` and `GEMINI_API_KEY` | Add the commented lines and two table rows | grep of environment names against `.env.example` | S |
| OPS-13 | Operations | low | `Dockerfile:5,24-34` | Base image not pinned to a patch version; no `HEALTHCHECK`; an unneeded `chown` of staticfiles | Pin `3.12.x-slim`; add a healthcheck | `docker build` | S |
| OPS-14 | Operations | low | `core/throttle.py:24-30` | If the configured client-IP header is missing, the code falls back to Render's proxy address, so all visitors share one throttle bucket | Log a warning when the header is configured but absent | Unit test | S |
| OPS-15 | Operations | info | `keep-awake.yml` | Heartbeat now works (4 successful runs), but GitHub cron can slip past the 15 minute spin-down, so a cold start is still possible | Optional second free pinger (cron-job.org or UptimeRobot, 5 minutes) | Check Render logs for gaps | S |

### Security findings

Result: **no critical, high or medium issues.** All items are low or informational. Not run:
`pip-audit` (needs a root-capable container; CI runs it for `requirements*.txt`).

| ID | Severity | Where | Problem | Fix | Test | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-01 | low | `assistant/tools.py:503-511` | `run()` catches only `ToolError`; wrong-typed model arguments (`{"search": 5}`, a list as args) raise TypeError or AttributeError and become an HTTP 500 for the owner | Treat non-dict args as `{}`; catch `(TypeError, AttributeError, ValueError)` and return an error dict | `assistant/tests/test_tools.py`: those calls return `{"error": ...}` | S |
| SEC-02 | low | `assistant/services.py:25`, `bin/start.sh:31` | Same root cause as **OPS-04** (assistant time budget vs gunicorn timeout; two slow questions block both workers; the owner login is public in demo mode) | See OPS-04 | Slow fake client raises `AssistantUnavailable` in under 75 s | S |
| SEC-03 | low | `assistant/tools.py` (`list_bookings`, `list_leave`, `list_orders`) | Visitor-written booking names and notes reach the model via tool results (prompt injection). Tools are read-only and output is rendered as text, so the worst case is a misleading answer | Truncate notes to about 120 characters and strip newlines in tool output | Tool test: long or multiline notes are truncated | S |
| SEC-04 | low (policy) | `assistant/tools.py` (`get_pay_period`, `list_pay_periods`, `list_employees`) | Pay rates and payslips are sent to Gemini. Fine for fake data, wrong for real payroll (free-tier terms need confirming) | `ASSISTANT_ALLOW_PAYROLL` flag, default false outside demo; note in `SECURITY.md` | `declarations()` omits payroll tools when off | S |
| SEC-05 | low | `staff/services.py:26-31`, `:57` | In demo mode the guard checks only the target user, so the shared owner can create new Owner or Manager accounts with a private password that lasts until the next reset; employee count is unbounded | In `DEMO_MODE`, refuse Owner/Manager creation and cap employees (about 40) | Demo-mode owner creation refused; the 41st employee refused | S |
| SEC-06 | low | `bin/start.sh:32`, `bookings/forms.py` (`q`), `sales/views.py` (`?code=`, `?self_order=<token>`) | Query strings reach the access log: guest name, phone and email searches and the self-order token (also the customer's secret link) | `--access-logformat '%(h)s %(m)s %(U)s %(s)s %(L)s'` (path without query) | `tests/test_start_script.py` asserts the flag | S |
| SEC-07 | low | `api/views.py:26-34`, `.env.example` | API bearer check is constant-time but not throttled; the example token is weak and gets copied. The live API is off (503), so no current exposure | Throttle failures per IP via `core.throttle`; refuse tokens under 24 characters; document `secrets.token_urlsafe(32)` | 6 bad tokens give 429; short token gives 503 | S |
| SEC-08 | low | `.github/dependabot.yml:5-6`, `ci.yml` audit job | `mcp_server/requirements.txt` is neither watched by Dependabot nor audited by CI | Add a pip entry for `/mcp_server`; `pip-audit -r mcp_server/requirements.txt` | CI fails on a vulnerable pin | S |
| SEC-09 | low | `render.yaml:11` | Same root cause as **OPS-01** (public `/healthz/` runs `SELECT 1` and is polled continuously; anyone can also burn compute hours) | See OPS-01 | Assertion on `render.yaml` | S |
| SEC-10 | low | `sales/views.py` (status and cancel views), `bookings/views.py` (`PublicThanksView`) | Public pages showing order contents or the guest name send no cache header (`no-store` is set only for signed-in users) | `never_cache` on these views | Header test on both pages | S |
| SEC-11 | info (decision) | `staff/views.py` (`EmployeeUpdateView`), `bookings/views.py` | Staff role sees guest phone and email; a Manager can change pay rates of lower roles with no owner approval. Intentional and tested | Owner decides (see questions) | n/a | S |

**Security: verified good** (no work needed): generic login errors, validated `next`, POST-only
logout, throttling per user+IP and per IP including the admin login; Cloudflare rejects a forged
`CF-Connecting-IP` (error 1000), so the throttle header cannot be spoofed on the live site;
HSTS, CSP (`script-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`), frame-deny, nosniff,
COOP and CORP, `no-store` for signed-in pages, Secure and HttpOnly CSRF cookie; `check --deploy`
clean; role checks run before object lookups, and live probes of Staff, Manager and Kitchen showed
403 on every page they should not reach; object-level rules (`assert_can_manage`, no self-approval,
own-leave cancel, Owner-only payroll) are in services and tested; self-order tokens are UUID4 and
code search is cashier-only; booking and self-order endpoints are throttled with a honeypot; no raw
SQL, no `csrf_exempt`, no uploads, `mark_safe` only on trusted SVG, one `innerHTML` on static text;
assistant tools call selectors only, cap rows and drop unknown arguments; exact dependency pins.

**Open questions for the owner** (from the security review): should Managers be able to change pay
rates, or should that be Owner-only (SEC-11)? Will this ever hold real data (decides how much SEC-04
and SEC-05 matter)? Keep `/healthz/` as Render's health check, or switch to `/livez/` (OPS-01)?

### Correctness and data-integrity findings

Verification: RUN = confirmed by a probe against a throwaway database; V = confirmed by reading
the code. Only COR-01 is a real money bug.

| ID | Severity | Where | Problem and how to reproduce | Fix | Test | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| COR-01 (RUN) | **high** | `payroll/services.py:150-222` | Payslips are a snapshot, and `finalize_period` checks only that payslips exist and no clock-in is open. Generate payslips with 4 h closed plus 1 open clock-in, close the entry, then finalize: 4.00 h is locked, true is 12.00, and the 8 hours are never paid. Approved leave or a rate change after generation behaves the same | Rebuild payslips inside `finalize_period`, or store `generated_at` and refuse if any entry, leave or employee changed since | Generate, close entry, finalize, assert 12.00 | S |
| COR-02 (V) | medium | `staff/selectors.py:107-116`, `payroll/services.py:135` | Paid leave counts every calendar day at a flat 8 h, including weekends and days off, with no balance or cap (a Monday to Sunday leave pays 7 x 8 h) | Count scheduled or weekday days only; add allowances (owner decision, Q2) | 7-day leave with 5 rostered days gives 5 | M |
| COR-03 (RUN) | medium | `payroll/models.py:21-27`, `payroll/services.py:137-145` | Each deduction rate is validated below 1 but active rates are never summed: two rates of 0.6 give net -200.00 on 1000 gross, locked into a payslip | Validate that the sum of active rates is below 1 in the formset and in `generate_payslips` | Two 0.6 rates raise `ValidationError` | S |
| COR-04 (RUN) | medium | `staff/models.py:43-48`, `staff/services.py:278` | A rostered shift cannot cross midnight (22:00 to 02:00 is refused); attendance handles midnight, the roster does not | Store shifts as datetimes or add an overnight flag | 22:00 to 02:00 saves with 4.00 h | M |
| COR-05 (RUN) | medium | `inventory/services.py:123-132` | `update_item` saves without `update_fields`, rewriting `quantity` from a stale copy: stock ends at 10 while the ledger says 15, breaking "ledger always matches" | `item.save(update_fields=[*data, "updated_at"])` | Load item, receive +5 elsewhere, update the stale copy, assert 15 | S |
| COR-06 (RUN) | medium | `sales/views.py:432-451`, `sales/selectors.py:217-222` | A self-order older than 60 minutes stays "pending" until the next self-order creation sweeps it. The customer's page still shows the code while the cashier lookup refuses it ("No open order") | Treat pending orders past the TTL as expired in the view, or sweep on read | 61-minute-old pending order shows "This order expired" | S |
| COR-07 (RUN) | low | `dashboard/management/commands/seed_demo.py:431-432,518-522,562-566` | `seed_demo` depends on the clock: seeded between 00:00 and about 02:00 Manila, today's orders land on yesterday ("sales today" is empty) and 3 clock-ins stay open, blocking the demo pay period from finalizing. `DEMO_RESET_HOUR=4` is safe; hours 0 to 2 are not | Anchor today's orders and on-shift entries to fixed local hours, clamped to today | Freeze time at 00:02, seed, assert orders today > 0 and no open entries | S |
| COR-08 (RUN) | low | `sales/selectors.py:113,189`, `inventory/selectors.py:301`, money filter | Rounding modes disagree: order math uses HALF_UP, the template filter and averages use HALF_EVEN (average 100.05 over 2 shows 50.02, HALF_UP gives 50.03) | Use HALF_UP everywhere | Average of 100.05 / 2 equals 50.03 | S |
| COR-09 (RUN) | low | `sales/services.py:79-123` | The service trusts the form: dine-in with no table is accepted, takeaway keeps a typed table, `order_type` and `payment_method` are not validated. Safe today (PosForm), not for a future API caller | Validate in `place_order` | `place_order(dine_in, "")` raises | S |
| COR-10 (RUN) | low | `staff/views.py:376,338` | N+1 queries on the leave list (3 rows cost 9 queries) and attendance list. Bounded by page size 20 | Annotate or prefetch the counts | `django_assert_num_queries` constant in row count | S |
| COR-11 (V) | low | `sales/selectors.py:73,101,122,142`, `staff/selectors.py:63,88`, `inventory/selectors.py:289` | `created_at__date` and `clock_in__date` defeat the btree index (correct results, sequential scans as data grows) | Filter on [local midnight, next local midnight) | Query-shape test | S |
| COR-12 (V) | low | `payroll/services.py:166-168` | No rate history: raising a rate and regenerating a draft reprices all hours in the period | Effective-dated rates, or warn on regenerate | Rate change keeps earlier hours at the old rate | M |
| COR-13 (V) | low | `sales/services.py:165` | `if expected and ...` skips the stale-ticket guard when `from` is missing, so a crafted POST can skip a kitchen step | Make `expected` required | POST without `from` is refused | S |
| COR-14 (V) | low | `staff/services.py:463-478` | `review_leave` can approve leave that already started or sits in a finalized pay period; it is never paid | Refuse or warn on past or finalized dates | Approving leave in a finalized period raises | S |
| COR-15 (V) | low | `staff/services.py:280,425`, `payroll/services.py:126` | Overlap checks (shifts, leave, pay periods) are check-then-insert with no lock or exclusion constraint | Lock the employee or period row, or a Postgres exclusion constraint | Two threads, same shift, one fails | M |
| COR-16 (V) | low | `core/throttle.py:145-157`, `bookings/services.py:180-194`, `sales/services.py:260-298` | `is_limited` then `record` is not atomic, so a parallel burst exceeds the per-IP limits | Record first, or lock per key | N threads against a limit of 3 | S |
| COR-17 (V) | low (product) | `sales/selectors.py:13-19` | The public menu lists dishes with 0 stock; the POS disables them | Mark them "sold out" | Menu shows sold out at 0 stock | S |

**Correctness: verified good** (no work needed): JS and server tax math agree (0 mismatches over
7 rates and subtotals of 1 to 200000 cents); checkout is atomic and a shortage rolls everything
back; 4 simultaneous orders for 1 portion gave 1 success and stock never went negative (row locks
in pk order plus a database CHECK); idempotent checkout via a unique token; void restores stock by
replaying the ledger, idempotently; self-order charge and cancel both lock the row; booking
capacity uses a per-slot advisory lock; payroll invariants (gross = regular + leave, net = gross -
deductions, unique period/employee, finalized periods locked, payslips snapshot rates); no
`FloatField`; FKs indexed; lists paginated; main list views free of N+1; `makemigrations --check`
clean.

**Open questions for the owner** (from the correctness review): is overtime or night differential
intentionally out of scope; should paid leave count calendar days or scheduled days, and is a leave
balance planned (CLAUDE.md defers leave rules); should booking capacity model dwell time or only
guests starting per 30-minute slot (today up to 40 can start per slot with no overlap accounting).

### Test coverage and speed (measured 2026-11-15)

667 tests pass; **97% line coverage** (5937 statements, 204 missed). With coverage on, the suite takes
about 12 minutes (6 minutes without).

| Module | Coverage | Missed lines | Note |
| --- | --- | --- | --- |
| `bin/seconds_until_hour.py` | 67% | 5 | The `__main__` path (bad-hour handling, see OPS-05) is untested |
| `payroll/views.py` | 74% | 17 | Payroll POST actions: add per-role tests (ties to COR-01) |
| `staff/views.py` | 80% | 51 | Leave review, attendance close, shift edit and delete paths |
| `bookings/views.py` | 89% | 12 | |
| `config/settings.py` | 88% | 9 | Deploy-only branches (`DATABASE_URL`, HTTPS) |

Slowest tests: the per-role link crawl (`core/tests/test_link_integrity.py`, 13 to 31 s per role,
mostly fixture setup) and the password-spraying throttle tests (19 to 22 s each, likely password
hashing). Cheap speedup to try: a fast password hasher in the test settings. Coverage is a floor
worth adding to CI once the gaps above are filled.

### Test quality, code health and docs findings

| ID | Severity | Where | Problem | Fix | Effort |
| --- | --- | --- | --- | --- | --- |
| QA-01 | medium | `requirements-dev.txt`, `ci.yml:57` | Coverage is measured nowhere in CI and not gated (`pytest-cov` absent) | Add `pytest-cov` and `--cov-fail-under` (current: 97%); print the table in the job summary | S |
| QA-02 | medium | `conftest.py:19-27` | No fast `PASSWORD_HASHERS` override in tests; the two sign-in lockout tests take 22 s and 19 s | Autouse fixture using `MD5PasswordHasher` | S |
| QA-03 | medium | `core/tests/test_link_integrity.py:34-43`, `dashboard/tests/test_dashboard.py` | `seed_demo` runs once per role (5 times) in the link crawl plus 5 more in dashboard tests: the top slow tests | Seed once per module or loop the 5 roles in one test; keep the 2 TRUNCATE tests | M |
| QA-04 | medium | `core/tests/test_access_guard.py:56` | The no-role test accepts 403 **or 404**, GET only: a view with no role check that 404s on dummy id `1` passes | Assert 403, use real objects for pk routes | S |
| QA-05 | medium | `test_access_guard.py:26-28` | Walk covers `/app/` and `/api/` for anonymous users only: no wrong-role per URL, no public POSTs (`/book/`, `/order/`, cancel), no `/admin/`, no object-level access | Role x URL matrix driven by `RoleRequiredMixin.allowed_roles` | M |
| QA-06 | medium | `test_link_integrity.py:45-57` | Crawler follows GET links under `/app/` only; `MAX_PAGES=150` truncates silently; only assertion is `len(seen) > 3` | Assert the queue drained; add public pages | S |
| QA-07 | medium | `bookings/tests/test_concurrency.py:13` | The only threaded test in the repo: checkout idempotency race, oversell, void, payslip generation and finalize, and `charge_self_order` have none | Threaded tests (backlog below) | M |
| QA-08 | medium | `bookings/services.py:185-190`, `bookings/views.py:146-147` | Posting `status=bogus` raises ValueError and the view flashes its text; no test | Validate against `Booking.Status.values`; add a test | S |
| QA-09 | medium | `payroll/tests/test_payroll.py:107-119`, `payroll/views.py:70-111` | Missing per-role tests for rates, payslip detail, period detail; the finalize action through the view; the "Unknown action" branch (ties to COR-01) | See backlog | S |
| QA-10 | medium | `sales/tests/test_views.py:95-105` | Kitchen advance tested only as Kitchen; menu create and update POST tested only as Manager | Parametrize over roles | S |
| QA-11 | medium | `api/tests/test_api.py:35-39` | Valid-token test asserts only status and content type; only `/api/menu/` has a payload test; the MCP tools depend on this contract | Schema test per endpoint, bad-date 400, bearer casing, empty token | S |
| QA-12 | medium | `mcp_server/server.py:8` | `mcp` is not in dev requirements, so the server is never imported in CI | Optional CI job that installs it and imports the server | S |
| QA-13 | low | `sales/tests/test_self_order.py`, `sales/tests/test_views.py`, `dashboard/tests/test_dashboard.py` | Brittle HTML assertions (attribute-order regexes; `"Payroll" not in html` matches anywhere) | Assert on `response.context` or scope to the nav block | M |
| QA-14 | low | `tests/test_access_order.py:24` | Unused `role` parameter: every URL runs twice identically | Parametrize on `url` only | S |
| QA-15 | low | several test modules | Tests import helpers from other test modules; duplicated fixtures (`booking_data`, `_worked`, `api_on`, `item`) | Move to `conftest.py` | S |
| QA-16 | low | `website/context_processors.py:13-17` | `cafe_open_now` reads the clock internally, so the 11:00 and 22:00 boundaries are untestable | Inject `now` | S |
| QA-17 | low | `pyproject.toml:11` | Ruff rules `DTZ`, `PT`, `C4`, `RUF` not enabled (DTZ would flag `bookings/services.py:43`, see OPS-11) | Add the rules | S |
| QA-18 | low | repo root | No LICENSE (a public repo defaults to all-rights-reserved), no pre-commit config, no CONTRIBUTING | MIT license; pre-commit with ruff and ruff-format | S |
| QA-19 | low | `inventory/selectors.py:25,38` | Dead code: `active_items()` and `recent_movements()` are unused | Delete | S |
| QA-20 | low | `sales/views.py:437-466`, `inventory/views.py:53-71`, `payroll/views.py:63-77`, `dashboard/views.py:30-32`, `bookings/views.py:162-167` | Logic in views that CLAUDE.md puts in services or selectors | Move and unit test | M |
| QA-21 | low | `sales/selectors.py:218`, `inventory/forms.py:15`, `bookings/selectors.py:7` | Function-level and constant imports between selectors and services (circular-import smell) | Move constants to `constants.py` | S |
| QA-22 | low | `sales/selectors.py:31` | `order_by("?")` makes the home page order random per request | Deterministic order | S |
| QA-23 | low | `accounts/tests`, `core/tests/test_templatetags.py` | Untested: successful password change, login `?next=https://evil`, several template tags, throttle pruning, `paginate` with a bad page | Small unit tests | S |
| QA-24 | low | `.env.example` | Same gap as OPS-12 (variables read by settings but not listed) | See OPS-12 | S |
| QA-25 | low | `README.md:77` | Says "450+ tests"; actual is 667 | Update or drop the number | S |
| QA-26 | medium | `README.md:84` | Claims "one access test per role for every staff page", contradicted by QA-09, QA-10 and the staff gaps | Close the gaps (QA-05) or soften the sentence | S |
| QA-27 | low | `CLAUDE.md` "Consistency" | Several apps lack parts of the standard layout; root `tests/` has no `__init__.py`; `seed_demo` is the deliberate cross-app exception | State the exemptions | S |

Also missing in docs: an `/api/` reference (five endpoints, parameters, error codes 401/503/400,
sample JSON); the README quickstart should warn to wait for migrations before `seed_demo`;
`docs/qa-checklist.md` says demo accounts show "local DEBUG only" and omits `DEMO_MODE`.

**Time-zone and flakiness: no real risk found.** Tests use `timezone.localdate()` and
`timezone.now()` consistently, with fixed local times or a fixed `NOW` in the time-rule tests;
Faker and `random` are seeded; no random ordering, skips or xfails. Residual risks: a run within
seconds of Manila midnight could fail the `tomorrow` fixture, and a shift crossing midnight or the
UTC boundary has no test (see COR-04).

**Test backlog** (one line each, grouped by app; per-role tests assert "403 and nothing saved"):

- **sales:** kitchen advance POST per role; menu create and update POST per role; POS POST per role
  (Kitchen and Staff get 403, no order created); threaded same-token `place_order` creates one order;
  concurrent orders for the last portion; cash exactly equal to total; tax rounds half up; quantity
  99 ok and 100 rejected; void without a reason keeps the order; charging an expired self-order;
  self-order code collision gives up after ten tries; table QR defaults to tables 1 to 8.
- **bookings:** unknown status rejected; update and create POST per role; party size 0, 1, 20, 21;
  exactly 90 days ahead ok and 91 rejected; public daily limit of 10; capacity error shown on update;
  search by phone, email and reference; simultaneous status changes apply once.
- **payroll:** rates GET and POST per role; payslip and period detail per role; finalize via the view
  locks the period; unknown action flashes an error; entry crossing midnight or UTC paid on its local
  start date; deduction rounds half up; two simultaneous payslip generations leave one set.
- **inventory:** update item POST per role; count equal to stock shows nothing changed; zero change
  and negative count rejected; concurrent sales cannot oversell the last unit.
- **staff:** shift delete, shift create and update, employee create and update, attendance close and
  leave review POSTs, each for all five roles.
- **api and mcp:** payload schema per endpoint; `sales_summary` bad date; bearer casing and empty
  token; no contact details in booking rows; server registers five tools (CI job with `mcp`).
- **accounts, core, website:** password change success; external `?next` rejected; cafe-open
  boundaries with injected time; template-tag unit tests; throttle pruning; `paginate` fallback;
  access-guard role matrix (QA-05).

**Already strong:** URLconf walk for anonymous access and role-check-before-lookup test; per-role
tables with "nothing saved" assertions across most apps; CI with real Postgres, migration-drift
check, `check --deploy`, pip-audit, CodeQL, Dependabot and both Docker builds; the "no inline JS"
CSP test over every template; idempotency and double-submit tests for checkout and kitchen advance;
a real thread-barrier booking race test; login throttling tests (user, IP, spraying, window, no-IP,
admin login).

### UX, UI and accessibility findings

Live crawl: 101 page loads at 390 and 1440 px as anonymous, owner, manager, cashier, kitchen and
staff. Every page returned 200 except expected 403 and 404; no horizontal overflow, one `h1` per
page, no unlabeled inputs, no JS errors; every page under 2 s except the cold home page on phone
(3.6 s); axe (WCAG 2.0/2.1 A and AA) clean on every page except `landmark-one-main` and `region` on
the 403 and 404 pages. **Not exercised live** (the test script crashed; findings marked CODE are
from reading templates, CSS and JS): POS charge, receipt and void, kitchen advance, table QR and
payslip printing, inventory form, leave approve and reject, dark-mode staff pages, phone drawer and
POS mobile bar, and tablet widths (641 to 1100 px). Test data left on the live site (cleared by the
nightly reset): one booking "UX AUDIT TEST (ignore)" and two cancelled customer orders.

| ID | Severity | Where | Problem | Fix | Effort |
| --- | --- | --- | --- | --- | --- |
| UX-01 | high (confirmed in code) | `staff/templates/staff/form.html:11` | Cancel is `href="javascript:history.back()"`; the CSP blocks `javascript:` URLs, so Cancel on shift and employee forms is dead. The existing "no inline JS" test checks event handlers only | Link to the list URL; extend the test to grep templates for `javascript:` | S |
| UX-02 | high (CODE) | `core/static/core/app.css:198-202` | POS "Order type" and "Payment" segmented radios are `opacity:0` with no `:focus-visible` style, so keyboard focus is invisible (WCAG 2.4.7); the public `.order-seg` has the ring | `.seg label:has(input:focus-visible)` outline | S |
| UX-03 | high (CODE) | `core/static/core/base.css:75,122` | Dark mode: `.btn--danger` is white on `#ec8f86`, about 2.4:1 (needs 4.5:1); affects Void, Reject, Delete | Dark ink on danger, or a darker background | S |
| UX-04 | high | `core/templates/core/partials/form.html:5-6` | Server-side error alert has no `role="alert"`; field errors have no id, `aria-describedby` or `aria-invalid`, so wrong-password and lockout messages are not announced | Add `role="alert"` and emit the aria attributes in the partial | M |
| UX-05 | high (CODE) | `core/static/core/app.css:243,296,322` | At 641 to 1100 px (tablet) the POS is single-column but the sticky total/Checkout bar exists only at 640 px and below; the cashier scrolls past the whole menu to charge | Show the bar up to 1100 px, or keep two columns to about 900 px | S |
| UX-06 | medium | `sales/templates/sales/self_order_list.html:49`, `sales/templates/sales/kitchen.html:35`, `core/static/core/motion.js` | A blind `location.reload()` every 30 s wipes the code the cashier is typing and can move a button under the finger on the kitchen board | Skip reload while an input has focus or a value, or fetch and swap the list | S |
| UX-07 | medium | `core/static/core/app.css:243-246` | Kitchen board collapses to one column at 1100 px (Ready far below Queued on a landscape tablet); 15 px ticket text; "late" is red only | Keep 3 columns to about 800 px, larger type, add a text or icon for late | M |
| UX-08 | medium | `core/templates/core/app_base.html`, `public_base.html` | No skip-to-content link; 16 sidebar links precede `<main>` | Skip link as first element | S |
| UX-09 | medium | `core/static/core/motion.js:102`, `base.css:165` | Error and warning toasts vanish after 6 s and pause only on mouse hover; on phone they cover the menu button | Do not auto-dismiss errors; pause on focus; show errors inline | S |
| UX-10 | medium | `sales/templates/sales/order_detail.html:5` | After every charge the cashier lands on a receipt with only Print and All orders: no "New order", one extra click per sale | Role-gated primary "New order" button | S |
| UX-11 | medium | `sales/static/sales/order.js:51-56` | Customer ordering: "Enter your table number above" with a disabled Done button, but the field is off-screen after scrolling and nothing is announced | Make the text a link that focuses the field; add `aria-live` | S |
| UX-12 | medium | `sales/static/sales/order.css:34`, `website/templates/website/menu.html` | Sold-out rows dim to 55% opacity (below AA); the only cue is "Sold out" in the price line; `/menu/` never shows availability. Not verified live | Add a badge as on the POS; dim only the photo | S |
| UX-13 | medium | `assistant/templates/assistant/chat.html:13` | The owner's nav item opens "Set GEMINI_API_KEY ... see docs/assistant.md": a developer note in the first demo impression (until the key is set, see C3) | In demo mode without a key, hide the item or show a friendly off-state with sample answers | S |
| UX-14 | medium | `core/static/core/app.css:27` | Sidebar group labels about 3.7:1 contrast; sidebar, login overlay and scrim still use green tints from an old theme | Brand-token color at about .62 alpha; replace the green tints | S |
| UX-15 | medium | `core/static/core/app.css:176,342,55,316`, `order.css`, `site.css` | Touch targets under 44 px: POS stepper 38, icon buttons 38 to 40, order stepper 40, party buttons 42 (83 to 94 small elements on the phone POS) | 44 px under `(pointer: coarse)` | S |
| UX-16 | low | `core/templates/core/base.html:11-13`, `config/settings.py` | Console shows "Refused to connect to fonts.googleapis.com" on every page. The stylesheet itself is allowed, so the fonts load; the refused request is the `preconnect` hint, which falls under `connect-src` | Remove the two `preconnect` lines, or self-host the fonts (fits the no-external-services goal) | S |
| UX-17 | medium | `bookings/static/bookings/book.js`, booking page | After seating hours the form defaults to today with all 21 slots hidden; a past date shows raw browser text "Value must be 11/15/2026 or later." | Default to the next open day; friendlier messages | S |
| UX-18 | low | `sales/templates/sales/order_list.html`, `order_detail.html`, `sales/views.py` | Money has no currency symbol on orders, receipt, payslip and the "Change due" toast (dashboard and POS show the peso sign) | One currency-aware filter | S |
| UX-19 | low | `core/static/core/motion.js:370` | Destructive actions use native `window.confirm` ("Cancel this order?" with no code or amount) | A `<dialog>` driven by the same `data-confirm`, showing context | M |
| UX-20 | low | `core/static/core/motion.js:312` | Hero photo stack auto-advances every 3.8 s with no pause control (WCAG 2.2.2) | Pause on focus; add a pause button | S |
| UX-21 | low | `core/templates/403.html`, `404.html`, `accounts/views.py` | 403 and 404 pages lack `<main>`; `/accounts/password/` returns HTTP 403 for an informational page; blank breadcrumb outside the nav | Wrap in `<main>`; return 200; fall back to the page title | S |
| UX-22 | low | `sales/templates/sales/self_order_status.html:51` | Customer status page reloads fully every 15 s (flash, screen readers not told); a cancelled order still says "Estimated total" | Fetch plus an `aria-live` region; relabel for cancelled | M |
| UX-23 | low | `core/static/core/motion.js`, `sales/templates/sales/table_qr.html` | Phone table stacking depends on JS (layout shift); tables in cards scroll sideways; printed QR cards have no URL fallback; thanks page shows the reference twice; mixed UK and US spelling | Server-render `data-label`; unify spelling | M |

**UX: works well** (verified live): no 5xx, overflow or unlabeled inputs on 101 pages; the POS charge
hints ("Enter the table...", "Cash received is short", "Change due") and quick-cash chips; QR ordering
states (pending, cancel confirm, cancelled, waiting banner); booking form focuses the first invalid
field and hides passed slots; every role's navigation matches what it can open and 403s are friendly;
strict CSP, double-submit lock on every POST form, shared partials, persisted dark mode, reduced
motion and print styles.

**Professional polish ideas** (not bugs): kitchen display mode (3 columns, large type, new-ticket
flash, no reload); an in-app confirm dialog with context; inline saved-state feedback; a demo-friendly
Ask RestoCore off-state with canned answers; one currency formatting helper; a "New order" shortcut
and POS keyboard shortcuts; self-hosted fonts and per-page titles with the restaurant name; empty
states with calls to action; a map link in the Visit section; a "start here" card for hiring managers
on the dashboard.

**Gap to close in phase 2:** re-run the UX crawl for the staff flows it never reached (fix its two
crashes: click the POS "Card" label instead of the hidden radio; wrap the dark-mode full-page
screenshot in try/except) and add 820 px views of the POS and kitchen.

**Operations: verified good** (no work needed): Cloudflare in front of Render; HTTP redirects to HTTPS;
warm latency from Manila 0.3 to 0.5 s; the nightly reset is one transaction and restores the role
groups; production image runs as a non-root user, is 340 MB, serves static files and `500.html`;
gunicorn is PID 1 and shuts down cleanly on SIGTERM (exit 0); a failed migration exits with code 1
and touches no data; peak memory about 154 MiB of 512; CI covers lint, format, tests on Postgres 17,
`check --deploy`, pip-audit, both Docker targets, with least-privilege permissions; CodeQL weekly
and per push; Dependabot for pip, Actions and Docker.

**Open questions for the owner** (from the ops review): is branch protection with required checks
enabled on `main`; how often does Render actually hit `/healthz/` and does a failure restart the
service (decides whether OPS-01 is high or medium); what do the Neon console and plan page show for
compute hours used, remaining quota and the restore window. Render and Neon pricing pages could not
be fetched during the audit, so those limits are unverified.

## 3. Work that is not code (carry-over, owner and agent)

| # | Item | Who | Notes |
| --- | --- | --- | --- |
| C1 | Deploy Abot (renamed from Sahod) | Owner creates `CUSTIX/Abot` repo and says "push"; agent pushes, sets up Render + Neon in a **separate** Render workspace | `render.yaml` service name is `abot-ph` (`abot.onrender.com` is taken). RestoCore alone uses about 744 of the 750 free hours a month |
| C2 | Portfolio update and deploy | Agent edits (done and verified: Abot entry and screenshot, live-demo badges and buttons, hero stat; lint clean, build clean, no console errors on desktop or phone; changes are uncommitted in `C:\Projects\custix`, which is not a git repo); owner deploys to Vercel | `abot-ph.onrender.com` and `github.com/CUSTIX/Abot` links go live only after C1, so deploy the portfolio after Abot is up |
| C3 | Ask RestoCore | Owner adds `GEMINI_API_KEY` in Render | Free key from Google AI Studio. Never paste it in chat |
| C4 | Rotate Neon password | Owner | The old one was pasted in chat once. Reset in Neon, paste the new `DATABASE_URL` into Render only |
| C5 | Confirm `DEMO_RESET_HOUR=4` in Render | Owner | Render should pick it up from `render.yaml`; confirm under Environment |
| C6 | Django 6.1 and Python 3.15 upgrades | Agent, each on its own branch | Deferred major bumps. Run the full suite plus a production-image rehearsal before merging |
| C7 | Client outreach | Owner with agent help | See section 5 |

## 4. Prioritized work plan

Rules for every phase: one change per commit; write the failing test first when the finding is a bug;
run the full suite and ruff before each push; pushing deploys (and reseeds) the live demo, so batch
pushes and avoid 04:00 Manila. Duplicates across reports are fixed once: SEC-02 = OPS-04,
SEC-09 = OPS-01, QA-24 = OPS-12.

| Phase | Goal | Items | Effort |
| --- | --- | --- | --- |
| 0. Quick wins | Cheap, low-risk fixes that remove the most visible problems | OPS-01 (health check to `/livez/`), OPS-03 (DB connection reuse and timeout), OPS-05 (validate reset hour), OPS-06 (reset needs `DEMO_MODE`), OPS-09 (log format), OPS-12 (env docs), SEC-06 (no query strings in access logs), UX-01 (dead Cancel link, plus a test for `javascript:` hrefs), UX-02 (POS focus ring), UX-03 (danger button contrast), UX-16 (drop `preconnect`), QA-18 (MIT license), QA-19 (dead code), QA-25 (README test count) | about 1 day |
| 1. Money, data and security | No wrong payroll, no stale stock, no stuck customer | **COR-01** first (rebuild payslips at finalize), COR-03 (rates sum below 1), COR-05 (`update_fields`), COR-06 (expired self-order on the status page), COR-07 (clock-independent seed), COR-09 and COR-13 (service-level validation), COR-08 (rounding), SEC-01, SEC-03, SEC-05, SEC-07, SEC-08, SEC-10, OPS-04 (gunicorn threads, assistant budget), OPS-02 (deploy only after green CI) | 2 to 3 days |
| 2. Test hardening | Make the safety net trustworthy before bigger refactors | QA-04 and QA-05 (real wrong-role matrix, 403 only, POSTs), QA-09 and QA-10 (payroll, sales, staff POST per role), QA-07 and the threaded tests, QA-08, QA-11, QA-02 (fast hasher), QA-03 (seed once), QA-01 (coverage gate, currently 97%), QA-12, QA-14 to QA-16, QA-23, plus the backlog above | 2 to 3 days |
| 3. UX and accessibility | Works for a cashier on a tablet and for keyboard and screen-reader users | UX-04 (announce errors), UX-05 (tablet POS bar), UX-06 (no reload while typing), UX-07 (kitchen board), UX-08 to UX-15, UX-17, UX-18, UX-21; re-run the UX crawl including the flows it never reached and 820 px views | 2 to 3 days |
| 4. Operations and docs | A stranger could run and recover it | OPS-07 (backup and restore notes), runbook (deploy, rollback, rotate secrets, restore, reseed, logs, heartbeat), OPS-08, OPS-10, OPS-11, OPS-13, OPS-14, `/api/` reference, README quickstart note, QA-26 (soften or close the claim), QA-17, QA-20 to QA-22, QA-27, remaining low UX items (UX-19, UX-20, UX-22, UX-23), SEC-04 (assistant payroll flag) | 2 days |
| 5. Upgrades | Stay current | Django 6.1 and Python 3.15, each on its own branch with the full suite and a production-image rehearsal; Dependabot for `/mcp_server` (SEC-08) | 1 day each |

**Decisions needed from the owner before the related items** (suggested defaults in bold):

1. Paid leave (COR-02): count **scheduled days only** with no balance for now, or add allowances?
2. Overnight shifts (COR-04): **support them** (needed by any real restaurant), or keep the limit and document it?
3. Manager pay-rate edits (SEC-11): **Owner-only**, or leave as is?
4. Will it ever hold real data (SEC-04, SEC-05)? Default: **no, stays a demo**; keep the guards.
5. Booking capacity (COR open question): **keep 40 starting per 30-minute slot** and document it, or model dwell time?
6. Overtime or night differential: **out of scope** for now; label payroll as a demo (already in CLAUDE.md).

**Outside the repo (owner dashboards):** OPS-01 and OPS-02 also need a check in Render (health check
and auto-deploy trigger fields); read the Neon console for compute hours and the restore window; check
branch protection on `main`.

## 5. Finding clients

Be honest with yourself about the goal: a portfolio that gets you interviews and freelance work is
different from selling a restaurant system, which needs support, hosting and trust. Start with the
first, and use café owners as a way to learn. Everything below is free.

**Do first (after Phase 1):** both live demos work and are fast, Abot is live, and the portfolio links
to them with the badges already built. Keep the heartbeat green. A visitor who waits a minute for a
cold start will not come back.

**Where to look:**
- **Local small businesses:** cafés and small restaurants in Bacolod. Offer a free two-week pilot of
  QR table ordering or bookings in exchange for feedback and a testimonial. Show the live demo on a
  phone in person. Do not use a real business's logo or name in public material without their
  permission (the Banwa branding stays local-only).
- **Remote and freelance:** LinkedIn (post a short demo video or the README GIF, not a link alone),
  Philippine developer and small-business Facebook groups, and OnlineJobs.ph for roles with foreign
  employers. Upwork and similar sites are crowded; pick a narrow offer.
- **Your own network:** past DHSUD and school contacts, and the US-based team you already work with.

**A narrow offer sells better than "I build software":** for example "QR ordering and table bookings
for a small café, set up in a week", with RestoCore as the proof. Three sentences: the problem, what
you built, the live link.

**What to prepare:** a 60-second screen recording of the QR order to cashier to kitchen flow; a
one-page case study per project (problem, what you built, result, tech); the README GIFs; a short
intro message you can adapt; and a clear statement that the demos use fake data.

**What not to do:** promise uptime or support you cannot give on free hosting; collect real customer
data in the demo; quote a price before you know the scope.

## 6. Definition of enterprise-ready (tick off at the end)

- [ ] No open critical or high findings; every fixed finding has a test that fails without the fix
- [ ] Every `/app/`, `/api/`, `/order/` and `/book/` route has a per-role test, including POST actions and object-level access
- [ ] Money, stock and payroll paths are atomic and idempotent, with race tests
- [ ] Every page works at phone and desktop width, by keyboard, with no console errors and no horizontal scroll
- [ ] Axe accessibility scan shows no serious or critical issues on the main pages
- [ ] CI blocks a bad deploy (or deploys only after green CI); CI runtime is reasonable
- [ ] Runbook exists: deploy, roll back, rotate secrets, restore the database, reseed the demo, read logs
- [ ] Logs are structured enough to debug a failed request; error pages leak nothing
- [ ] Dependencies are current or deliberately pinned with a reason; audit job green
- [ ] README quickstart works from a clean clone; docs match behaviour; test counts are accurate
- [ ] Coverage reported in CI with a floor for `services.py` modules
- [ ] Abot and the portfolio link to live demos that work
