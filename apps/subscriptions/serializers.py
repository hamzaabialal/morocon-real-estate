"""Serializers for subscription plans, subscriptions, and payments."""
from rest_framework import serializers

from apps.subscriptions.models import AgencySubscription, Payment, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Public serializer for active subscription plans."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price_monthly",
            "features",
            "max_listings",
            "has_analytics",
            "has_lead_notifications",
            "has_social_boost",
            "is_active",
            "order",
        ]
        read_only_fields = fields


class AgencySubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for an agency's current subscription."""

    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = AgencySubscription
        fields = [
            "id",
            "agency",
            "plan",
            "status",
            "started_at",
            "expires_at",
            "stripe_subscription_id",
            "stripe_customer_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment records."""

    class Meta:
        model = Payment
        fields = [
            "id",
            "agency",
            "amount",
            "currency",
            "status",
            "gateway",
            "gateway_payment_id",
            "description",
            "created_at",
        ]
        read_only_fields = fields


class SubscribeSerializer(serializers.Serializer):
    """Payload for starting a Stripe checkout subscription."""

    plan_id = serializers.UUIDField(required=False)
    plan_slug = serializers.SlugField(required=False)

    def validate(self, attrs):
        """Require either plan_id or plan_slug."""
        if not attrs.get("plan_id") and not attrs.get("plan_slug"):
            raise serializers.ValidationError("Provide either plan_id or plan_slug.")
        return attrs
