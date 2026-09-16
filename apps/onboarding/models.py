from django.conf import settings
from django.db import models


class UserTourState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tours")
    tour_key = models.SlugField(max_length=80, default="mvp_first_run")
    completed = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)
    last_step = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "tour_key")]

    def __str__(self):
        return f"{self.user} / {self.tour_key}"
