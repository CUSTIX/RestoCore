from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from core.roles import has_role


class RoleRequiredMixin(LoginRequiredMixin):
    """Anonymous users go to login; signed-in users without an allowed role get 403."""

    allowed_roles: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_role(request.user, *self.allowed_roles):
            raise PermissionDenied("Your role cannot access this page.")
        return super().dispatch(request, *args, **kwargs)
