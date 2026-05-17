"""Social publishing models for property media distribution."""
import uuid

from django.db import models


class SocialPost(models.Model):
    """A scheduled or published social post for a property listing."""

    PLATFORM_CHOICES = [
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("tiktok", "TikTok"),
        ("youtube", "YouTube"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("scheduled", "Scheduled"),
        ("posted", "Posted"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property", on_delete=models.CASCADE, related_name="social_posts"
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    post_url = models.URLField(null=True, blank=True)
    platform_post_id = models.CharField(max_length=150, null=True, blank=True)
    likes = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at", "-created_at"]
        indexes = [
            models.Index(fields=["platform", "status"]),
            models.Index(fields=["scheduled_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.property_id} on {self.platform}"
