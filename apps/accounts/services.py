"""Account-domain services."""

from django.contrib.auth.models import Group, Permission

from .roles import ROLE_PERMISSIONS


def sync_role_groups() -> None:
    """Make Group permissions match the version-controlled role matrix."""

    permissions = {
        f"{permission.content_type.app_label}.{permission.codename}": permission
        for permission in Permission.objects.select_related("content_type")
    }

    for role_name, permission_labels in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        group.permissions.set(
            permissions[label] for label in permission_labels if label in permissions
        )
