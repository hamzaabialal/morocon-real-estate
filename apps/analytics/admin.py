"""Admin configuration for analytics and lead models."""
from django.contrib import admin

from apps.analytics.models import (
    AgencyAnalyticsSummary,
    LeadEvent,
    PropertyClick,
    PropertyView,
)


@admin.register(PropertyView)
class PropertyViewAdmin(admin.ModelAdmin):
    list_display = ["property", "ip_address", "session_key", "referrer", "created_at"]
    search_fields = ["property__yakeey_ref", "ip_address", "user_agent", "referrer"]
    list_filter = ["created_at", "property__city"]


@admin.register(PropertyClick)
class PropertyClickAdmin(admin.ModelAdmin):
    list_display = ["property", "click_type", "ip_address", "created_at"]
    search_fields = ["property__yakeey_ref", "ip_address"]
    list_filter = ["click_type", "created_at", "property__city"]


@admin.register(LeadEvent)
class LeadEventAdmin(admin.ModelAdmin):
    list_display = ["property", "agency", "source", "phone", "created_at"]
    search_fields = ["property__yakeey_ref", "agency__name", "phone", "source"]
    list_filter = ["source", "created_at", "agency"]


@admin.register(AgencyAnalyticsSummary)
class AgencyAnalyticsSummaryAdmin(admin.ModelAdmin):
    list_display = ["agency", "date", "views", "clicks", "leads", "top_property"]
    search_fields = ["agency__name", "top_property__yakeey_ref"]
    list_filter = ["date", "agency"]
