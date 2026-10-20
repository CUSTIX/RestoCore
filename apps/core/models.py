from django.db import models


class TimeStampedModel(models.Model):
    """Shared timestamps for persisted domain models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ModuleAccess(models.Model):
    """Permission anchor for the internal RestoCore workspace."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_internal", "Can access the internal workspace"),
        ]

    def __str__(self) -> str:
        return "Internal workspace access"
