MFA_REQUIRED_GROUPS = frozenset({"owner", "payroll"})


def requires_mfa(user) -> bool:
    """Return whether the account policy requires multi-factor authentication."""

    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=MFA_REQUIRED_GROUPS).exists()


def is_mfa_verified(user) -> bool:
    """Read django-otp verification state without coupling callers to middleware details."""

    verifier = getattr(user, "is_verified", None)
    return bool(verifier and verifier())
