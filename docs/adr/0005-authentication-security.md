# ADR 0005: Authentication security baseline

## Status

Accepted.

## Decision

RestoCore uses django-axes for login attempt tracking and lockout, with the Axes standalone authentication backend before Django's ModelBackend and Axes middleware last in the middleware chain.

RestoCore also installs django-otp and its TOTP plugin. Multi-factor authentication is required by policy for owner, payroll, and superuser accounts, but enforcement is deferred until a safe device-enrollment and recovery flow exists.

## Why

Rate limiting is safe to enable immediately. Mandatory OTP without enrollment and recovery would create an account lockout risk, so policy and middleware are established first and enforcement follows with the enrollment workflow.

## Consequences

- Default login failure limit is five attempts with a 15-minute cooldown and can be overridden by environment variables.
- OTP-aware request state is available through django-otp middleware.
- Owner, payroll, and superuser routes must enforce verified MFA once enrollment is implemented.
- Recovery codes and administrator recovery procedures must exist before enforcement is enabled.
