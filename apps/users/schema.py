from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from apps.core.schema import UNAUTHORIZED_EXAMPLES, ErrorResponseSerializer
from .serializers import (
    UserSerializer,
    CustomTokenObtainSerializer,
    UserProfileSerializer,
)

# Define schemas for authentication endpoints

LOGIN_RESPONSE_SCHEMA = {
    200: OpenApiResponse(
        response=CustomTokenObtainSerializer,
        description="Successfully authenticated",
    ),
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Invalid credentials",
        examples=[
            OpenApiExample(
                "Invalid Credentials",
                value={"detail": "Unable to log in with provided credentials."},
                status_codes=["400"],
            ),
            OpenApiExample(
                "Missing Fields",
                value={
                    "email": ["This field is required."],
                    "password": ["This field is required."],
                },
                status_codes=["400"],
            ),
        ],
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication failed",
        examples=[
            OpenApiExample(
                "Authentication Failed",
                value={"error": "Authentication failed"},
                status_codes=["401"],
            ),
        ],
    ),
    500: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Server error",
        examples=[
            OpenApiExample(
                "Cookie Error",
                value={"error": "Failed to set authentication cookies"},
                status_codes=["500"],
            ),
        ],
    ),
}

TOKEN_REFRESH_SCHEMA = {
    200: OpenApiResponse(
        response=CustomTokenObtainSerializer,
        description="Successfully refreshed token",
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Invalid refresh token",
        examples=[
            OpenApiExample(
                "No Token",
                value={"detail": "No refresh token found"},
                status_codes=["401"],
            ),
            OpenApiExample(
                "Blacklisted Token",
                value={"detail": "Token is blacklisted"},
                status_codes=["401"],
            ),
            OpenApiExample(
                "Token Error",
                value={"detail": "Token is invalid or expired"},
                status_codes=["401"],
            ),
        ],
    ),
    429: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Rate limited",
        examples=[
            OpenApiExample(
                "Rate Limited",
                value={"detail": "Too many refresh attempts"},
                status_codes=["429"],
            ),
        ],
    ),
    500: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Server error",
        examples=[
            OpenApiExample(
                "Server Error",
                value={"detail": "Token refresh failed"},
                status_codes=["500"],
            ),
        ],
    ),
}

TOKEN_VERIFY_SCHEMA = {
    200: OpenApiResponse(
        description="Token is valid",
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Invalid token",
        examples=[
            OpenApiExample(
                "No Token",
                value={"error": "No token found"},
                status_codes=["401"],
            ),
            OpenApiExample(
                "Invalid Token",
                value={"error": "Invalid token"},
                status_codes=["401"],
            ),
        ],
    ),
}

LOGOUT_SCHEMA = {
    200: OpenApiResponse(
        description="Successfully logged out",
        examples=[
            OpenApiExample(
                "Success",
                value={"detail": "Successfully logged out."},
                status_codes=["200"],
            ),
        ],
    ),
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Logout failed",
        examples=[
            OpenApiExample(
                "Failed",
                value={"error": "Logout failed"},
                status_codes=["400"],
            ),
        ],
    ),
}

USER_CREATE_RESPONSE_SCHEMA = {
    201: OpenApiResponse(
        response=UserSerializer,
        description="User successfully created",
    ),
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Validation error",
        examples=[
            OpenApiExample(
                "Invalid Data",
                value={
                    "email": ["This email is already registered."],
                    "password": ["Passwords do not match."],
                },
                status_codes=["400"],
            ),
            OpenApiExample(
                "Bad Request",
                value={
                    "email": ["This field may not be blank."],
                    "password": ["This field may not be blank."],
                    "password2": ["This field may not be blank."],
                },
                status_codes=["400"],
            ),
        ],
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication required",
        examples=UNAUTHORIZED_EXAMPLES,
    ),
}

PROFILE_DETAIL_SCHEMA = {
    200: OpenApiResponse(
        response=UserProfileSerializer,
        description="User profile data",
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication required",
        examples=UNAUTHORIZED_EXAMPLES,
    ),
}

PROFILE_PUT_SCHEMA = {
    200: OpenApiResponse(
        response=UserProfileSerializer,
        description="User profile updated",
    ),
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Validation error",
        examples=[
            OpenApiExample(
                "Invalid Data",
                value={"password": ["Password must be at least 5 characters long."]},
                status_codes=["400"],
            ),
            OpenApiExample(
                "Missing Fields",
                value={"password": ["This field is required."]},
                status_codes=["400"],
            ),
        ],
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication required",
        examples=UNAUTHORIZED_EXAMPLES,
    ),
}

PROFILE_PATCH_SCHEMA = {
    200: OpenApiResponse(
        response=UserProfileSerializer,
        description="User profile updated",
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication required",
        examples=UNAUTHORIZED_EXAMPLES,
    ),
}

USER_ACTIVATION_SCHEMA = {
    200: OpenApiResponse(
        response=UserProfileSerializer,
        description="User profile updated",
    ),
    401: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Authentication required",
        examples=UNAUTHORIZED_EXAMPLES,
    ),
}
