# ADR 0005: Authentication security baseline

## Status

Accepted.

## Decision

RestoCore uses django-axes for login attempt tracking and lockout, with the Axes standalone authentication backend before Django's ModelBackend and Axes middleware last in the middleware chain.

RestoCore uses django-otp with TOTP authenticators and one-time static recovery codes. Multi-factor authentication is required for owner, payroll, and superuser accounts before they can enter internal or Django-admin surfaces.

Unenrolled MFA-required accounts are redirected to Account Security. Enrolled but unverified accounts are redirected to a verification challenge. Public website routes remain accessible without forcing an MFA challenge merely because the visitor is already signed in.

## Why

High-privilege restaurant and payroll accounts require stronger protection than password-only authentication. Central middleware enforcement ensures future internal modules inherit the same policy without duplicating checks in each view.

## Consequences

- Default login failure limit is five attempts with a 15-minute cooldown and can be overridden by environment variables.
- Owner, payroll, and superuser accounts must enroll a TOTP authenticator before internal access.
- A successful enrollment verifies the current session immediately.
- TOTP codes and one-time recovery codes can satisfy the MFA challenge.
- Recovery-code rotation invalidates all previous recovery codes.
- Public website routes do not require an MFA challenge.
- MFA enrollment and recovery-code rotation are written to the audit log.
