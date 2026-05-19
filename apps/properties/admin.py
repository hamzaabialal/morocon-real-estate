"""Admin registrations for property models."""
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
    list_display = (
        "yakeey_ref",
        "city",
        "property_category",
        "price",
        "status",
        "media_status",
        "agency",
        "created_at",
    )
    list_filter = ("status", "media_status", "property_category", "transaction_type", "source", "city")
    search_fields = ("yakeey_ref", "description", "formatted_address", "agency__name")
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
        ("Location", {"fields": ("city", "district", "neighborhood", "latitude", "longitude", "formatted_address")}),
        ("Description", {"fields": ("description",)}),
        ("Media", {"fields": ("media_status", "media_generated_at", "cover_image_url", "reel_url", "square_video_url")}),
        ("AI captions", {"fields": ("caption_fr", "caption_ar", "caption_hashtags")}),
        ("Stats", {"fields": ("views_count", "created_at", "updated_at")}),
    )
    inlines = [PropertyImageInline, PropertyFeaturesInline]


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ("property", "order", "is_main", "url")
    list_filter = ("is_main",)
    search_fields = ("property__yakeey_ref",)


@admin.register(PropertyFeatures)
class PropertyFeaturesAdmin(admin.ModelAdmin):
    list_display = ("property",)
    search_fields = ("property__yakeey_ref",)
