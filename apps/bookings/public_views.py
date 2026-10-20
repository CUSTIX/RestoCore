from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from .forms import PublicBookingForm


class PublicBookingView(FormView):
    template_name = "bookings/public_booking.html"
    form_class = PublicBookingForm
    success_url = reverse_lazy("booking_public:success")

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class PublicBookingSuccessView(TemplateView):
    template_name = "bookings/public_booking_success.html"
