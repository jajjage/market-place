from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class LogoutSerializer(TokenObtainPairSerializer):
    """
    Serializer for logging out users by clearing authentication cookies.
    """

    def validate(self, attrs):
        # This method can be extended to perform additional validation if needed
        return super().validate(attrs)

    def save(self, **kwargs):
        # This method can be extended to perform actions on logout if needed
        pass


class CustomTokenObtainSerializer(TokenObtainPairSerializer):
    """
    Custom serializer for JWT token generation.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims to token
        token["email"] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add extra response data
        user = self.user
        data["user_id"] = str(user.id)
        data["email"] = user.email
        data["first_name"] = user.first_name
        data["last_name"] = user.last_name

        return data
