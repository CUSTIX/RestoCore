from typing import Any

from django.db import models

from .models import AuditEvent


def record_audit_event(
    *,
    action: str,
    actor=None,
    target: models.Model | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Persist a normalized audit event without coupling domains to audit storage details."""

    action = action.strip()
    if not action:
        raise ValueError("Audit action must not be blank.")

    target_type = ""
    target_id = ""
    if target is not None:
        target_type = target._meta.label_lower
        target_id = str(target.pk) if target.pk is not None else ""

    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before or {},
        after=after or {},
        metadata=metadata or {},
        ip_address=ip_address,
    )
