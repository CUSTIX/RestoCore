from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from .mixins import ProtectedPermissionMixin


@require_GET
def healthz(request):
    """Return process health without depending on external services."""
    return JsonResponse({"status": "ok", "service": "restocore"})


class WorkspaceView(ProtectedPermissionMixin, TemplateView):
    template_name = "internal/workspace.html"
    permission_required = "core.access_internal"
    raise_exception = True


class ModuleLandingView(ProtectedPermissionMixin, TemplateView):
    """Reusable protected landing page for a module skeleton."""

    template_name = "internal/module_landing.html"
    permission_required = ()
    raise_exception = True
    module_name = ""
    module_description = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["module_name"] = self.module_name
        context["module_description"] = self.module_description
        return context
