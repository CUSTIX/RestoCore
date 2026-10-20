"""Shared abstract models. Business entities belong in their owning application."""

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base for records that need creation and modification timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
