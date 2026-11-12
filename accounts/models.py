from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """RestoCore user. Defined before the first migration so it can grow without a painful swap.

    Roles are Django Groups (see core.roles); a user may hold more than one.
    """

    class Meta:
        ordering = ("username",)

    def __str__(self) -> str:
        return self.get_full_name() or self.username
