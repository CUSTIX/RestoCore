from django.contrib import admin

from bookings.models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "date", "time", "party_size", "status", "source")
    list_filter = ("status", "source", "date")
    search_fields = ("reference", "name", "phone", "email")
