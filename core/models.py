from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base: every RestoCore model records when it was created and last changed."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ThrottleEvent(models.Model):
    """One counted event (a failed sign-in, a public booking, ...) for rate limiting.

    Stored in Postgres rather than a per-process cache, so every web worker and every restart
    sees the same counts (the web container stays stateless). See core.throttle.
    """

    scope = models.CharField(max_length=40)
    key = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=("scope", "key", "created_at"))]

    def __str__(self) -> str:
        return f"{self.scope}: {self.key} at {self.created_at:%Y-%m-%d %H:%M}"
