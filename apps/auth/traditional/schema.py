# apps/auth/traditional/schema.py
from drf_spectacular.utils import extend_schema, OpenApiExample
from .serializers import CustomTokenObtainSerializer

login_schema = extend_schema(
    summary="User Login",
    description="""
    Authenticates a user and returns an access and refresh token pair.
    The tokens are also set as cookies (`access_token` and `refresh_token`).
    """,
    request=CustomTokenObtainSerializer,
    responses={
        200: CustomTokenObtainSerializer,
        401: {"description": "Authentication failed"},
        429: {"description": "Too many login attempts"},
    },
    examples=[
        OpenApiExample(
            "Successful Login",
            value={
                "status": "success",
                "message": "Login successful",
                "data": {
                    "access": "your_access_token",
                    "refresh": "your_refresh_token",
                    "user_id": "user_id",
                    "email": "user@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                },
            },
            response_only=True,
        ),
    ],
)

refresh_schema = extend_schema(
    summary="Refresh Access Token",
    description="""
    Refreshes an expired access token using a valid refresh token.
    The refresh token is expected to be in an HTTP-only cookie (`refresh_token`).
    A new access token is returned and also set as a cookie.
    """,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "No refresh token found or token is blacklisted"},
        429: {"description": "Too many refresh attempts"},
        500: {"description": "Token refresh failed"},
    },
)

verify_schema = extend_schema(
    summary="Verify Access Token",
    description="""
    Verifies the validity of an access token.
    The access token is expected to be in an HTTP-only cookie (`access_token`).
    """,
    responses={
        200: {"description": "Token is valid"},
        401: {"description": "Invalid or no token found"},
    },
)

logout_schema = extend_schema(
    summary="User Logout",
    description="""
    Logs out the user by clearing the access and refresh token cookies.
    """,
    responses={
        200: {"description": "Successfully logged out"},
        400: {"description": "Logout failed"},
    },
)

test_auth_schema = extend_schema(
    summary="Test Authentication",
    description="""
    An endpoint to test if the user is authenticated.
    Requires a valid access token in the `access_token` cookie.
    """,
    responses={
        200: {"description": "You are authenticated"},
        401: {"description": "Authentication credentials were not provided"},
    },
)
