from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse

from apps.core.decorators import admin_required

from .forms import UserCreateForm, UserEditForm
from .models import feature_rbac_enabled

User = get_user_model()

PER_PAGE_CHOICES = (10, 15, 25, 50)
DEFAULT_PER_PAGE = 15


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def _page_number_window(page_obj, adjacent=1):
    current = page_obj.number
    total = page_obj.paginator.num_pages
    if total <= 7:
        return list(range(1, total + 1))
    pages = {1, total, current}
    for i in range(current - adjacent, current + adjacent + 1):
        if 1 <= i <= total:
            pages.add(i)
    ordered = sorted(pages)
    result = []
    prev = None
    for num in ordered:
        if prev is not None and num - prev > 1:
            result.append(None)
        result.append(num)
        prev = num
    return result


def _redirect_after_user_create(user):
    """
    Merge-safe handoff: when Access Control is enabled, open it to assign roles.
    On Main (FEATURE_RBAC off) stay on the Users list.
    """
    if feature_rbac_enabled():
        try:
            hub = reverse("access:hub")
            return redirect(f"{hub}?assign_user={user.pk}")
        except NoReverseMatch:
            pass
    return redirect("accounts:user_list")


@admin_required
def user_list(request):
    q = (request.GET.get("q") or "").strip()
    active = request.GET.get("active") or ""
    try:
        per_page = int(request.GET.get("per_page") or DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    if per_page not in PER_PAGE_CHOICES:
        per_page = DEFAULT_PER_PAGE

    qs = User.objects.all().order_by("email", "username")
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    if active == "1":
        qs = qs.filter(is_active=True)
    elif active == "0":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    ctx = {
        "page_title": "Users",
        "page_obj": page_obj,
        "users": page_obj.object_list,
        "q": q,
        "active": active,
        "per_page": per_page,
        "per_page_choices": PER_PAGE_CHOICES,
        "page_numbers": _page_number_window(page_obj),
        "feature_rbac": feature_rbac_enabled(),
    }
    return render(request, "accounts/user_list.html", ctx)


@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"User {user.email or user.username} created with full access.",
            )
            return _redirect_after_user_create(user)
    else:
        form = UserCreateForm()
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "page_title": "Add User",
            "is_create": True,
            "feature_rbac": feature_rbac_enabled(),
        },
    )


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            if user.pk == request.user.pk and not form.cleaned_data.get("is_active", True):
                messages.error(request, "You cannot deactivate your own account.")
            else:
                saved = form.save()
                messages.success(
                    request,
                    f"User {saved.email or saved.username} updated.",
                )
                return redirect("accounts:user_list")
    else:
        form = UserEditForm(instance=user)
    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "page_title": f"Edit {user.email or user.username}",
            "is_create": False,
            "edit_user": user,
            "feature_rbac": feature_rbac_enabled(),
        },
    )


@admin_required
def user_deactivate(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method != "POST":
        return redirect("accounts:user_list")
    if user.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_list")
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a superuser can deactivate another superuser.")
        return redirect("accounts:user_list")
    user.is_active = False
    user.save(update_fields=["is_active"])
    messages.success(request, f"{user.email or user.username} deactivated.")
    return redirect("accounts:user_list")


@admin_required
def user_activate(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method != "POST":
        return redirect("accounts:user_list")
    user.is_active = True
    if user.role != User.Role.ADMIN and not user.is_superuser:
        user.role = User.Role.ADMIN
        user.save(update_fields=["is_active", "role"])
    else:
        user.save(update_fields=["is_active"])
    messages.success(request, f"{user.email or user.username} activated.")
    return redirect("accounts:user_list")
