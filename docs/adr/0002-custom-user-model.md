# ADR 0002: Create the custom user model before the first migration

- Status: Accepted
- Date: 2026-10-20

## Context

Replacing Django's user model after migrations and foreign keys exist is disruptive. RestoCore will later attach employee profiles, roles, audit events, and object-level access rules to users.

## Decision

Create `accounts.User` from `AbstractUser` before the first migration. Keep Django's username login identifier for now and require a unique email address. Alternative login behavior can be added through an authentication backend without replacing the model.

## Consequences

- Future identity fields can be added safely to the project-owned user model.
- Staff accounts are not forced into email-only login before POS and employee-login requirements are known.
- All foreign keys must reference `settings.AUTH_USER_MODEL`, never Django's concrete `User` class.
