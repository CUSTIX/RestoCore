# RestoCore Architecture

## Architectural style

RestoCore is a modular monolith. It deploys as one Django application, while business ownership is separated by Django application boundaries.

## Module ownership

| Module | Initial responsibility |
| --- | --- |
| `core` | Shared technical infrastructure and abstract primitives; no restaurant business entities |
| `accounts` | Authentication identity and authorization integration |
| `website` | Public restaurant pages and showcase content |
| `bookings` | Reservations and booking rules |
| `orders` | Orders, order items, lifecycle, and order-domain rules |
| `pos` | Cashier-facing workflows that orchestrate the order domain |
| `inventory` | Ingredients, utensils, decorations, stock, and stock movements |
| `staff` | Employee profiles, attendance, schedules, breaks, and requests |
| `payroll` | Payroll runs, configurable statutory tables, and payslips |
| `reports` | Read models and reporting queries across modules |

## Dependency rules

1. `config` wires applications together but contains no business logic.
2. Business entities belong to one owning module; do not place them in `core` merely because several modules use them.
3. Cross-module writes will use explicit application services once such coordination exists.
4. Direct ORM queries are acceptable inside the owning module. Add selectors or services when real complexity appears, not pre-emptively.
5. Templates use shared layouts and components. Pages compose them rather than duplicating navigation or shell markup.
6. Authorization will be enforced at the view, queryset, and template layers. Template visibility is not a security boundary.
7. `orders` owns order state. `pos` provides cashier workflows and must not duplicate order records or status logic.

## Data conventions

- PostgreSQL is the authoritative runtime database.
- `USE_TZ` remains enabled; timestamps are stored in UTC and displayed in `Asia/Manila`.
- Monetary values use integer centavos or `Decimal`, never binary floating point.
- Stock and money mutations will be auditable.
- Inventory categories such as ingredients, utensils, and decorations remain one inventory domain unless their rules materially diverge.

## Deferred decision

A dining table is a shared restaurant resource used by both bookings and dine-in orders. It must not be placed in `core`. Before implementing either feature, write an ADR choosing a dedicated owning context such as `floor` or `restaurant`.
