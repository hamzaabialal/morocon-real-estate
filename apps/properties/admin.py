"""Admin configuration for property listings and related records."""
from django.contrib import admin

from apps.properties.models import Property, PropertyFeatures, PropertyImage


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "yakeey_ref",
        "title",
        "city",
        "price",
        "status",
        "is_featured",
        "views_count",
    ]
    search_fields = [
        "yakeey_ref",
        "formatted_address",
        "main_address",
        "description",
        "agent_name",
        "agent_phone",
    ]
    list_filter = [
        "status",
        "transaction_type",
        "property_category",
        "property_type",
        "city",
        "is_featured",
        "is_verified",
        "source",
        "media_status",
    ]
    readonly_fields = ["views_count", "created_at", "updated_at"]

    @admin.display(description="Title")
    def title(self, obj):
        return obj.formatted_address or obj.main_address or obj.yakeey_ref


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ["property", "url", "order", "is_main", "created_at"]
    search_fields = ["property__yakeey_ref", "url"]
    list_filter = ["is_main", "created_at"]


@admin.register(PropertyFeatures)
class PropertyFeaturesAdmin(admin.ModelAdmin):
    list_display = ["property", "furniture", "terrace", "garage", "pool", "created_at"]
    search_fields = ["property__yakeey_ref"]
    list_filter = ["furniture", "terrace", "garage", "pool", "created_at"]
