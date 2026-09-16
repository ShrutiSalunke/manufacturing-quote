import logging
import uuid

from django.http import HttpResponseServerError
from django.template.loader import render_to_string

from apps.core.logging_utils import log_event


class ExceptionLoggingMiddleware:
    """
    Assign correlation_id per request and persist unhandled exceptions to SystemLog.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.correlation_id = uuid.uuid4()
        response = self.get_response(request)
        response["X-Correlation-Id"] = str(request.correlation_id)
        return response

    def process_exception(self, request, exception):
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        # Let Django handle expected HTTP errors normally (403/404).
        if isinstance(exception, (PermissionDenied, Http404)):
            return None

        entry = log_event(
            "ERROR",
            "middleware",
            "EXCEPTION",
            f"Unhandled exception: {exception}",
            request=request,
            exc=exception,
            context={"exception_type": type(exception).__name__},
            correlation_id=getattr(request, "correlation_id", None),
        )
        cid = entry.correlation_id if entry else getattr(request, "correlation_id", "")
        logging.getLogger("manufacturing_quote").error(
            "Unhandled exception correlation_id=%s", cid, exc_info=exception
        )
        # Let Django's default 500 handling run in DEBUG; in production show friendly page
        from django.conf import settings

        # Also return None during tests so Django test client template instrumentation
        # is not re-entered when rendering a custom 500 page.
        if settings.DEBUG or getattr(settings, "TESTING", False):
            return None

        html = render_to_string(
            "errors/500.html",
            {"correlation_id": str(cid), "request": request},
            request=request,
        )
        response = HttpResponseServerError(html)
        response["X-Correlation-Id"] = str(cid)
        return response
