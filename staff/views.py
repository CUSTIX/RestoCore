import datetime as dt

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import FormView, TemplateView, View

from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import ALL_ROLES, MANAGEMENT
from staff import selectors, services
from staff.forms import (
    AttendanceFilterForm,
    CloseEntryForm,
    EmployeeForm,
    LeaveFilterForm,
    LeaveRequestForm,
    LeaveReviewForm,
    NewEmployeeForm,
    ShiftForm,
    WeekForm,
)
from staff.models import Employee, LeaveRequest, Shift, TimeEntry


def _error_text(exc) -> str:
    return exc.messages[0] if isinstance(exc, ValidationError) else str(exc)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _updated_message(employee) -> str:
    """Confirmation after an edit; a deactivation also says what was cleaned up."""
    done = getattr(employee, "cleanup", None)
    if not done:
        return "Employee updated."
    parts = [f"{_plural(done['shifts'], 'upcoming shift')} removed"]
    if done["leave"]:
        parts.append(f"{_plural(done['leave'], 'pending leave request')} cancelled")
    return f"{employee} deactivated: {', '.join(parts)}. Hours already worked are still paid."


# ---- Self service (every role) ------------------------------------------------------------


class MyWorkView(RoleRequiredMixin, FormView):
    """The signed-in employee's shifts, clock in/out, attendance and leave requests."""

    allowed_roles = ALL_ROLES
    template_name = "staff/me.html"
    form_class = LeaveRequestForm

    @cached_property
    def employee(self):
        return selectors.employee_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = {
            **super().get_context_data(**kwargs),
            "employee": self.employee,
            "active_section": "me",
        }
        if self.employee:
            entry = selectors.open_entry(self.employee)
            ctx.update(
                shifts=selectors.upcoming_shifts(self.employee),
                open_entry=entry,
                # A forgotten clock-in can't be clocked out here: don't offer the button.
                entry_needs_manager=services.entry_needs_manager(entry),
                now_ymd=timezone.localdate().strftime("%Y%m%d"),
                entries=selectors.time_entries(employee=self.employee)[:10],
                leaves=selectors.leave_requests(employee=self.employee)[:10],
            )
        return ctx

    def form_valid(self, form):
        if not self.employee:
            raise PermissionDenied("You do not have an employee profile.")
        try:
            services.request_leave(self.employee, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Leave request sent for approval.")
        return redirect("staff:me")


class ClockView(RoleRequiredMixin, View):
    allowed_roles = ALL_ROLES

    def post(self, request):
        employee = selectors.employee_for_user(request.user)
        if not employee:
            raise PermissionDenied("You do not have an employee profile.")
        try:
            if request.POST.get("action") == "out":
                entry = services.clock_out(employee)
                messages.success(request, f"Clocked out. You worked {entry.hours} hours.")
            else:
                services.clock_in(employee)
                messages.success(request, "Clocked in. Have a good shift!")
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
        return redirect("staff:me")


class LeaveCancelView(RoleRequiredMixin, View):
    allowed_roles = ALL_ROLES

    def post(self, request, pk):
        employee = selectors.employee_for_user(request.user)
        leave = get_object_or_404(LeaveRequest, pk=pk)
        if not employee:
            raise PermissionDenied
        try:
            services.cancel_leave(leave, employee=employee)
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Leave request cancelled.")
        return redirect("staff:me")


# ---- Employees (management) ---------------------------------------------------------------


class EmployeeListView(RoleRequiredMixin, TemplateView):
    allowed_roles = MANAGEMENT
    template_name = "staff/employee_list.html"

    def get_context_data(self, **kwargs):
        q = self.request.GET.get("q", "").strip()
        show_all = self.request.GET.get("all") == "1"
        qs = selectors.filter_employees(q=q, include_inactive=show_all)
        page_obj = paginate(self.request, qs)
        for e in page_obj:  # link only the rows this user may actually edit
            e.can_edit = services.can_edit_employee(self.request.user, e.user)
        return {
            **super().get_context_data(**kwargs),
            "page_obj": page_obj,
            "q": q,
            "show_all": show_all,
            "active_section": "employees",
        }


class EmployeeCreateView(RoleRequiredMixin, FormView):
    allowed_roles = MANAGEMENT
    template_name = "staff/form.html"
    form_class = NewEmployeeForm
    extra_context = {"title": "New employee", "active_section": "employees"}

    def get_initial(self):
        return {"hire_date": timezone.localdate(), "is_active": True, "role": "Staff"}

    def form_valid(self, form):
        data = {k: v for k, v in form.cleaned_data.items() if k != "is_active"}
        try:
            employee = services.create_employee(actor=self.request.user, **data)
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_text(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"{employee} can now log in as {employee.user.username}.")
        return redirect("staff:employee_list")


class EmployeeUpdateView(RoleRequiredMixin, FormView):
    allowed_roles = MANAGEMENT
    template_name = "staff/form.html"
    form_class = EmployeeForm

    @cached_property
    def employee(self):  # loaded only after the role check in dispatch()
        return get_object_or_404(Employee.objects.select_related("user"), pk=self.kwargs["pk"])

    def _check_object_access(self):
        """Object-level check (the role check only says "is a manager"): a manager may not even
        open the form for an owner or another manager. Same rule the service enforces on save."""
        user = self.employee.user
        services.assert_can_manage(
            self.request.user, target_role=services.primary_role(user), target_user=user
        )

    def get(self, request, *args, **kwargs):
        self._check_object_access()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._check_object_access()
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        e, u = self.employee, self.employee.user
        return {
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "role": services.primary_role(u),
            "position": e.position,
            "phone": e.phone,
            "hourly_rate": e.hourly_rate,
            "hire_date": e.hire_date,
            "is_active": e.is_active,
        }

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "title": f"Edit {self.employee}",
            "active_section": "employees",
        }

    def form_valid(self, form):
        try:
            employee = services.update_employee(
                self.employee, actor=self.request.user, **form.cleaned_data
            )
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, _error_text(exc))
            return self.form_invalid(form)
        messages.success(self.request, _updated_message(employee))
        return redirect("staff:employee_list")


# ---- Shifts (management) ------------------------------------------------------------------


class ShiftListView(RoleRequiredMixin, TemplateView):
    allowed_roles = MANAGEMENT
    template_name = "staff/shift_list.html"

    def get_context_data(self, **kwargs):
        form = WeekForm(self.request.GET or None)
        today = timezone.localdate()
        start = (form.cleaned_data.get("start") if form.is_valid() else None) or (
            today - dt.timedelta(days=today.weekday())
        )
        end = start + dt.timedelta(days=6)
        shifts = list(selectors.shifts_between(start, end))
        days = [
            {
                "date": start + dt.timedelta(days=i),
                "is_past": start + dt.timedelta(days=i) < today,
                "shifts": [s for s in shifts if s.date == start + dt.timedelta(days=i)],
            }
            for i in range(7)
        ]
        return {
            **super().get_context_data(**kwargs),
            "week_form": form,
            "start": start,
            "end": end,
            "days": days,
            "prev": start - dt.timedelta(days=7),
            "next": start + dt.timedelta(days=7),
            "active_section": "shifts",
        }


class ShiftEditView(RoleRequiredMixin, FormView):
    allowed_roles = MANAGEMENT
    template_name = "staff/form.html"
    form_class = ShiftForm

    @cached_property
    def shift(self):  # loaded only after the role check in dispatch()
        pk = self.kwargs.get("pk")
        return get_object_or_404(Shift, pk=pk) if pk else None

    def get_initial(self):
        if self.shift:
            return ShiftForm.from_shift(self.shift).initial
        return {"date": self.request.GET.get("date") or timezone.localdate()}

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "title": "Edit shift" if self.shift else "New shift",
            "shift": self.shift,
            "active_section": "shifts",
        }

    def form_valid(self, form):
        try:
            shift = services.save_shift(shift=self.shift, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Shift saved.")
        return redirect(f"{reverse('staff:shift_list')}?start={_week_start(shift.date)}")


class ShiftDeleteView(RoleRequiredMixin, View):
    allowed_roles = MANAGEMENT

    def post(self, request, pk):
        shift = get_object_or_404(Shift, pk=pk)
        week = _week_start(shift.date)
        services.delete_shift(shift)
        messages.success(request, "Shift deleted.")
        return redirect(f"{reverse('staff:shift_list')}?start={week}")


def _week_start(day: dt.date) -> str:
    return (day - dt.timedelta(days=day.weekday())).isoformat()


# ---- Attendance & leave (management) ------------------------------------------------------


class AttendanceListView(RoleRequiredMixin, TemplateView):
    allowed_roles = MANAGEMENT
    template_name = "staff/attendance_list.html"

    @staticmethod
    def _open_entries():
        """Open clock-ins, each with a close form limited to sensible times."""
        now = timezone.localtime().replace(second=0, microsecond=0)
        fmt = "%Y-%m-%dT%H:%M"
        rows = []
        for entry in selectors.clocked_in_now():
            start = timezone.localtime(entry.clock_in)
            latest = min(now, start + dt.timedelta(hours=services.MAX_SHIFT_HOURS))
            stale = now - start > dt.timedelta(hours=services.MAX_SHIFT_HOURS)
            # Suggest the planned shift end (the likely real answer), never the latest allowed
            # time: one careless click on "Close" must not pay a 16-hour shift.
            planned = selectors.scheduled_end(entry.employee_id, start.date())
            suggestion = None
            if planned:
                guess = start.replace(hour=planned.hour, minute=planned.minute)
                if start < guess <= latest:
                    suggestion = guess
            form = CloseEntryForm(initial={"clock_out": suggestion}, auto_id=f"close{entry.pk}_%s")
            form.fields["clock_out"].widget.attrs.update(
                min=(start + dt.timedelta(minutes=1)).strftime(fmt), max=latest.strftime(fmt)
            )
            rows.append({"entry": entry, "stale": stale, "form": form})
        return rows

    def get_context_data(self, **kwargs):
        form = AttendanceFilterForm(self.request.GET or None)
        date = form.cleaned_data.get("date") if form.is_valid() else None
        return {
            **super().get_context_data(**kwargs),
            "filter_form": form,
            "page_obj": paginate(self.request, selectors.time_entries(date=date)),
            "clocked_in": self._open_entries(),
            "active_section": "attendance",
        }


class LeaveListView(RoleRequiredMixin, TemplateView):
    allowed_roles = MANAGEMENT
    template_name = "staff/leave_list.html"

    def get_context_data(self, **kwargs):
        # Default to "pending" whenever no status was chosen, including on ?page=N links.
        data = self.request.GET if "status" in self.request.GET else {"status": "pending"}
        form = LeaveFilterForm(data)
        status = form.cleaned_data["status"] if form.is_valid() else LeaveRequest.Status.PENDING
        page_obj = paginate(self.request, selectors.leave_requests(status=status))
        for leave in page_obj:  # what this reviewer can do, and what approving would change
            if leave.status == LeaveRequest.Status.PENDING:
                leave.review_blocker = services.review_blocker(leave, self.request.user)
                leave.shift_conflicts = services.shifts_during_leave(leave).count()
        return {
            **super().get_context_data(**kwargs),
            "filter_form": form,
            "page_obj": page_obj,
            "review_form": LeaveReviewForm(),
            "active_section": "leave",
        }


class LeaveReviewView(RoleRequiredMixin, View):
    allowed_roles = MANAGEMENT

    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        form = LeaveReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Choose approve or reject.")
            return redirect("staff:leave_list")
        try:
            leave = services.review_leave(
                leave,
                reviewer=request.user,
                approve=form.cleaned_data["decision"] == "approve",
                note=form.cleaned_data["note"],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_text(exc))
        else:
            text = f"Leave {leave.get_status_display().lower()}."
            if leave.removed_shifts:
                n = leave.removed_shifts
                text += f" {n} scheduled shift{'s' if n != 1 else ''} on those days removed."
            messages.success(request, text)
        return redirect("staff:leave_list")


class AttendanceCloseView(RoleRequiredMixin, View):
    """Managers close a forgotten clock-in (otherwise those hours are never paid)."""

    allowed_roles = MANAGEMENT

    def post(self, request, pk):
        entry = get_object_or_404(TimeEntry, pk=pk)
        form = CloseEntryForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter the date and time the person left.")
        else:
            try:
                services.close_entry(entry, at=form.cleaned_data["clock_out"], by=request.user)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_text(exc))
            else:
                messages.success(request, f"Closed {entry.employee}'s clock-in.")
        return redirect("staff:attendance_list")
