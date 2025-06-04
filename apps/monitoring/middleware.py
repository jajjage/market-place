import time
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    For any incoming request whose path matches one of the configured API prefixes,
    record start time, then on response compute duration and log under "{short_name}_performance".
    """

    def process_request(self, request):
        # Attempt to find a matching prefix
        path = request.path
        for prefix, short_name in settings.PERFORMANCE_API_PREFIXES.items():
            if path.startswith(prefix):
                request._perf_start = time.time()
                request._perf_short_name = short_name
                break

    def process_response(self, request, response):
        if hasattr(request, "_perf_start"):
            duration = time.time() - request._perf_start
            short_name = request._perf_short_name
            logger = logging.getLogger(f"{short_name}_performance")

            # If it was slow, log a warning; otherwise, you could log at INFO level if desired
            if duration > settings.SLOW_REQUEST_THRESHOLD_SEC:
                logger.warning(
                    f"Slow {short_name} API request: "
                    f"{request.method} {request.path} took {duration:.3f}s "
                    f"- Status {response.status_code}"
                )
            else:
                logger.info(
                    f"{short_name} API request: {request.method} {request.path} "
                    f"took {duration:.3f}s - Status {response.status_code}"
                )

            # Always set header so clients can see timing
            response["X-Response-Time"] = f"{duration:.3f}s"

        return response
