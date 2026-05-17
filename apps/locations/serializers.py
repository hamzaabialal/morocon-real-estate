"""Read-only serializers for location resources."""
from rest_framework import serializers

from apps.locations.models import City, Country, District, Neighborhood


class CountrySerializer(serializers.ModelSerializer):
    """Serializer for country records."""

    class Meta:
        model = Country
        fields = ["id", "name", "code", "created_at"]
        read_only_fields = fields


class CitySerializer(serializers.ModelSerializer):
    """Serializer for city records."""

    property_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = City
        fields = [
            "id",
            "name",
            "slug",
            "country",
            "latitude",
            "longitude",
            "property_count",
            "created_at",
        ]
        read_only_fields = fields


class DistrictSerializer(serializers.ModelSerializer):
    """Serializer for district records."""

    class Meta:
        model = District
        fields = ["id", "name", "slug", "city", "created_at"]
        read_only_fields = fields


class NeighborhoodSerializer(serializers.ModelSerializer):
    """Serializer for neighborhood records."""

    class Meta:
        model = Neighborhood
        fields = [
            "id",
            "name",
            "slug",
            "district",
            "latitude",
            "longitude",
            "created_at",
        ]
        read_only_fields = fields
