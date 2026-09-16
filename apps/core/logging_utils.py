import logging
import traceback
import uuid

from django.contrib.auth import get_user_model


def log_event(
    level,
    source,
    event_type,
    message,
    *,
    user=None,
    request=None,
    exc=None,
    context=None,
    correlation_id=None,
):
    """
    Persist an event to SystemLog (database only). Returns the SystemLog instance.
    """
    from apps.auditlog.models import SystemLog

    ctx = dict(context or {})
    tb = ""
    if exc is not None:
        tb = traceback.format_exc()
        if not tb or tb.strip() == "NoneType: None":
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    request_path = ""
    http_method = ""
    cid = correlation_id
    resolved_user = user

    if request is not None:
        request_path = getattr(request, "path", "") or ""
        http_method = getattr(request, "method", "") or ""
        if cid is None:
            cid = getattr(request, "correlation_id", None)
        if resolved_user is None and getattr(request, "user", None) is not None:
            if getattr(request.user, "is_authenticated", False):
                resolved_user = request.user

    if cid is None:
        cid = uuid.uuid4()

    level_value = level if isinstance(level, str) else str(level)
    event_value = event_type if isinstance(event_type, str) else str(event_type)

    # Avoid FK issues if user is anonymous / unsaved
    user_fk = None
    if resolved_user is not None and getattr(resolved_user, "pk", None):
        User = get_user_model()
        if isinstance(resolved_user, User):
            user_fk = resolved_user

    try:
        entry = SystemLog.objects.create(
            level=level_value.upper(),
            source=source[:100],
            event_type=event_value.upper(),
            message=str(message),
            traceback=tb,
            request_path=request_path[:500],
            http_method=http_method[:10],
            user=user_fk,
            correlation_id=cid,
            context=ctx,
        )
    except Exception:
        # Last-resort: never break the request path due to logging failure
        logging.getLogger("manufacturing_quote").exception("Failed to write SystemLog")
        return None

    return entry
