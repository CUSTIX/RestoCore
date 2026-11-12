from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """RestoCore user. Defined before the first migration so it can grow without a painful swap.

    Roles are Django Groups (see core.roles); a user may hold more than one.
    """

    class Meta:
        ordering = ("username",)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class LoginFailure(models.Model):
    """One failed sign-in. Used to slow down password guessing (see accounts.services).

    Kept in Postgres, not a per-process cache, so every web worker and restart sees the same count.
    """

    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=("username", "ip_address", "created_at"))]

    def __str__(self) -> str:
        return f"{self.username} from {self.ip_address or '?'} at {self.created_at:%Y-%m-%d %H:%M}"
