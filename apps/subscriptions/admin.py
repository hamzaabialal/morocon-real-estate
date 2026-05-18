"""Admin configuration for subscription and payment models."""
from django.contrib import admin

from apps.subscriptions.models import AgencySubscription, Payment, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price_monthly", "is_active", "order"]
    search_fields = ["name", "slug", "description", "stripe_price_id"]
    list_filter = ["is_active", "has_analytics", "has_lead_notifications"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(AgencySubscription)
class AgencySubscriptionAdmin(admin.ModelAdmin):
    list_display = ["agency", "plan", "status", "started_at", "expires_at"]
    search_fields = ["agency__name", "stripe_subscription_id", "stripe_customer_id"]
    list_filter = ["status", "plan", "started_at", "expires_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["agency", "amount", "currency", "status", "gateway", "created_at"]
    search_fields = ["agency__name", "gateway_payment_id", "description"]
    list_filter = ["status", "gateway", "currency", "created_at"]
