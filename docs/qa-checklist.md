# QA checklist (v1)

Setup: `docker compose down -v`, `docker compose up --build`, then
`docker compose run --rm web python manage.py seed_demo`. Password for every account: `restocore-demo`.

## Public (logged out)
- [ ] `/` shows hero, hours and featured dishes; `/menu/` lists only available items.
- [ ] `/book/`: valid booking → thanks page with an 8-character reference.
- [ ] Booking in the past, outside hours, or party size 0 / 21 → error, nothing saved.
- [ ] Fill one slot with 40 guests → next booking at that time says "fully booked".
- [ ] `/app/` redirects to login.

## owner
- [ ] Sidebar shows every section including **Payroll (demo)**; `/admin/` works.
- [ ] Payroll: create a period, Generate, open a payslip, Finalize → Generate is no longer offered.
- [ ] Payroll → Deduction rates: change a rate, regenerate a draft period, totals change.
- [ ] Employees: create a Manager; edit a Manager; cannot deactivate or demote yourself.

## manager
- [ ] No Payroll link; `/app/payroll/` → 403.
- [ ] Bookings: filter by date/status/search; confirm → seat → complete; cancelled is final.
- [ ] Menu: add a category, add a dish with a recipe; price 0 is rejected.
- [ ] Inventory: new item, receive, waste more than on hand (error), stock count.
- [ ] Orders: void a paid order with a reason → ingredients go back (not if already served).
- [ ] Employees: creating an Owner or Manager is refused ("Only an owner…").
- [ ] Schedules: add a shift, overlapping shift is refused, shift on approved leave is refused.
- [ ] Leave: approve / reject others; your own request shows "another manager or the owner reviews it".

## cashier
- [ ] Sidebar: Dashboard, Point of sale, Orders, My work only.
- [ ] POS: live total updates; dine-in without table → error; cash below total → error.
- [ ] Order too large for stock → "Not enough stock…", no order created, stock unchanged.
- [ ] Successful checkout → receipt page with change; Print receipt hides the sidebar.
- [ ] No void form on orders; `/app/inventory/` → 403.

## kitchen
- [ ] Kitchen board: Start preparing → Mark ready → Mark served; served orders leave the board.
- [ ] Inventory visible, can receive/waste/count, but no New item / Edit item.

## staff
- [ ] Bookings visible and editable; POS, inventory, employees → 403.
- [ ] My work: clock in, clock in again (error), clock out; request leave; cancel a pending request.

## Every role
- [ ] Change password works; log out returns to the home page.
- [ ] Pages are usable at phone width (no sideways scrolling).

## MCP / API
- [ ] `curl -H "Authorization: Bearer local-dev-api-token" http://127.0.0.1:8000/api/menu/` returns JSON.
- [ ] Without the header → 401. See [mcp.md](mcp.md) to connect an MCP client.
