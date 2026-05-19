"""Analytics and lead tracking models for property and agency reporting."""
import uuid

from django.db import models


class PropertyView(models.Model):
    """Single page-view event for a property listing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="analytics_views",
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(null=True, blank=True)
    channel = models.CharField(max_length=30, blank=True, db_index=True,
                               help_text="instagram / facebook / tiktok / youtube / direct etc. (from utm_source or referrer)")
    session_key = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Property View"
        verbose_name_plural = "Property Views"

    def __str__(self) -> str:
        return f"View for {self.property_id}"


class PropertyClick(models.Model):
    """Single contact or engagement click for a property listing."""

    CLICK_TYPE_CHOICES = [
        ("call", "Call"),
        ("whatsapp", "WhatsApp"),
        ("email", "Email"),
        ("map", "Map"),
        ("share", "Share"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="analytics_clicks",
    )
    click_type = models.CharField(max_length=20, choices=CLICK_TYPE_CHOICES)
    channel = models.CharField(max_length=30, blank=True, db_index=True,
                               help_text="instagram / facebook / tiktok / youtube / direct etc.")
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Property Click"
        verbose_name_plural = "Property Clicks"

    def __str__(self) -> str:
        return f"{self.click_type} click for {self.property_id}"


class AgencyAnalyticsSummary(models.Model):
    """Daily precomputed analytics summary for an agency."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "agencies.Agency",
        on_delete=models.CASCADE,
        related_name="analytics_summaries",
    )
    date = models.DateField()
    views = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    leads = models.IntegerField(default=0)
    top_property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="top_in_agency_summaries",
    )

    class Meta:
        ordering = ["-date", "agency__name"]
        unique_together = ("agency", "date")
        verbose_name = "Agency Analytics Summary"
        verbose_name_plural = "Agency Analytics Summaries"

    def __str__(self) -> str:
        return f"{self.agency_id} analytics for {self.date}"


class LeadEvent(models.Model):
    """Lead event generated from a contact action on a property."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="lead_events",
    )
    agency = models.ForeignKey(
        "agencies.Agency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_events",
    )
    phone = models.CharField(max_length=30, null=True, blank=True)
    source = models.CharField(max_length=50, help_text="How they contacted: call / whatsapp / email")
    channel = models.CharField(max_length=30, blank=True, db_index=True,
                               help_text="Where they came from: instagram / facebook / tiktok / youtube / direct")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lead Event"
        verbose_name_plural = "Lead Events"

    def __str__(self) -> str:
        return f"{self.source} lead for {self.property_id}"
