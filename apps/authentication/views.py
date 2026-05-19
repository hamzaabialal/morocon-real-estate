"""JWT authentication views."""
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.authentication.serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Return access/refresh tokens with custom identity claims."""

    serializer_class = CustomTokenObtainPairSerializer
