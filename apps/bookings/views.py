from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import ListView

from apps.core.mixins import ProtectedPermissionMixin

from .models import Booking
from .services import InvalidBookingTransition, transition_booking


class BookingListView(ProtectedPermissionMixin, ListView):
    permission_required = "bookings.access_bookings"
    template_name = "bookings/internal_list.html"
    context_object_name = "bookings"
    paginate_by = 25

    def get_queryset(self):
        queryset = Booking.objects.all().order_by("starts_at", "id")
        status = self.request.GET.get("status")
        valid_statuses = {value for value, _ in Booking.Status.choices}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        return queryset


class BookingStatusUpdateView(ProtectedPermissionMixin, View):
    permission_required = "bookings.manage_bookings"

    def post(self, request, pk):
        new_status = request.POST.get("status", "")
        try:
            transition_booking(
                booking_id=pk,
                new_status=new_status,
                actor=request.user,
            )
        except Booking.DoesNotExist as exc:
            raise Http404 from exc
        except InvalidBookingTransition:
            messages.error(request, "That booking status change is not allowed.")
        else:
            messages.success(request, "Booking status updated.")

        return redirect("bookings:home")
