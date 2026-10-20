from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.bookings.models import Booking
from apps.bookings.services import InvalidBookingTransition, transition_booking


@pytest.fixture
def manager_user():
    user = get_user_model().objects.create_user(
        email="booking-manager@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="manager"))
    return user


@pytest.fixture
def pending_booking():
    return Booking.objects.create(
        guest_name="Booking Guest",
        guest_email="booking@example.com",
        party_size=3,
        starts_at=timezone.now() + timedelta(days=1),
    )


@pytest.mark.django_db
def test_booking_workspace_lists_requests(client, manager_user, pending_booking):
    client.force_login(manager_user)

    response = client.get(reverse("bookings:home"))

    assert response.status_code == 200
    assert b"Booking Guest" in response.content
    assert b"Confirm" in response.content


@pytest.mark.django_db
def test_booking_status_update_requires_post(client, manager_user, pending_booking):
    client.force_login(manager_user)

    response = client.get(reverse("bookings:status", args=[pending_booking.pk]))

    assert response.status_code == 405


@pytest.mark.django_db
def test_manager_can_confirm_pending_booking(client, manager_user, pending_booking):
    client.force_login(manager_user)

    response = client.post(
        reverse("bookings:status", args=[pending_booking.pk]),
        {"status": Booking.Status.CONFIRMED},
    )

    assert response.status_code == 302
    pending_booking.refresh_from_db()
    assert pending_booking.status == Booking.Status.CONFIRMED
    assert AuditEvent.objects.filter(
        actor=manager_user,
        action="bookings.status_changed",
        target_id=str(pending_booking.pk),
    ).exists()


@pytest.mark.django_db
def test_transition_service_rejects_invalid_jump(manager_user, pending_booking):
    with pytest.raises(InvalidBookingTransition):
        transition_booking(
            booking_id=pending_booking.pk,
            new_status=Booking.Status.COMPLETED,
            actor=manager_user,
        )

    pending_booking.refresh_from_db()
    assert pending_booking.status == Booking.Status.PENDING


@pytest.mark.django_db
def test_booking_filter_limits_results(client, manager_user, pending_booking):
    Booking.objects.create(
        guest_name="Confirmed Guest",
        guest_email="confirmed@example.com",
        party_size=2,
        starts_at=timezone.now() + timedelta(days=2),
        status=Booking.Status.CONFIRMED,
    )
    client.force_login(manager_user)

    response = client.get(reverse("bookings:home"), {"status": Booking.Status.CONFIRMED})

    assert response.status_code == 200
    assert b"Confirmed Guest" in response.content
    assert b"Booking Guest" not in response.content
