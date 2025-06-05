from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled


def custom_exception_handler(exc, context):
    """
    Intercept any DRF exception. If it’s a Throttled error, convert it to
    a JSON response with a dynamic message based on `scope`. Otherwise,
    fall back to DRF’s default behavior.
    """
    # Let DRF build the default error response first (it will include a 429
    # status code and a Retry-After header for Throttled exceptions).
    response = exception_handler(exc, context)

    if isinstance(exc, Throttled) and response is not None:
        # 1) Extract the view, then get the first throttle’s scope
        view = context.get("view", None)
        throttles = [] if view is None else getattr(view, "get_throttles", lambda: [])()
        scope = None
        if throttles:
            scope = getattr(throttles[0], "scope", None)

        # 2) Determine how many seconds the client should wait
        wait_seconds = int(exc.wait) if exc.wait is not None else None

        # 3) Build a dynamic message
        if scope == "watchlist_toggle":
            detail = "Too many toggle requests. Please wait before adding/removing more products."
        elif scope == "watchlist_bulk":
            detail = "Too many bulk operations. Please wait before performing more bulk actions."
        elif scope == "watchlist":
            detail = (
                "Too many watchlist requests. Please wait before making more requests."
            )
        elif scope == "brand_search":
            detail = "Too many brand‐search requests. Please wait a minute before searching again."
        elif scope == "brand_create":
            detail = "Too many brand‐creation attempts. Please wait a bit before trying again."
        else:
            if wait_seconds is not None:
                detail = f"Request rate limit exceeded. Please wait {wait_seconds} seconds and try again."
            else:
                detail = "Request rate limit exceeded. Please try again later."

        # 4) Replace DRF’s default response body with our own structure
        response.data = {
            "status": "error",
            "message": detail,
            "retry_after": wait_seconds,
        }
        response.status_code = 429  # ensure HTTP 429

    return response
