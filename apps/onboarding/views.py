from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.core.models import AppSetting

from .models import UserTourState


TOUR_KEY = "mvp_first_run"


def get_tour_state(user):
    state, _ = UserTourState.objects.get_or_create(user=user, tour_key=TOUR_KEY)
    return state


@login_required
def tour_status(request):
    enabled = AppSetting.get_bool("tour_enabled", True)
    state = get_tour_state(request.user)
    return JsonResponse(
        {
            "enabled": enabled,
            "tour_key": TOUR_KEY,
            "should_start": enabled and not state.completed and not state.dismissed,
            "completed": state.completed,
            "dismissed": state.dismissed,
            "last_step": state.last_step,
        }
    )


@login_required
@require_POST
def tour_complete(request):
    state = get_tour_state(request.user)
    state.completed = True
    state.dismissed = False
    state.save(update_fields=["completed", "dismissed", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def tour_dismiss(request):
    state = get_tour_state(request.user)
    state.dismissed = True
    state.save(update_fields=["dismissed", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def tour_step(request):
    state = get_tour_state(request.user)
    try:
        state.last_step = int(request.POST.get("step", 0))
    except ValueError:
        state.last_step = 0
    state.save(update_fields=["last_step", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
def restart_tour(request):
    state = get_tour_state(request.user)
    state.completed = False
    state.dismissed = False
    state.last_step = 0
    state.save(update_fields=["completed", "dismissed", "last_step", "updated_at"])
    return redirect(request.GET.get("next") or "core:dashboard")
