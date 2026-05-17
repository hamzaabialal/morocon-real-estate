"""Serializers for property listing APIs."""
from rest_framework import serializers

from apps.properties.models import Property, PropertyFeatures, PropertyImage


class PropertyImageSerializer(serializers.ModelSerializer):
    """Serializer for property image records."""

    class Meta:
        model = PropertyImage
        fields = ["id", "url", "order", "is_main", "created_at"]
        read_only_fields = ["id", "created_at"]


class PropertyFeaturesSerializer(serializers.ModelSerializer):
    """Serializer for all property features and measured feature areas."""

    class Meta:
        model = PropertyFeatures
        exclude = ["property"]
        read_only_fields = ["id", "created_at"]


class PropertyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for search results and listing pages."""

    city = serializers.StringRelatedField()
    district = serializers.StringRelatedField()
    neighborhood = serializers.StringRelatedField()

    class Meta:
        model = Property
        fields = [
            "id",
            "yakeey_ref",
            "transaction_type",
            "property_category",
            "property_type",
            "status",
            "price",
            "currency",
            "area",
            "bedrooms",
            "bathrooms",
            "city",
            "district",
            "neighborhood",
            "cover_image_url",
            "is_featured",
            "is_verified",
            "listed_at",
        ]
        read_only_fields = fields


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Full property serializer with nested images and feature data."""

    images = PropertyImageSerializer(many=True, read_only=True)
    features = PropertyFeaturesSerializer(read_only=True)

    class Meta:
        model = Property
        fields = [
            "id",
            "yakeey_ref",
            "transaction_type",
            "property_category",
            "property_type",
            "status",
            "price",
            "currency",
            "area",
            "built_area",
            "bedrooms",
            "bathrooms",
            "toilets",
            "floor",
            "total_floors",
            "construction_year",
            "condominium_fees",
            "furnished",
            "is_new",
            "closed_residence",
            "is_featured",
            "is_verified",
            "general_state",
            "view",
            "occupation_state",
            "description",
            "cover_image_url",
            "latitude",
            "longitude",
            "formatted_address",
            "main_address",
            "source_url",
            "marketplace_url",
            "agent_name",
            "agent_phone",
            "registration_fees",
            "total_acquisition_cost",
            "views_count",
            "city",
            "district",
            "neighborhood",
            "agency",
            "agency_match_confidence",
            "source",
            "property_tag",
            "reel_url",
            "square_video_url",
            "caption_fr",
            "caption_ar",
            "caption_hashtags",
            "media_generated_at",
            "media_status",
            "listed_at",
            "created_at",
            "updated_at",
            "images",
            "features",
        ]
        read_only_fields = ["id", "views_count", "created_at", "updated_at"]
