"""Custom JWT serializers wired via SIMPLE_JWT['TOKEN_OBTAIN_SERIALIZER']."""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the user's role + agency id to the access token payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = getattr(user, "role", "")
        token["agency_id"] = str(getattr(user, "agency_id", "") or "")
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = {
            "id": str(user.id),
            "email": user.email,
            "role": getattr(user, "role", ""),
            "agency_id": str(getattr(user, "agency_id", "") or ""),
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        return data
