"""Admin registrations for SocialPost rows."""
from django.contrib import admin

from apps.social.models import SocialPost


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "platform",
        "status",
        "scheduled_at",
        "posted_at",
        "post_url",
    )
    list_filter = ("status", "platform")
    search_fields = ("property__yakeey_ref", "post_url", "error_message")
    readonly_fields = ("id", "created_at", "posted_at", "post_url", "platform_post_id")
    actions = ["retry_publish"]

    @admin.action(description="Retry publishing selected posts now")
    def retry_publish(self, request, queryset):
        from celery_tasks.social import post_property_to_platform
        results = {"posted": 0, "failed": 0}
        for sp in queryset:
            sp.status = "scheduled"
            sp.save(update_fields=["status"])
            outcome = post_property_to_platform(str(sp.id))
            key = "posted" if outcome.get("status") == "posted" else "failed"
            results[key] += 1
        self.message_user(request, f"Retried {len(queryset)} post(s): {results}")
