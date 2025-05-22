from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainSerializer(TokenObtainPairSerializer):
    """
    Custom serializer for JWT token generation.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims to token
        token["user_type"] = user.user_type
        token["verification_status"] = user.verification_status
        token["email"] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add extra response data
        user = self.user
        data["user_id"] = str(user.id)
        data["email"] = user.email
        data["user_type"] = user.user_type
        data["verification_status"] = user.verification_status
        data["first_name"] = user.first_name
        data["last_name"] = user.last_name

        return data
