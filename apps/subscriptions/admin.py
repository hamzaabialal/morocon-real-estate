"""Admin registrations for subscription + payment models."""
from django.contrib import admin

from apps.subscriptions.models import AgencySubscription, Payment, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price_monthly", "max_listings", "is_active", "order")
    list_filter = ("is_active", "has_analytics", "has_lead_notifications", "has_social_boost")
    search_fields = ("name", "slug")


@admin.register(AgencySubscription)
class AgencySubscriptionAdmin(admin.ModelAdmin):
    list_display = ("agency", "plan", "status", "started_at", "expires_at", "stripe_subscription_id")
    list_filter = ("status", "plan")
    search_fields = ("agency__name", "stripe_subscription_id", "stripe_customer_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("agency", "amount", "currency", "status", "gateway", "created_at")
    list_filter = ("status", "gateway", "currency")
    search_fields = ("agency__name", "gateway_payment_id", "description")
