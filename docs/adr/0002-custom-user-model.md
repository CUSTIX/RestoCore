# ADR 0002: Create the custom user model before the first migration

- Status: Accepted
- Date: 2026-10-20

## Context

Replacing Django's user model after migrations and foreign keys exist is disruptive. RestoCore will attach employee profiles, roles, audit events, and object-level access rules to users.

## Decision

Create `accounts.User` from `AbstractUser` before feature development and use unique email addresses as the authentication identifier. Remove Django's username field and keep employee-specific data out of the identity model.

A project-owned user manager handles normal and superuser creation. All foreign keys must reference `settings.AUTH_USER_MODEL`.

## Consequences

- Login is email-based across internal roles.
- Employee profile and HR fields remain in the staff domain rather than the account model.
- Future identity fields can be added without replacing Django's user model.
- Code and tests must not depend on a username field.
