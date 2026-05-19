"""Raw agency collection models for PropertyFinder.ma data."""
import uuid

from django.db import models


class CollectedAgency(models.Model):
    """Public agency contact data collected from PropertyFinder.ma."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    whatsapp = models.CharField(max_length=30, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    city_raw = models.CharField(max_length=120, blank=True)
    propertyfinder_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    source_url = models.URLField()
    raw_data = models.JSONField(default=dict, blank=True)
    matched_agency = models.ForeignKey(
        "agencies.Agency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collected_propertyfinder_records",
    )
    match_confidence = models.FloatField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-collected_at"]
        verbose_name = "Collected Agency"
        verbose_name_plural = "Collected Agencies"

    def __str__(self) -> str:
        return self.name or self.source_url


class CollectionRun(models.Model):
    """Execution record for a PropertyFinder.ma agency collection run."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    pages_visited = models.IntegerField(default=0)
    agencies_found = models.IntegerField(default=0)
    agencies_new = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Collection Run"
        verbose_name_plural = "Collection Runs"

    def __str__(self) -> str:
        return f"PropertyFinder collection {self.started_at or self.id}"


class ScrapeJob(models.Model):
    """Execution record for Sarouty and Yakeey scraper jobs."""

    SOURCE_CHOICES = [
        ("sarouty", "sarouty"),
        ("yakeey", "yakeey"),
    ]
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("running", "running"),
        ("completed", "completed"),
        ("failed", "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    start_id = models.IntegerField(null=True, blank=True)
    end_id = models.IntegerField(null=True, blank=True)
    records_scraped = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Scrape Job"
        verbose_name_plural = "Scrape Jobs"

    def __str__(self) -> str:
        return f"{self.source} scrape {self.created_at or self.id}"


class ScrapeError(models.Model):
    """Individual record failure captured during a scraper job."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        ScrapeJob, on_delete=models.CASCADE, related_name="errors"
    )
    listing_id = models.IntegerField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Scrape Error"
        verbose_name_plural = "Scrape Errors"

    def __str__(self) -> str:
        return f"{self.job_id} error {self.listing_id or self.id}"
