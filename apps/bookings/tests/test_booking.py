from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bookings.models import Booking


@pytest.mark.django_db
def test_booking_defaults_to_pending():
    booking = Booking.objects.create(
        guest_name="Sample Guest",
        party_size=4,
        starts_at=timezone.now() + timedelta(days=1),
    )

    assert booking.status == Booking.Status.PENDING
    assert booking.party_size == 4


@pytest.mark.django_db
def test_booking_rejects_zero_party_size():
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(
            guest_name="Invalid Guest",
            party_size=0,
            starts_at=timezone.now() + timedelta(days=1),
        )
