"""Serializers for the public property marketplace API."""
from rest_framework import serializers

from apps.properties.models import Property, PropertyFeatures, PropertyImage


class LocationLookupSerializer(serializers.Serializer):
    """Small read-only lookup shape for nested location values."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True, required=False)


class AgencyLookupSerializer(serializers.Serializer):
    """Small read-only agency shape exposed on public listings."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    whatsapp = serializers.CharField(read_only=True)
    logo_url = serializers.URLField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_claimed = serializers.BooleanField(read_only=True)


class PropertyImageSerializer(serializers.ModelSerializer):
    """Image asset paths attached to a property listing."""

    asset_url = serializers.URLField(source="url", read_only=True)

    class Meta:
        model = PropertyImage
        fields = ["id", "url", "asset_url", "order", "is_main", "created_at"]
        read_only_fields = fields


class PropertyFeaturesSerializer(serializers.ModelSerializer):
    """Boolean amenities and measured feature areas."""

    class Meta:
        model = PropertyFeatures
        exclude = ["property"]

    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields


class PropertySerializer(serializers.ModelSerializer):
    """Comprehensive read-only serializer for public marketplace listings."""

    city = LocationLookupSerializer(read_only=True)
    district = LocationLookupSerializer(read_only=True)
    neighborhood = LocationLookupSerializer(read_only=True)
    agency = AgencyLookupSerializer(read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    features = PropertyFeaturesSerializer(read_only=True)

    class Meta:
        model = Property
        fields = [
            "id",
            "sarouty_id",
            "yakeey_id",
            "yakeey_ref",
            "listing_type",
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
            "land_registration_fees",
            "notary_fees",
            "total_acquisition_cost",
            "enrichment_confidence",
            "views_count",
            "city",
            "district",
            "neighborhood",
            "agency",
            "source",
            "property_tag",
            "reel_url",
            "square_video_url",
            "caption_fr",
            "caption_ar",
            "caption_hashtags",
            "media_generated_at",
            "media_status",
            "scrape_status",
            "last_scraped_at",
            "listed_at",
            "created_at",
            "updated_at",
            "images",
            "features",
        ]
        read_only_fields = fields


class PropertyListSerializer(PropertySerializer):
    """List serializer kept as an alias for backwards-compatible imports."""


class PropertyDetailSerializer(PropertySerializer):
    """Detail serializer kept as an alias for backwards-compatible imports."""
