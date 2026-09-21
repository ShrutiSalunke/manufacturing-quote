from django import template

from apps.core.permissions import feature_rbac_enabled, user_can

register = template.Library()


@register.simple_tag(takes_context=True)
def can(context, module, action="view"):
    """Merge-safe permission check for templates."""
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user_can(user, module, action)


@register.simple_tag
def rbac_enabled():
    return feature_rbac_enabled()
