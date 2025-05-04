from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class BaseAPIView(APIView):
    """
    Base API View that standardizes response format across the application.
    All responses will have the format:
    {
        "status": "success" | "error",
        "message": str,
        "data": Any | None
    }
    """

    def send_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        """Send a success response"""
        response_data = {"status": "success", "message": message, "data": data}
        return Response(response_data, status=status_code)

    def send_error(
        self,
        message="An error occurred",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        """Send an error response"""
        response_data = {"status": "error", "message": message, "data": data}
        return Response(response_data, status=status_code)


class PingRateThrottle(AnonRateThrottle):
    rate = "10/minute"


from .tasks import test_task


@extend_schema(
    description="Handles a ping request to check if the server is responsive.",
    responses={
        200: {
            "type": "object",
            "properties": {"ping": {"type": "string"}},
            "example": {"ping": "pong"},
        },
        405: {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "example": {"detail": 'Method "POST" not allowed.'},
        },
    },
)
@api_view(["GET"])
@throttle_classes([PingRateThrottle])
def ping(request):
    logger.info("Ping request received from %s", request.META.get("REMOTE_ADDR"))
    return JsonResponse({"ping": "pong"})


def fire_task(request):
    """
    TODO 🚫 After testing the view, remove it with the task and the route.

    Handles a request to fire a test Celery task. The task will be retried
    up to 3 times and after 5 seconds if it fails (by default). The retry
    time will be increased exponentially.
    """
    if request.method == "GET":
        test_task.delay()
        return JsonResponse({"task": "Task fired"})

    return JsonResponse({"error": "Method Not Allowed"}, status=405)
