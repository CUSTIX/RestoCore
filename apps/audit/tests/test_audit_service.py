import pytest
from django.contrib.auth import get_user_model

from apps.audit.services import record_audit_event


@pytest.mark.django_db
def test_record_audit_event_normalizes_target_and_snapshots():
    actor = get_user_model().objects.create_user(
        email="auditor@example.com",
        password="test-only-password",
    )

    event = record_audit_event(
        action="accounts.permission_changed",
        actor=actor,
        target=actor,
        before={"active": False},
        after={"active": True},
        metadata={"source": "test"},
        ip_address="127.0.0.1",
    )

    assert event.actor == actor
    assert event.target_type == "accounts.user"
    assert event.target_id == str(actor.pk)
    assert event.before == {"active": False}
    assert event.after == {"active": True}
    assert event.metadata == {"source": "test"}


@pytest.mark.django_db
def test_record_audit_event_rejects_blank_action():
    with pytest.raises(ValueError):
        record_audit_event(action="   ")
