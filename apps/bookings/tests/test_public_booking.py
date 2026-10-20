from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking


@pytest.mark.django_db
def test_public_booking_page_loads(client):
    response = client.get(reverse("booking_public:create"))

    assert response.status_code == 200
    assert b"Request a reservation" in response.content


@pytest.mark.django_db
def test_valid_public_booking_creates_pending_request(client):
    starts_at = timezone.localtime(timezone.now() + timedelta(days=1))

    response = client.post(
        reverse("booking_public:create"),
        {
            "guest_name": "Sample Guest",
            "guest_email": "guest@example.com",
            "guest_phone": "",
            "party_size": 4,
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "notes": "Window seat if available",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("booking_public:success")
    booking = Booking.objects.get()
    assert booking.status == Booking.Status.PENDING
    assert booking.guest_email == "guest@example.com"


@pytest.mark.django_db
def test_public_booking_requires_a_contact_method(client):
    starts_at = timezone.localtime(timezone.now() + timedelta(days=1))

    response = client.post(
        reverse("booking_public:create"),
        {
            "guest_name": "Sample Guest",
            "guest_email": "",
            "guest_phone": "",
            "party_size": 2,
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert Booking.objects.count() == 0
    assert b"Provide an email address or phone number." in response.content


@pytest.mark.django_db
def test_public_booking_rejects_past_time(client):
    starts_at = timezone.localtime(timezone.now() - timedelta(hours=1))

    response = client.post(
        reverse("booking_public:create"),
        {
            "guest_name": "Sample Guest",
            "guest_email": "guest@example.com",
            "guest_phone": "",
            "party_size": 2,
            "starts_at": starts_at.strftime("%Y-%m-%dT%H:%M"),
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert Booking.objects.count() == 0
    assert b"Choose a reservation time in the future." in response.content
