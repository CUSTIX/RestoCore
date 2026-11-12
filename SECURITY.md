# Security

RestoCore is a portfolio project; **all data in it is fake**. Even so, it is built the way a real
restaurant system holding staff and payroll data should be.

## Reporting a problem

Please open a private report through GitHub: **Security → Report a vulnerability** on this
repository. Don't open a public issue for security problems.

## What protects what

**Access control**
- Roles are Django Groups (Owner, Manager, Cashier, Kitchen, Staff). Every staff view checks the
  role *before* loading any object, and object-level rules live in the services (for example: only
  an owner can edit an owner or manager; nobody approves their own leave; staff only cancel their
  own requests).
- A test walks the whole URLconf and fails if any `/app/` URL lets an anonymous visitor or a
  signed-in user without a role through, or if any `/api/` URL answers without a token.
- The read-only API needs `Authorization: Bearer <token>`, compared in constant time; it is off
  unless a token is configured.

**Sign-in**
- Failed sign-ins are throttled (stored in Postgres, so every worker sees them): 5 per username +
  IP or 30 per IP in 15 minutes. Locking is per username *and* IP, so a stranger can't lock a real
  user out from somewhere else.
- The visitor IP is read only from a header the proxy overwrites (`CLIENT_IP_HEADER`, e.g.
  Cloudflare's `CF-Connecting-IP`), never from a raw `X-Forwarded-For` that callers can forge.
- Django's password validators; sessions end after 12 hours; session and CSRF cookies are
  `HttpOnly`, and `Secure` + HSTS when served over HTTPS.

**Browser-side**
- A strict **Content Security Policy**: `script-src 'self'`, so no inline JavaScript, `eval`, or
  third-party scripts can run. Templates use `data-*` attributes instead of `onclick=...`, and a
  test fails if any template gains an inline script or event handler.
- `X-Frame-Options: DENY` + `frame-ancestors 'none'` (no clickjacking), `nosniff`,
  `Referrer-Policy: same-origin`, `Cross-Origin-Opener/Resource-Policy: same-origin`, and a
  `Permissions-Policy` that switches off camera, microphone, location and payment APIs.
- Signed-in pages are sent with `Cache-Control: no-store`, so "Back" after logging out on a shared
  POS terminal shows nothing.
- Django templates auto-escape everything; the only `mark_safe` is for the app's own fixed SVG
  icons. Client-side code builds DOM nodes with `textContent`, never `innerHTML` with user data.

**Data**
- All writes go through forms/services with validation; money is `Decimal`; multi-step writes
  are transactions with row locks where races matter (booking capacity, stock).
- Secrets come only from environment variables. `.env` and the `local/` branding folder are
  gitignored.

**Public demo** (`DEMO_MODE=true`)
- Demo accounts are listed on the login page and all data is wiped and reseeded on every start.
- Password changes are disabled and no account gets Django admin, so one visitor can't lock
  out or take over the demo for the next.

**Supply chain and CI**
- Every dependency is pinned. CI runs `pip-audit` against the PyPI advisory database, ruff's
  security rules (flake8-bandit), `manage.py check --deploy` in HTTPS mode, and the full test suite
  on every push and pull request. CodeQL scans Python and JavaScript weekly and on every change;
  Dependabot proposes updates for Python packages, GitHub Actions and the Docker base image.
- The production image runs as a non-root user and contains no test tools.
