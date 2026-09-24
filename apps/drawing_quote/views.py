from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def placeholder(request):
    """Smoke-test page when DRAWING_QUOTE_ENABLED is on (Phase P0)."""
    return render(
        request,
        "drawing_quote/placeholder.html",
        {
            "page_title": "Quote from drawing",
        },
    )
