# ADR 0004: Audit and money foundation

## Status

Accepted.

## Decision

RestoCore records sensitive actions through a dedicated audit app and a single audit service. Domain code supplies the action, actor, target, and before/after snapshots without depending on audit table details.

Money is normalized through a shared Decimal-based utility. Binary floating-point values are rejected at the boundary. Database money fields should use DecimalField and the shared precision constants unless a domain has a documented reason to differ.

## Why

Money, stock, payroll, permission changes, and voids require reliable historical evidence. A dedicated audit boundary avoids duplicated logging schemas and keeps future retention or export changes isolated.

Using Decimal prevents binary floating-point rounding errors and keeps Philippine peso/centavo calculations deterministic.

## Consequences

- Sensitive domain services must call the audit service inside the same business transaction where appropriate.
- Audit records are append-oriented and read-only in Django admin.
- Object-level authorization and domain-specific audit hooks will be added when real models exist.
- Floats are not accepted for money calculations.
