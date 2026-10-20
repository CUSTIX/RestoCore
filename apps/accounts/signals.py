from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .services import sync_role_groups


@receiver(post_migrate, dispatch_uid="accounts.sync_role_groups")
def sync_roles_after_migrate(**kwargs) -> None:
    """Keep default Groups synchronized after permissions are created."""

    sync_role_groups()
