import datetime as dt
import threading

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from bookings import services
from bookings.models import Booking
from bookings.tests.test_services import booking_data


@pytest.mark.django_db(transaction=True, serialized_rollback=True)  # keep migration data
def test_two_simultaneous_bookings_cannot_overbook_an_empty_slot(tomorrow):
    """Two parties of 20+5 race for a 40-seat slot that already has 20 guests: only one wins."""
    services.create_booking(**booking_data(tomorrow, party_size=20, time=dt.time(19, 0)))
    start = threading.Barrier(2)
    results = []

    def book():
        try:
            start.wait()
            services.create_booking(**booking_data(tomorrow, party_size=15, time=dt.time(19, 0)))
            results.append("ok")
        except ValidationError:
            results.append("full")
        finally:
            connection.close()

    threads = [threading.Thread(target=book) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["full", "ok"]
    assert sum(Booking.objects.values_list("party_size", flat=True)) == 35


@pytest.mark.django_db
def test_update_uses_database_status_not_stale_copy(tomorrow):
    booking = services.create_booking(**booking_data(tomorrow))
    stale = Booking.objects.get(pk=booking.pk)
    services.change_status(booking, Booking.Status.CANCELLED)
    with pytest.raises(ValidationError, match="Only pending or confirmed"):
        services.update_booking(stale, **booking_data(tomorrow, party_size=2))
