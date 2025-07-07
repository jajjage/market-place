from drf_spectacular.utils import extend_schema, OpenApiExample
from djoser.social.serializers import ProviderAuthSerializer

google_auth_schema = extend_schema(
    summary="Google Authentication",
    description="""
    Authenticates a user using a Google OAuth2 access token.
    If the user does not exist, a new user account is created.
    On successful authentication, it returns access and refresh tokens,
    which are also set as cookies (`access_token` and `refresh_token`).
    """,
    request=ProviderAuthSerializer,
    responses={
        201: {
            "description": "Social authentication successful",
            "examples": [
                OpenApiExample(
                    "Successful Google Auth",
                    value={
                        "status": "success",
                        "message": "Social authentication successful",
                        "data": {
                            "id": "user_id",
                            "email": "user@example.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "verification_status": "Email Verified",
                            "profile": {
                                "id": "profile_id",
                                "display_name": "JohnD",
                                "bio": "A short bio.",
                                "phone_number": "+1234567890",
                                "country": "USA",
                                "city": "New York",
                                "email_verified": True,
                                "phone_verified": False,
                                "avatar_url": "http://example.com/avatar.jpg",
                            },
                        },
                    },
                )
            ],
        },
        400: {"description": "Invalid token or provider"},
        401: {"description": "Authentication failed"},
        404: {"description": "User not found"},
    },
)
