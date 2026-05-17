"""Subscription plan and billing API views."""
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.subscriptions.models import AgencySubscription, Payment, SubscriptionPlan
from apps.properties.models import Property
from apps.subscriptions.serializers import (
    AgencySubscriptionSerializer,
    SubscribeSerializer,
    SubscriptionPlanSerializer,
)


class SubscriptionPlanViewSet(ReadOnlyModelViewSet):
    """Public endpoint for active subscription plans."""

    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True).order_by("order")


class SubscriptionStatusView(APIView):
    """Return the current authenticated agency subscription."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        agency = getattr(request.user, "agency", None)
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )
        subscription = getattr(agency, "subscription", None)
        if subscription is None:
            return Response({"subscription": None, "plan": None})
        return Response({"subscription": AgencySubscriptionSerializer(subscription).data})


class SubscribeView(APIView):
    """Create a Stripe Checkout session for a plan subscription."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        agency = getattr(request.user, "agency", None)
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        plan_queryset = SubscriptionPlan.objects.filter(is_active=True)
        if data.get("plan_id"):
            plan = get_object_or_404(plan_queryset, id=data["plan_id"])
        else:
            plan = get_object_or_404(plan_queryset, slug=data["plan_slug"])

        if plan.price_monthly == 0:
            subscription, _ = AgencySubscription.objects.update_or_create(
                agency=agency,
                defaults={"plan": plan, "status": "active", "expires_at": None},
            )
            agency.subscription_plan = plan
            agency.subscription_expires_at = subscription.expires_at
            agency.save(update_fields=["subscription_plan", "subscription_expires_at"])
            return Response({"checkout_url": None, "subscription": subscription.id})

        if not plan.stripe_price_id:
            return Response(
                {
                    "error": "This plan is missing a Stripe price ID.",
                    "code": "MISSING_STRIPE_PRICE",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import stripe
        except ImportError:
            return Response(
                {"error": "Stripe SDK is not installed.", "code": "STRIPE_UNAVAILABLE"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        success_url = request.build_absolute_uri("/api/v1/subscriptions/status/")
        cancel_url = request.build_absolute_uri("/api/v1/subscriptions/plans/")
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=agency.email or request.user.email,
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"agency_id": str(agency.id), "plan_id": str(plan.id)},
            subscription_data={
                "metadata": {"agency_id": str(agency.id), "plan_id": str(plan.id)}
            },
        )
        return Response({"checkout_url": session.url})


class CancelSubscriptionView(APIView):
    """Cancel the current agency subscription."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        agency = getattr(request.user, "agency", None)
        if agency is None or not hasattr(agency, "subscription"):
            return Response(
                {"error": "No active subscription found.", "code": "NO_SUBSCRIPTION"},
                status=status.HTTP_404_NOT_FOUND,
            )

        subscription = agency.subscription
        if subscription.stripe_subscription_id:
            try:
                import stripe
            except ImportError:
                return Response(
                    {"error": "Stripe SDK is not installed.", "code": "STRIPE_UNAVAILABLE"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )

        subscription.status = "cancelled"
        subscription.save(update_fields=["status", "updated_at"])
        return Response({"status": "cancelled"})


class StripeWebhookView(APIView):
    """Handle Stripe billing webhooks."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            import stripe
        except ImportError:
            return Response(
                {"error": "Stripe SDK is not installed.", "code": "STRIPE_UNAVAILABLE"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.body
        signature = request.META.get("HTTP_STRIPE_SIGNATURE")
        if settings.STRIPE_WEBHOOK_SECRET:
            try:
                event = stripe.Webhook.construct_event(
                    payload, signature, settings.STRIPE_WEBHOOK_SECRET
                )
            except (ValueError, stripe.error.SignatureVerificationError):
                return Response(status=status.HTTP_400_BAD_REQUEST)
        else:
            event = request.data

        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        handlers = {
            "checkout.session.completed": self.handle_checkout_completed,
            "customer.subscription.updated": self.handle_subscription_updated,
            "customer.subscription.deleted": self.handle_subscription_deleted,
            "invoice.payment_failed": self.handle_invoice_payment_failed,
        }
        handler = handlers.get(event_type)
        if handler:
            handler(data_object)
        return Response({"received": True})

    @transaction.atomic
    def handle_checkout_completed(self, session):
        """Activate a subscription or boost listing after checkout succeeds."""
        metadata = session.get("metadata") or {}
        if metadata.get("type") == "listing_boost" or metadata.get("boost_property_id"):
            self.handle_listing_boost_checkout(session)
            return

        agency_id = metadata.get("agency_id")
        plan_id = metadata.get("plan_id")
        if not agency_id or not plan_id:
            return

        plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if not plan:
            return

        subscription, _ = AgencySubscription.objects.update_or_create(
            agency_id=agency_id,
            defaults={
                "plan": plan,
                "status": "active",
                "stripe_subscription_id": session.get("subscription"),
                "stripe_customer_id": session.get("customer"),
            },
        )
        subscription.agency.subscription_plan = plan
        subscription.agency.subscription_expires_at = subscription.expires_at
        subscription.agency.save(
            update_fields=["subscription_plan", "subscription_expires_at"]
        )
        Payment.objects.create(
            agency=subscription.agency,
            amount=plan.price_monthly,
            currency="MAD",
            status="completed",
            gateway="stripe",
            gateway_payment_id=session.get("payment_intent") or session.get("id"),
            description=f"{plan.name} subscription checkout",
        )

    def handle_listing_boost_checkout(self, session):
        """Mark a boosted listing as featured after successful checkout."""
        metadata = session.get("metadata") or {}
        property_id = metadata.get("boost_property_id")
        agency_id = metadata.get("agency_id")
        property_obj = Property.objects.filter(id=property_id, agency_id=agency_id).first()
        if not property_obj:
            return

        property_obj.is_featured = True
        property_obj.save(update_fields=["is_featured", "updated_at"])

        amount = Decimal(str(session.get("amount_total") or 20000)) / Decimal("100")
        payment_id = session.get("payment_intent") or session.get("id")
        payment = Payment.objects.filter(gateway_payment_id=session.get("id")).first()
        if payment:
            payment.status = "completed"
            payment.gateway_payment_id = payment_id
            payment.save(update_fields=["status", "gateway_payment_id"])
        else:
            Payment.objects.create(
                agency=property_obj.agency,
                amount=amount,
                currency=(session.get("currency") or "MAD").upper(),
                status="completed",
                gateway="stripe",
                gateway_payment_id=payment_id,
                description=f"Listing boost for {property_obj.yakeey_ref}",
            )

    def handle_subscription_updated(self, stripe_subscription):
        """Sync subscription status updates from Stripe."""
        subscription = self.find_subscription(stripe_subscription)
        if not subscription:
            return
        subscription.status = self.map_stripe_status(stripe_subscription.get("status"))
        subscription.expires_at = self.timestamp_to_datetime(
            stripe_subscription.get("current_period_end")
        )
        subscription.save(update_fields=["status", "expires_at", "updated_at"])
        subscription.agency.subscription_plan = subscription.plan
        subscription.agency.subscription_expires_at = subscription.expires_at
        subscription.agency.save(
            update_fields=["subscription_plan", "subscription_expires_at"]
        )

    def handle_subscription_deleted(self, stripe_subscription):
        """Mark a subscription as cancelled when Stripe deletes it."""
        subscription = self.find_subscription(stripe_subscription)
        if not subscription:
            return
        subscription.status = "cancelled"
        subscription.expires_at = timezone.now()
        subscription.save(update_fields=["status", "expires_at", "updated_at"])

    def handle_invoice_payment_failed(self, invoice):
        """Mark a subscription past due after a failed invoice payment."""
        stripe_subscription_id = invoice.get("subscription")
        stripe_customer_id = invoice.get("customer")
        subscription = AgencySubscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first() or AgencySubscription.objects.filter(
            stripe_customer_id=stripe_customer_id
        ).first()
        if not subscription:
            return
        subscription.status = "past_due"
        subscription.save(update_fields=["status", "updated_at"])
        Payment.objects.create(
            agency=subscription.agency,
            amount=subscription.plan.price_monthly,
            currency="MAD",
            status="failed",
            gateway="stripe",
            gateway_payment_id=invoice.get("id"),
            description="Stripe invoice payment failed",
        )

    def find_subscription(self, stripe_subscription):
        """Find a local subscription from a Stripe subscription object."""
        stripe_subscription_id = stripe_subscription.get("id")
        stripe_customer_id = stripe_subscription.get("customer")
        return AgencySubscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first() or AgencySubscription.objects.filter(
            stripe_customer_id=stripe_customer_id
        ).first()

    def map_stripe_status(self, stripe_status):
        """Map Stripe statuses into local subscription status choices."""
        if stripe_status in {"active", "trialing", "past_due"}:
            return stripe_status
        if stripe_status in {"canceled", "incomplete_expired", "unpaid"}:
            return "cancelled"
        return "past_due"

    def timestamp_to_datetime(self, value):
        """Convert a Stripe Unix timestamp into an aware datetime."""
        if not value:
            return None
        return datetime.fromtimestamp(value, tz=timezone.get_current_timezone())
