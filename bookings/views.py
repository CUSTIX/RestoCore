import datetime as dt

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views.generic import FormView, TemplateView, View

from bookings import selectors, services
from bookings.forms import BookingFilterForm, BookingForm, PublicBookingForm
from bookings.models import Booking
from core import throttle
from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import MANAGEMENT, STAFF

BOOKING_ROLES = (*MANAGEMENT, STAFF)


# ---- Public -------------------------------------------------------------------------------


class PublicBookingView(FormView):
    template_name = "bookings/public_form.html"
    form_class = PublicBookingForm

    def form_valid(self, form):
        data = {k: v for k, v in form.cleaned_data.items() if k != "website"}
        try:
            booking = services.create_public_booking(ip=throttle.client_ip(self.request), **data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return redirect("public_bookings:thanks", reference=booking.reference)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["opening"], ctx["last_seating"] = selectors.opening_hours()
        return ctx


class PublicThanksView(TemplateView):
    template_name = "bookings/public_thanks.html"

    def get_context_data(self, **kwargs):
        booking = selectors.get_by_reference(kwargs["reference"])
        if booking is None:
            raise Http404
        return {**super().get_context_data(**kwargs), "booking": booking}


# ---- Staff --------------------------------------------------------------------------------


class BookingListView(RoleRequiredMixin, TemplateView):
    allowed_roles = BOOKING_ROLES
    template_name = "bookings/list.html"

    def get_context_data(self, **kwargs):
        form = BookingFilterForm(self.request.GET or None)
        filters = form.cleaned_data if form.is_valid() else {}
        qs = selectors.filter_bookings(
            date=filters.get("date"),
            status=filters.get("status", ""),
            q=filters.get("q", ""),
            when=filters.get("when") or selectors.WHEN_UPCOMING,
        )
        return {
            **super().get_context_data(**kwargs),
            "filter_form": form,
            "page_obj": paginate(self.request, qs),
            "summary": selectors.today_summary(),
            "active_section": "bookings",
        }


class BookingDetailView(RoleRequiredMixin, TemplateView):
    allowed_roles = BOOKING_ROLES
    template_name = "bookings/detail.html"

    def get_context_data(self, **kwargs):
        booking = get_object_or_404(Booking, pk=kwargs["pk"])
        transitions = [(s, Booking.Status(s).label) for s in services.allowed_transitions(booking)]
        return {
            **super().get_context_data(**kwargs),
            "booking": booking,
            "transitions": transitions,
            "active_section": "bookings",
        }


class BookingCreateView(RoleRequiredMixin, FormView):
    allowed_roles = BOOKING_ROLES
    template_name = "bookings/form.html"
    form_class = BookingForm
    extra_context = {"active_section": "bookings", "title": "New booking"}

    def form_valid(self, form):
        try:
            booking = services.create_booking(source=Booking.Source.STAFF, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, f"Booking {booking.reference} created.")
        return redirect("bookings:detail", pk=booking.pk)


class BookingUpdateView(RoleRequiredMixin, FormView):
    allowed_roles = BOOKING_ROLES
    template_name = "bookings/form.html"
    form_class = BookingForm
    extra_context = {"active_section": "bookings", "title": "Edit booking"}

    @cached_property
    def booking(self):  # loaded only after the role check in dispatch()
        return get_object_or_404(Booking, pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "instance": self.booking}

    def get(self, request, *args, **kwargs):
        # Closed bookings can't be edited: don't show a form that can never be saved.
        if self.booking.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED):
            messages.info(request, "This booking is closed, so it can't be edited.")
            return redirect("bookings:detail", pk=self.booking.pk)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            services.update_booking(self.booking, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Booking updated.")
        return redirect("bookings:detail", pk=self.booking.pk)


class BookingStatusView(RoleRequiredMixin, View):
    allowed_roles = BOOKING_ROLES

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        try:
            booking = services.change_status(booking, request.POST.get("status", ""))
        except (ValidationError, ValueError) as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        else:
            messages.success(request, f"Booking marked {booking.get_status_display().lower()}.")
        return redirect("bookings:detail", pk=pk)


class AvailabilityView(View):
    """Public JSON for the booking form: seats left per time on one date (counts only)."""

    def get(self, request):
        try:
            day = dt.date.fromisoformat(request.GET.get("date", ""))
        except ValueError:
            return JsonResponse({"error": "Use ?date=YYYY-MM-DD"}, status=400)
        response = JsonResponse({"date": day.isoformat(), "seats": selectors.availability(day)})
        response["Cache-Control"] = "no-store"  # changes with every booking
        return response
