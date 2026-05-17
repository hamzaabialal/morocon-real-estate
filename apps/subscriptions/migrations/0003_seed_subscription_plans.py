from decimal import Decimal

from django.db import migrations


PLANS = [
    {
        "name": "Free",
        "slug": "free",
        "description": "Free listing plan for basic agency visibility.",
        "price_monthly": Decimal("0.00"),
        "features": {"featured_listings": 0, "unlimited": False},
        "max_listings": None,
        "has_analytics": False,
        "has_lead_notifications": False,
        "has_social_boost": False,
        "is_active": True,
        "order": 1,
    },
    {
        "name": "Starter",
        "slug": "starter",
        "description": "Analytics and up to 10 featured listings.",
        "price_monthly": Decimal("500.00"),
        "features": {"featured_listings": 10, "unlimited": False},
        "max_listings": 10,
        "has_analytics": True,
        "has_lead_notifications": False,
        "has_social_boost": False,
        "is_active": True,
        "order": 2,
    },
    {
        "name": "Pro",
        "slug": "pro",
        "description": "Analytics, lead notifications, and social boost tools.",
        "price_monthly": Decimal("1500.00"),
        "features": {
            "featured_listings": 50,
            "lead_notifications": True,
            "social_boost": True,
            "unlimited": False,
        },
        "max_listings": 50,
        "has_analytics": True,
        "has_lead_notifications": True,
        "has_social_boost": True,
        "is_active": True,
        "order": 3,
    },
    {
        "name": "Agency",
        "slug": "agency",
        "description": "All features with unlimited listing capacity.",
        "price_monthly": Decimal("5000.00"),
        "features": {
            "featured_listings": None,
            "lead_notifications": True,
            "social_boost": True,
            "unlimited": True,
        },
        "max_listings": None,
        "has_analytics": True,
        "has_lead_notifications": True,
        "has_social_boost": True,
        "is_active": True,
        "order": 4,
    },
]


def seed_subscription_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    for plan in PLANS:
        defaults = plan.copy()
        slug = defaults.pop("slug")
        SubscriptionPlan.objects.update_or_create(slug=slug, defaults=defaults)


def unseed_subscription_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug__in=[plan["slug"] for plan in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0002_alter_subscriptionplan_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_subscription_plans, unseed_subscription_plans),
    ]
