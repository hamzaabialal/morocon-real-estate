"""Admin registrations for analytics events."""
from django.contrib import admin

from apps.analytics.models import AgencyAnalyticsSummary, LeadEvent, PropertyClick, PropertyView


@admin.register(PropertyView)
class PropertyViewAdmin(admin.ModelAdmin):
    list_display = ("property", "created_at", "ip_address", "referrer")
    list_filter = ("created_at",)
    search_fields = ("property__yakeey_ref", "ip_address", "referrer")
    readonly_fields = [field.name for field in PropertyView._meta.fields]


@admin.register(PropertyClick)
class PropertyClickAdmin(admin.ModelAdmin):
    list_display = ("property", "click_type", "created_at", "ip_address")
    list_filter = ("click_type", "created_at")
    search_fields = ("property__yakeey_ref",)
    readonly_fields = [field.name for field in PropertyClick._meta.fields]


@admin.register(LeadEvent)
class LeadEventAdmin(admin.ModelAdmin):
    list_display = ("agency", "property", "source", "phone", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("agency__name", "property__yakeey_ref")
    readonly_fields = [field.name for field in LeadEvent._meta.fields]


@admin.register(AgencyAnalyticsSummary)
class AgencyAnalyticsSummaryAdmin(admin.ModelAdmin):
    list_display = ("agency", "date", "views", "clicks", "leads")
    list_filter = ("date",)
    search_fields = ("agency__name",)
