"""Serializers for agency profiles and authentication."""
from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.agencies.models import Agency, User


class AgencyPublicSerializer(serializers.ModelSerializer):
    """Public agency profile without billing or enrichment internals."""

    class Meta:
        model = Agency
        fields = [
            "id",
            "name",
            "slug",
            "phone",
            "whatsapp",
            "website",
            "logo_url",
            "city",
            "is_verified",
            "source",
            "created_at",
        ]
        read_only_fields = fields


class AgencySerializer(serializers.ModelSerializer):
    """Private agency profile serializer for owners and admins."""

    class Meta:
        model = Agency
        fields = [
            "id",
            "name",
            "slug",
            "phone",
            "whatsapp",
            "email",
            "website",
            "logo_url",
            "city",
            "is_verified",
            "subscription_plan",
            "subscription_expires_at",
            "source",
            "propertyfinder_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "is_verified",
            "subscription_plan",
            "subscription_expires_at",
            "source",
            "propertyfinder_id",
            "created_at",
            "updated_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for authenticated user profile data."""

    agency = AgencyPublicSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "agency",
            "is_active",
            "is_staff",
            "last_login",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "role",
            "agency",
            "is_active",
            "is_staff",
            "last_login",
            "created_at",
        ]


class RegisterSerializer(serializers.Serializer):
    """Registration payload for agency owner sign-up."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    agency_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=30)

    def validate_email(self, value):
        """Ensure email addresses remain unique."""
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email


class LoginSerializer(serializers.Serializer):
    """Login payload using email and password."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Authenticate credentials and attach the user."""
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        attrs["user"] = user
        return attrs
