from django.http import Http404, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class BaseResponseMixin:
    """Mixin to standardize API responses."""

    """
    Base API View that standardizes response format across the application.
    All responses will have the format:
    {
        "status": "success" | "error",
        "message": str,
        "data": Any | None
    }
    """

    def success_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        """Send a success response"""
        response_data = {
            "status": "success",
            "status_code": status_code,
            "message": message,
            "data": data,
        }
        return Response(response_data, status=status_code)

    def error_response(
        self,
        message="An error occurred",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        """Send an error response"""
        response_data = {
            "status": "error",
            "message": message,
            "data": data,
            "status_code": status_code,
        }
        return Response(response_data, status=status_code)


class BaseViewSet(ModelViewSet, BaseResponseMixin):
    """Base ViewSet for patient-related models with standardized CRUD operations."""

    def create(self, request, *args, **kwargs):
        """
        Standardized create method with proper error handling and response format.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} created successfully",
                status_code=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return self.error_response(
                message=str(e),  # detail.get("non_field_errors")
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, AttributeError, PermissionError) as e:
            return self.error_response(
                message=f"Failed to create {self.get_model_name().lower()}: {str(e)!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        """
        Standardized update method with proper error handling and response format.
        """
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} updated successfully",
            )
        except ValidationError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (PermissionError, AttributeError, TypeError) as e:
            return self.error_response(
                message=f"Failed to update {self.get_model_name().lower()}: {str(e)!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        """
        Standardized delete method with proper error handling and response format.
        """
        try:
            instance = self.get_object()
            self.perform_destroy(instance)

            return self.success_response(
                message=f"{self.get_model_name()} deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
            )
        except (Http404, PermissionError, ValidationError) as e:
            return self.error_response(
                message=f"Failed to delete {self.get_model_name().lower()}: {str(e)!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def list(self, request, *args, **kwargs):
        """
        Standardized list method with proper error handling and response format.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} list retrieved successfully",
            )
        except (ValidationError, PermissionError):
            return self.error_response(
                message=f"Failed to retrieve {self.get_model_name().lower()} list",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, AttributeError) as e:
            return self.error_response(
                message=f"Error processing {self.get_model_name().lower()} list: {str(e)!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        """
        Standardized retrieve method with proper error handling and response format.
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)

            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} retrieved successfully",
            )
        except Http404:
            return self.error_response(
                message=f"{self.get_model_name()} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except (ValidationError, PermissionError) as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def get_model_name(self) -> str:
        """AHelper method to get the model name for messages."""
        return self.__class__.__name__.replace("ViewSet", "")


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

    def success_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        """Send a success response"""
        response_data = {
            "status": "success",
            "status_code": status_code,
            "message": message,
            "data": data,
        }
        return Response(response_data, status=status_code)

    def error_response(
        self,
        message="An error occurred",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        """Send an error response"""
        response_data = {
            "status": "error",
            "message": message,
            "data": data,
            "status_code": status_code,
        }
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
