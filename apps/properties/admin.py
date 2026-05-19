"""Admin configuration for property listings and related records."""
from django.contrib import admin

from apps.properties.models import Property, PropertyFeatures, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0
    fields = ("order", "url", "is_main")


class PropertyFeaturesInline(admin.StackedInline):
    model = PropertyFeatures
    can_delete = False


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "yakeey_ref",
        "title",
        "city",
        "property_category",
        "price",
        "status",
        "media_status",
        "is_featured",
        "agency",
        "views_count",
    ]
    list_filter = [
        "status",
        "media_status",
        "transaction_type",
        "property_category",
        "property_type",
        "city",
        "is_featured",
        "is_verified",
        "source",
    ]
    search_fields = [
        "yakeey_ref",
        "description",
        "formatted_address",
        "main_address",
        "agency__name",
        "agent_name",
        "agent_phone",
    ]
    readonly_fields = (
        "id",
        "views_count",
        "media_generated_at",
        "created_at",
        "updated_at",
        "reel_url",
        "square_video_url",
        "caption_fr",
        "caption_ar",
        "caption_hashtags",
    )
    fieldsets = (
        ("Identity", {"fields": ("id", "yakeey_ref", "agency", "source")}),
        ("Listing", {"fields": ("transaction_type", "property_category", "property_type", "status", "is_featured")}),
        ("Price + area", {"fields": ("price", "currency", "area", "bedrooms", "bathrooms", "toilets")}),
        ("Location", {"fields": ("city", "district", "neighborhood", "latitude", "longitude", "formatted_address", "main_address")}),
        ("Agent", {"fields": ("agent_name", "agent_phone")}),
        ("Description", {"fields": ("description",)}),
        ("Media", {"fields": ("media_status", "media_generated_at", "cover_image_url", "reel_url", "square_video_url")}),
        ("AI captions", {"fields": ("caption_fr", "caption_ar", "caption_hashtags")}),
        ("Stats", {"fields": ("views_count", "created_at", "updated_at")}),
    )
    inlines = [PropertyImageInline, PropertyFeaturesInline]

    @admin.display(description="Title")
    def title(self, obj):
        return obj.formatted_address or obj.main_address or obj.yakeey_ref


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ["property", "url", "order", "is_main", "created_at"]
    list_filter = ["is_main", "created_at"]
    search_fields = ["property__yakeey_ref", "url"]


@admin.register(PropertyFeatures)
class PropertyFeaturesAdmin(admin.ModelAdmin):
    list_display = ["property"]
    search_fields = ["property__yakeey_ref"]
