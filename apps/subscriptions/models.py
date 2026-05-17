"""Subscription models for agency plan assignments."""
import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def build_unique_slug(model_class, value: str, instance_pk=None) -> str:
    """Build a unique slug for subscription plans."""
    base_slug = slugify(value) or "plan"
    slug = base_slug
    counter = 2

    queryset = model_class.objects.filter(slug=slug)
    if instance_pk:
        queryset = queryset.exclude(pk=instance_pk)

    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        queryset = model_class.objects.filter(slug=slug)
        if instance_pk:
            queryset = queryset.exclude(pk=instance_pk)
        counter += 1

    return slug


class SubscriptionPlan(models.Model):
    """Plan definition used to gate agency SaaS features."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    features = models.JSONField(default=dict, blank=True)
    max_listings = models.IntegerField(null=True, blank=True)
    has_analytics = models.BooleanField(default=False)
    has_lead_notifications = models.BooleanField(default=False)
    has_social_boost = models.BooleanField(default=False)
    stripe_price_id = models.CharField(max_length=120, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "price_monthly", "name"]
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"

    def save(self, *args, **kwargs) -> None:
        """Auto-generate a unique slug from the plan name."""
        if not self.slug:
            self.slug = build_unique_slug(SubscriptionPlan, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class AgencySubscription(models.Model):
    """Current subscription state for an agency."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("cancelled", "Cancelled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.OneToOneField(
        "agencies.Agency",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=120, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Agency Subscription"
        verbose_name_plural = "Agency Subscriptions"

    @property
    def is_active(self) -> bool:
        """Return whether the subscription currently grants paid features."""
        if self.status not in {"active", "trialing"}:
            return False
        return self.expires_at is None or self.expires_at >= timezone.now()

    def __str__(self) -> str:
        return f"{self.agency_id} - {self.plan.name}"


class Payment(models.Model):
    """Payment record for subscriptions and manual billing events."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    GATEWAY_CHOICES = [("stripe", "Stripe"), ("manual", "Manual")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "agencies.Agency",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default="MAD")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default="stripe")
    gateway_payment_id = models.CharField(max_length=120, null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} for {self.agency_id}"
