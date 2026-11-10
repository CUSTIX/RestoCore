from django.views.generic import TemplateView

from bookings import selectors as bookings
from core.mixins import RoleRequiredMixin
from core.roles import ALL_ROLES, CASHIER, KITCHEN, MANAGEMENT, STAFF, has_role
from inventory import selectors as inventory
from sales import selectors as sales
from staff import selectors as staff


class DashboardView(RoleRequiredMixin, TemplateView):
    """One page, different cards per role. Each block only queries what that role can see."""

    allowed_roles = ALL_ROLES
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        ctx = {**super().get_context_data(**kwargs), "active_section": "dashboard"}
        employee = staff.employee_for_user(user)
        if employee:
            ctx["my_shifts"] = staff.upcoming_shifts(employee, days=7)[:3]
            ctx["my_open_entry"] = staff.open_entry(employee)
        if has_role(user, *MANAGEMENT, STAFF):
            ctx["bookings"] = bookings.today_summary()
            ctx["upcoming_bookings"] = bookings.upcoming(limit=8)
        if has_role(user, *MANAGEMENT, CASHIER):
            ctx["sales"] = sales.sales_summary()
            week = sales.daily_revenue(7)
            peak = max((d["revenue"] for d in week), default=0) or 1
            ctx["week"] = [{**d, "pct": int(d["revenue"] * 100 / peak)} for d in week]
        if has_role(user, *MANAGEMENT, KITCHEN):
            ctx["kitchen_count"] = sales.kitchen_queue().count()
            ctx["low_stock"] = inventory.low_stock_items()[:8]
        if has_role(user, *MANAGEMENT):
            ctx["pending_leave"] = staff.pending_leave_count()
            ctx["clocked_in"] = staff.clocked_in_now()
        return ctx
