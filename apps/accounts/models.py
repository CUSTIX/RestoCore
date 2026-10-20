from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """RestoCore user model; extend this instead of replacing it later."""

    email = models.EmailField("email address", unique=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "accounts_user"
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.get_full_name() or self.username
