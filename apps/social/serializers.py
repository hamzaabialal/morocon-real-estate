"""Serializers for social publishing endpoints."""
from rest_framework import serializers

from apps.social.models import SocialPost


class SocialPostSerializer(serializers.ModelSerializer):
    """Read-only representation of social post state and performance."""

    property_id = serializers.UUIDField(source="property.id", read_only=True)
    property_title = serializers.SerializerMethodField()

    class Meta:
        model = SocialPost
        fields = [
            "id",
            "property_id",
            "property_title",
            "platform",
            "status",
            "scheduled_at",
            "posted_at",
            "post_url",
            "platform_post_id",
            "likes",
            "views",
            "shares",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields

    def get_property_title(self, social_post):
        property_obj = social_post.property
        if property_obj.formatted_address:
            return property_obj.formatted_address
        return f"{property_obj.get_property_category_display()} {property_obj.yakeey_ref}".strip()
