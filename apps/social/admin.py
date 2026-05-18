"""Admin configuration for social publishing records."""
from django.contrib import admin

from apps.social.models import SocialPost


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = [
        "property",
        "platform",
        "status",
        "scheduled_at",
        "posted_at",
        "likes",
        "views",
        "shares",
    ]
    search_fields = ["property__yakeey_ref", "post_url", "platform_post_id"]
    list_filter = ["platform", "status", "scheduled_at", "posted_at", "created_at"]
