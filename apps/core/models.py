from django.db import models


class Plant(models.Model):
    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=50, unique=True)
    currency = models.CharField(max_length=10, default="INR")
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AppSetting(models.Model):
    key = models.SlugField(max_length=100, unique=True)
    value = models.TextField(blank=True, default="")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key

    @classmethod
    def get_bool(cls, key, default=False):
        try:
            row = cls.objects.get(key=key)
            return row.value.strip().lower() in ("1", "true", "yes", "on")
        except cls.DoesNotExist:
            return default
