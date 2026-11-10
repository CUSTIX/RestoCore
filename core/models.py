from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base: every RestoCore model records when it was created and last changed."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
