from django.contrib import admin

from .models import UserTourState


@admin.register(UserTourState)
class UserTourStateAdmin(admin.ModelAdmin):
    list_display = ("user", "tour_key", "completed", "dismissed", "last_step", "updated_at")
