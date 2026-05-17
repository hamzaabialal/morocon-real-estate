"""Serializers for analytics tracking events."""
from rest_framework import serializers

from apps.analytics.models import (
    AgencyAnalyticsSummary,
    LeadEvent,
    PropertyClick,
    PropertyView,
)


class PropertyViewSerializer(serializers.ModelSerializer):
    """Serializer for property view events."""

    class Meta:
        model = PropertyView
        fields = [
            "id",
            "property",
            "ip_address",
            "user_agent",
            "referrer",
            "session_key",
            "created_at",
        ]
        read_only_fields = fields


class PropertyClickSerializer(serializers.ModelSerializer):
    """Serializer used to validate public click tracking payloads."""

    class Meta:
        model = PropertyClick
        fields = ["id", "property", "click_type", "created_at", "ip_address"]
        read_only_fields = ["id", "property", "created_at", "ip_address"]


class AgencyAnalyticsSummarySerializer(serializers.ModelSerializer):
    """Serializer for daily agency analytics summaries."""

    class Meta:
        model = AgencyAnalyticsSummary
        fields = ["id", "agency", "date", "views", "clicks", "leads", "top_property"]
        read_only_fields = fields


class LeadEventSerializer(serializers.ModelSerializer):
    """Serializer for lead events."""

    class Meta:
        model = LeadEvent
        fields = ["id", "property", "agency", "phone", "source", "created_at"]
        read_only_fields = fields
