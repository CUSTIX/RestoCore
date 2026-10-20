from django.db import transaction

from apps.audit.services import record_audit_event

from .models import Booking


class InvalidBookingTransition(ValueError):
    pass


ALLOWED_TRANSITIONS = {
    Booking.Status.PENDING: {
        Booking.Status.CONFIRMED,
        Booking.Status.CANCELLED,
    },
    Booking.Status.CONFIRMED: {
        Booking.Status.SEATED,
        Booking.Status.CANCELLED,
    },
    Booking.Status.SEATED: {
        Booking.Status.COMPLETED,
    },
    Booking.Status.COMPLETED: set(),
    Booking.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_booking(*, booking_id: int, new_status: str, actor) -> Booking:
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    old_status = booking.status

    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise InvalidBookingTransition(
            f"Cannot move booking from {old_status!r} to {new_status!r}."
        )

    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])

    record_audit_event(
        action="bookings.status_changed",
        actor=actor,
        target=booking,
        before={"status": old_status},
        after={"status": new_status},
    )
    return booking
