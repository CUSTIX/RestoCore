# ADR 0001: Use a modular monolith

- Status: Accepted
- Date: 2026-10-20

## Context

RestoCore combines public pages and connected restaurant operations. A solo developer needs clear module boundaries without the operational cost and failure modes of distributed services.

## Decision

Build one Django deployment and one PostgreSQL database. Separate business ownership through Django applications under `apps/`, explicit URL namespaces, and documented dependency rules.

## Consequences

- Transactions across orders, inventory, staff, and payroll remain straightforward.
- Local development and deployment stay understandable.
- Module boundaries must be protected through review and tests because the runtime does not enforce them.
- A module may be extracted later only when measured scaling or ownership pressure justifies it.
