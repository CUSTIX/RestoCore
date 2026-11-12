from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView, View

from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import OWNER
from payroll import selectors, services
from payroll.forms import DeductionRateFormSet, PeriodForm
from payroll.models import PayPeriod, Payslip
from staff import selectors as staff_selectors

PAYROLL_ROLES = (OWNER,)


class PeriodListView(RoleRequiredMixin, FormView):
    allowed_roles = PAYROLL_ROLES
    template_name = "payroll/period_list.html"
    form_class = PeriodForm

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "page_obj": paginate(self.request, selectors.periods()),
            "rates": selectors.deduction_rates().filter(is_active=True),
            "active_section": "payroll",
        }

    def form_valid(self, form):
        try:
            period = services.create_period(user=self.request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Pay period created. Generate payslips next.")
        return redirect("payroll:period_detail", pk=period.pk)


class PeriodDetailView(RoleRequiredMixin, TemplateView):
    allowed_roles = PAYROLL_ROLES
    template_name = "payroll/period_detail.html"

    def get_context_data(self, **kwargs):
        period = get_object_or_404(PayPeriod, pk=kwargs["pk"])
        return {
            **super().get_context_data(**kwargs),
            "period": period,
            # Unclosed clock-ins aren't paid: show them so the owner fixes them before finalizing.
            "can_finalize": services.period_has_ended(period),
            "open_entries": staff_selectors.open_entries_between(period.start_date, period.end_date)
            if period.status == PayPeriod.Status.DRAFT
            else [],
            "payslips": selectors.payslips_for(period),
            "totals": selectors.period_totals(period),
            "active_section": "payroll",
        }


class PeriodActionView(RoleRequiredMixin, View):
    allowed_roles = PAYROLL_ROLES

    def post(self, request, pk):
        period = get_object_or_404(PayPeriod, pk=pk)
        action = request.POST.get("action")
        try:
            if action == "generate":
                count = services.generate_payslips(period)
                messages.success(request, f"Generated {count} payslip{'s' if count != 1 else ''}.")
            elif action == "finalize":
                services.finalize_period(period)
                messages.success(request, "Pay period finalized. Payslips are now locked.")
            else:
                messages.error(request, "Unknown action.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect("payroll:period_detail", pk=pk)


class PayslipDetailView(RoleRequiredMixin, TemplateView):
    allowed_roles = PAYROLL_ROLES
    template_name = "payroll/payslip.html"

    def get_context_data(self, **kwargs):
        slip = get_object_or_404(
            Payslip.objects.select_related("period").prefetch_related("deductions"),
            pk=kwargs["pk"],
        )
        return {**super().get_context_data(**kwargs), "slip": slip, "active_section": "payroll"}


class DeductionRatesView(RoleRequiredMixin, TemplateView):
    allowed_roles = PAYROLL_ROLES
    template_name = "payroll/rates.html"

    def get_context_data(self, formset=None, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "formset": formset or DeductionRateFormSet(queryset=selectors.deduction_rates()),
            "active_section": "payroll",
        }

    def post(self, request):
        formset = DeductionRateFormSet(request.POST, queryset=selectors.deduction_rates())
        if formset.is_valid():
            formset.save()
            messages.success(
                request, "Deduction rates saved. They apply to newly generated payslips."
            )
            return redirect("payroll:rates")
        return self.render_to_response(self.get_context_data(formset=formset))
