"""Router registrations for subscriptions endpoints."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.subscriptions.views import (
    CancelSubscriptionView,
    StripeWebhookView,
    SubscribeView,
    SubscriptionPlanViewSet,
    SubscriptionStatusView,
)


router = DefaultRouter()
router.register("subscriptions/plans", SubscriptionPlanViewSet, basename="subscription-plan")

urlpatterns = [
    path("subscriptions/status/", SubscriptionStatusView.as_view(), name="subscription-status"),
    path("subscriptions/subscribe/", SubscribeView.as_view(), name="subscription-subscribe"),
    path("subscriptions/cancel/", CancelSubscriptionView.as_view(), name="subscription-cancel"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
