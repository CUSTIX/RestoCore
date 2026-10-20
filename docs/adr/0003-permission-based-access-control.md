# ADR 0003: Permission-based access control

## Status

Accepted.

## Decision

RestoCore uses Django Groups to represent operational roles and Django Permissions to represent capabilities.

Application code checks granular permissions, never role names. Each domain owns its permission codenames. A version-controlled role matrix maps the default groups (owner, manager, cashier, kitchen, waiter, and payroll) to those permissions.

Protected views redirect anonymous users to login and return HTTP 403 to authenticated users who lack the required capability. Internal navigation is derived from the same permission checks and is presentation only; route authorization remains authoritative.

## Why

Roles change more often than business capabilities. Checking permissions keeps views stable when responsibilities move between roles, supports future custom roles, and avoids duplicated authorization rules across templates and views.

## Consequences

- Permission changes require tests and code review.
- New modules define permissions in their own Django app.
- Queryset and object-level authorization must still be added when domain models exist.
- Hiding a navigation item never replaces server-side authorization.
