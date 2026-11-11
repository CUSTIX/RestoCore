# QA checklist (v1)

Setup: `docker compose down -v`, `docker compose up --build`, then
`docker compose run --rm web python manage.py seed_demo`. Password for every account: `restocore-demo`.
The login page lists the demo accounts (local DEBUG only) and fills them in with one click.

## Public site (logged out)
- [ ] Home: photo stack shuffles every few seconds, ticker scrolls, stats count up, sections reveal on scroll.
- [ ] Home "The ritual": the kettle-and-cup scene stays pinned while the three steps scroll past; the
      kettle tilts and pours, the cup fills (percentage counts up), the step in view lights up, and
      steam rises when it reads "Ready to sip". On phones the scene pins under the navbar.
- [ ] Navbar: highlight glides between links on hover; "Open / Closed" chip matches the time;
      navbar narrows after scrolling; theme toggle switches light / dark and is remembered.
- [ ] House favourites: hovering a dish with a mouse shows a floating photo next to the cursor.
- [ ] `/menu/`: only available items; category bar is centred under the navbar and highlights the
      section you are reading; tapping a category jumps to it.
- [ ] `/book/`: time chips and +/− guest stepper work; valid booking → thanks page with reference.
- [ ] Booking in the past, outside hours, or party size 0 / 21 → error, nothing saved.
- [ ] Fill one slot with 40 guests → next booking at that time says "fully booked".
- [ ] `/app/` redirects to login. Unknown URL shows the 404 page.

## owner
- [ ] Sidebar shows every section including **Payroll (demo)**; `/admin/` works; sidebar collapses to icons.
- [ ] Payroll: create a period, Generate, open a payslip, Finalize → Generate is no longer offered.
- [ ] Payroll → Deduction rates: change a rate, regenerate a draft period, totals change.
- [ ] Employees: create a Manager; edit a Manager; cannot deactivate or demote yourself.

## manager
- [ ] No Payroll link; `/app/payroll/` → 403 page.
- [ ] Bookings: filter by date/status/search; confirm → seat → complete; cancelled is final.
- [ ] Menu: add a category; add a dish with a photo and recipe; price 0 is rejected.
- [ ] Inventory: new item, receive, waste more than on hand (error), stock count.
- [ ] Orders: void a paid order with a reason → ingredients go back (not if already served).
- [ ] Employees: creating an Owner or Manager is refused ("Only an owner…").
- [ ] Schedules: add a shift, overlapping shift is refused, shift on approved leave is refused.
- [ ] Leave: approve / reject others; your own request says another manager or the owner reviews it.

## cashier
- [ ] Sidebar: Dashboard, Point of sale, Orders, My work only.
- [ ] POS: tap a dish card or use +/− ; cart and totals update live; dine-in without table → error;
      cash below total → error; Takeaway hides the table field, Card hides cash received.
- [ ] Order too large for stock → "Not enough stock…", no order created, stock unchanged.
- [ ] Successful checkout → receipt with change; Print receipt hides the sidebar.
- [ ] No void form on orders; `/app/inventory/` → 403.

## kitchen
- [ ] Kitchen board: Queued → Preparing → Ready columns; timers turn red after 15 minutes;
      Start preparing → Mark ready → Mark served moves the ticket.
- [ ] Inventory visible, can receive/waste/count, but no New item / Edit item.

## staff
- [ ] Bookings visible and editable; POS, inventory, employees → 403.
- [ ] My work: clock in, clock in again (error), clock out; request leave; cancel a pending request.

## Every role
- [ ] Change password works; log out returns to the home page.
- [ ] Dark mode in the staff area (sun/moon button in the top bar).

## Phones and tablets
- [ ] Public: navbar becomes logo + theme + "Menu" button with a drop-down sheet; no sideways scroll.
- [ ] Staff: ☰ opens the sidebar drawer; tap outside or Esc closes it.
- [ ] Tables (bookings, orders, inventory…) show as one card per row on phones.
- [ ] POS on a phone: dishes two per row; a bottom bar shows item count + total with Checkout.
- [ ] Tapping a form field does not zoom the page on iPhone.

## Production-style stack
- [ ] `docker compose -f docker-compose.prod.yml -p restocore-prod up --build -d`, seed, open
      <http://127.0.0.1:8080/>: same app under gunicorn, static files load, DEBUG off (real 404 page).

## MCP / API
- [ ] `curl -H "Authorization: Bearer local-dev-api-token" http://127.0.0.1:8000/api/menu/` returns JSON.
- [ ] Without the header → 401. See [mcp.md](mcp.md) to connect an MCP client.
