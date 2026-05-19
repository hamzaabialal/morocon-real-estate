"""Seed dummy data for local dev / demos.

Usage:
    python manage.py seed_dummy_data           # add if missing (idempotent)
    python manage.py seed_dummy_data --reset   # wipe DEMO-* rows first, then reseed
    python manage.py seed_dummy_data --with-media   # also enqueue AI media gen (slow + uses your API quotas)

What it creates:
  - 1 superuser  (admin@yakeey.local)
  - 3 agencies   (Atlas Realty, Marrakech Souk Properties, Tangier Sands)
  - 6 agency users (2 per agency: owner + agent)
  - Subscriptions (1 per agency: Pro / Starter / Free)
  - 18 properties (6 per agency, varied cities/categories/prices, mix of media statuses)
  - SocialPost rows for "ready" properties (4 platforms, mix of scheduled/posted/failed)
  - Sample analytics events (PropertyView, PropertyClick, LeadEvent)

All dummy rows use the prefix "DEMO-" in yakeey_ref so --reset can find them.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from apps.agencies.models import Agency
from apps.analytics.models import LeadEvent, PropertyClick, PropertyView
from apps.locations.models import City
from apps.properties.models import Property
from apps.properties.signals import trigger_media_generation_on_create
from apps.social.models import SocialPost
from apps.subscriptions.models import AgencySubscription, SubscriptionPlan


User = get_user_model()
DEMO_PREFIX = "DEMO-"
DEFAULT_PASSWORD = "demo1234"

PLACEHOLDER_COVERS = [
    "/assets/property-1-BF0RFkF4.jpg",
    "/assets/property-2-BdNA2aYD.jpg",
    "/assets/property-3-B-fIDnYp.jpg",
    "/assets/property-4-16KWJM64.jpg",
    "/assets/property-5-CgArBAFm.jpg",
    "/assets/property-6-Bg6-I-q8.jpg",
]

AGENCIES = [
    {
        "name": "Atlas Realty",
        "phone": "+212522000001",
        "whatsapp": "+212661111111",
        "email": "contact@atlas-realty.demo",
        "city_name": "Casablanca",
        "plan_slug": "pro",
        "owner_email": "owner.atlas@yakeey.local",
        "agent_email": "agent.atlas@yakeey.local",
    },
    {
        "name": "Marrakech Souk Properties",
        "phone": "+212524000002",
        "whatsapp": "+212662222222",
        "email": "hello@marrakech-souk.demo",
        "city_name": "Marrakech",
        "plan_slug": "starter",
        "owner_email": "owner.marrakech@yakeey.local",
        "agent_email": "agent.marrakech@yakeey.local",
    },
    {
        "name": "Tangier Sands",
        "phone": "+212539000003",
        "whatsapp": "+212663333333",
        "email": "info@tangier-sands.demo",
        "city_name": "Tangier",
        "plan_slug": "free",
        "owner_email": "owner.tangier@yakeey.local",
        "agent_email": "agent.tangier@yakeey.local",
    },
]

PROPERTY_TEMPLATES = [
    # (category, type, base price, area, beds, baths, description)
    ("VILLA",  "ISOLATED_HOUSE",   4500000, 320, 4, 3, "Sun-drenched villa with infinity pool and palm garden."),
    ("VILLA",  "ISOLATED_HOUSE",   8200000, 450, 6, 4, "Luxury seafront villa with private terrace."),
    ("RIAD",   "RIAD",             6800000, 280, 5, 4, "Restored riad in the Medina with central fountain and zellige tiles."),
    ("FLAT",   "APARTMENT",        1850000, 145, 3, 2, "Modern apartment with floor-to-ceiling windows and parking."),
    ("FLAT",   "STUDIO",           980000,  55,  1, 1, "Bright studio in central district, fully renovated."),
    ("HOUSE",  "TWINNED_HOUSE",    2400000, 180, 4, 2, "Family townhouse with garden, walking distance to schools."),
    ("OFFICE", "OFFICE",           3500000, 220, 0, 2, "Premium office space in the business district, glass facade."),
    ("FLAT",   "DUPLEX",           3100000, 240, 4, 3, "Duplex apartment with panoramic city views."),
    ("VILLA",  "ISOLATED_HOUSE",   12000000, 600, 7, 5, "Estate-grade villa with cinema room and gym."),
    ("HOUSE",  "STRIPED_HOUSE",    1650000, 130, 3, 2, "Cosy striped house in a quiet residential area."),
    ("RIAD",   "RIAD",             5500000, 260, 5, 4, "Traditional riad, ready to host guests, in the heart of the Medina."),
    ("FLAT",   "TRIPLEX",          4200000, 320, 5, 3, "Spacious triplex penthouse with terrace and sea view."),
]


def make_yakeey_ref(agency_slug, index):
    return f"{DEMO_PREFIX}{agency_slug[:3].upper()}-{index:03d}"


class Command(BaseCommand):
    help = "Seed dummy agencies, users, properties, posts, and analytics for local dev."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing DEMO-* rows first.")
        parser.add_argument("--with-media", action="store_true", help="Also enqueue AI media generation (slow).")

    def handle(self, *args, **options):
        reset = options["reset"]
        with_media = options["with_media"]

        if reset:
            self.reset()

        self.ensure_cities()
        self.ensure_plans()

        signal_disconnected = False
        if not with_media:
            post_save.disconnect(trigger_media_generation_on_create, sender=Property)
            signal_disconnected = True
            self.stdout.write(self.style.WARNING("Signal disconnected -- properties will be created without AI media."))

        try:
            superuser = self.ensure_superuser()
            agencies = self.create_agencies()
            properties = self.create_properties(agencies)
            self.create_social_posts(properties)
            self.create_analytics(properties)
        finally:
            if signal_disconnected:
                post_save.connect(trigger_media_generation_on_create, sender=Property)

        self.print_summary(superuser, agencies, properties)

    def reset(self):
        n_props = Property.objects.filter(yakeey_ref__startswith=DEMO_PREFIX).count()
        n_users = User.objects.filter(email__endswith="@yakeey.local").count()
        n_agencies = Agency.objects.filter(email__endswith=".demo").count()
        Property.objects.filter(yakeey_ref__startswith=DEMO_PREFIX).delete()
        AgencySubscription.objects.filter(agency__email__endswith=".demo").delete()
        Agency.objects.filter(email__endswith=".demo").delete()
        User.objects.filter(email__endswith="@yakeey.local").exclude(is_superuser=True).delete()
        self.stdout.write(self.style.WARNING(f"Reset: removed {n_props} demo properties, {n_agencies} agencies, {n_users-1} agency users."))

    def ensure_cities(self):
        if City.objects.count() == 0:
            self.stdout.write("No cities found -- running seed_morocco_cities...")
            from django.core.management import call_command
            call_command("seed_morocco_cities")

    def ensure_plans(self):
        defaults = [
            {"slug": "free",    "name": "Free",    "price_monthly": Decimal("0"),    "max_listings": 3,   "order": 0},
            {"slug": "starter", "name": "Starter", "price_monthly": Decimal("500"),  "max_listings": 25,  "order": 1, "has_analytics": True},
            {"slug": "pro",     "name": "Pro",     "price_monthly": Decimal("1500"), "max_listings": 100, "order": 2, "has_analytics": True, "has_lead_notifications": True},
            {"slug": "agency",  "name": "Agency",  "price_monthly": Decimal("5000"), "max_listings": None, "order": 3, "has_analytics": True, "has_lead_notifications": True, "has_social_boost": True},
        ]
        for plan_data in defaults:
            SubscriptionPlan.objects.get_or_create(slug=plan_data["slug"], defaults=plan_data)

    def ensure_superuser(self):
        user, created = User.objects.get_or_create(
            email="admin@yakeey.local",
            defaults={
                "first_name": "Yakeey",
                "last_name": "Admin",
                "role": getattr(User.Role, "ADMIN", "admin") if hasattr(User, "Role") else "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PASSWORD)
            user.save()
        return user

    def create_agencies(self):
        result = []
        for agency_data in AGENCIES:
            city = City.objects.filter(name__iexact=agency_data["city_name"]).first()
            agency, created = Agency.objects.get_or_create(
                email=agency_data["email"],
                defaults={
                    "name": agency_data["name"],
                    "phone": agency_data["phone"],
                    "whatsapp": agency_data["whatsapp"],
                    "city": city,
                    "is_verified": True,
                    "source": "self_registered",
                },
            )

            plan = SubscriptionPlan.objects.filter(slug=agency_data["plan_slug"]).first()
            if plan:
                AgencySubscription.objects.get_or_create(
                    agency=agency,
                    defaults={
                        "plan": plan,
                        "status": "active",
                        "started_at": timezone.now() - timedelta(days=30),
                        "expires_at": timezone.now() + timedelta(days=335),
                    },
                )

            owner = self._make_user(agency_data["owner_email"], "Owner", agency_data["name"].split()[0], agency, "agency_owner")
            agent = self._make_user(agency_data["agent_email"], "Agent", agency_data["name"].split()[0], agency, "agent")

            result.append({"agency": agency, "owner": owner, "agent": agent})
            tag = self.style.SUCCESS("[+]") if created else self.style.NOTICE("[=]")
            self.stdout.write(f"  {tag} agency {agency.name}")
        return result

    def _make_user(self, email, first, last, agency, role):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first,
                "last_name": last,
                "agency": agency,
                "role": role,
                "is_active": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PASSWORD)
            user.save()
        return user

    def create_properties(self, agencies):
        cities = list(City.objects.all())
        if not cities:
            return []

        created_properties = []
        for agency_info in agencies:
            agency = agency_info["agency"]
            agency_slug = agency.name.lower().replace(" ", "-")[:10]
            for idx, template in enumerate(PROPERTY_TEMPLATES[:6]):
                category, ptype, base_price, area, beds, baths, description = template
                ref = make_yakeey_ref(agency_slug, idx + 1)

                if Property.objects.filter(yakeey_ref=ref).exists():
                    continue

                price_jitter = random.uniform(0.85, 1.15)
                price = Decimal(str(int(base_price * price_jitter)))

                city = random.choice(cities)
                cover = random.choice(PLACEHOLDER_COVERS)

                media_status = random.choices(
                    ["ready", "pending", "failed"], weights=[60, 30, 10], k=1
                )[0]

                listed_days_ago = random.randint(1, 60)

                prop_data = {
                    "yakeey_ref": ref,
                    "transaction_type": "SALE",
                    "property_category": category,
                    "property_type": ptype,
                    "status": "LISTED",
                    "price": price,
                    "currency": "DH",
                    "area": Decimal(str(area)),
                    "bedrooms": beds,
                    "bathrooms": baths,
                    "toilets": max(1, baths - 1),
                    "description": description,
                    "cover_image_url": cover,
                    "city": city,
                    "agency": agency,
                    "is_featured": random.random() < 0.2,
                    "is_verified": True,
                    "source": "manual",
                    "media_status": media_status,
                    "agent_name": f"{agency_info['agent'].first_name} {agency_info['agent'].last_name}".strip(),
                    "agent_phone": agency.phone,
                    "listed_at": timezone.now() - timedelta(days=listed_days_ago),
                    "views_count": random.randint(0, 800),
                }

                if media_status == "ready":
                    prop_data["caption_fr"] = f"Magnifique {category.lower()} de {area}m² à {city.name}, {beds} chambres. Prix : {int(price):,} DH."
                    prop_data["caption_ar"] = f"عقار رائع بمساحة {area} متر مربع في {city.name}، {beds} غرف."
                    prop_data["caption_hashtags"] = [
                        f"#{city.name}", "#ImmobilierMaroc", f"#{category}", "#AVendre",
                        "#RealEstate", "#MoroccanProperty", f"#{beds}Chambres", "#Investissement",
                    ]
                    prop_data["reel_url"] = ""
                    prop_data["square_video_url"] = ""
                    prop_data["media_generated_at"] = timezone.now() - timedelta(hours=random.randint(1, 72))

                prop = Property.objects.create(**prop_data)
                created_properties.append(prop)

        self.stdout.write(f"  + {len(created_properties)} properties")
        return created_properties

    def create_social_posts(self, properties):
        platforms = [("instagram", 10), ("facebook", 10), ("tiktok", 13), ("youtube", 17)]
        total = 0
        for prop in properties:
            if prop.media_status != "ready":
                continue
            if SocialPost.objects.filter(property=prop).exists():
                continue
            for platform, hour in platforms:
                offset_days = random.choice([-2, -1, 0, 0, 1, 2])
                scheduled_at = timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=offset_days)
                if scheduled_at < timezone.now():
                    state = random.choice(["posted", "posted", "failed"])
                else:
                    state = "scheduled"

                post_url = ""
                posted_at = None
                error_message = ""
                if state == "posted":
                    post_url = f"https://{platform}.com/yakeey/p/{prop.yakeey_ref.lower()}-{random.randint(1000,9999)}"
                    posted_at = scheduled_at + timedelta(minutes=random.randint(1, 5))
                elif state == "failed":
                    error_message = f"{platform} publisher returned None — missing credentials (demo)"

                SocialPost.objects.create(
                    property=prop,
                    platform=platform,
                    status=state,
                    scheduled_at=scheduled_at,
                    posted_at=posted_at,
                    post_url=post_url,
                    error_message=error_message,
                    likes=random.randint(0, 600) if state == "posted" else 0,
                    views=random.randint(0, 8000) if state == "posted" else 0,
                    shares=random.randint(0, 60) if state == "posted" else 0,
                )
                total += 1
        self.stdout.write(f"  + {total} social posts")

    def create_analytics(self, properties):
        sources = ["call", "whatsapp", "email"]
        views_total = 0
        clicks_total = 0
        leads_total = 0
        for prop in properties:
            if random.random() > 0.5:
                continue
            v_count = random.randint(5, 40)
            for _ in range(v_count):
                PropertyView.objects.create(
                    property=prop,
                    ip_address=f"192.168.{random.randint(0,255)}.{random.randint(1,254)}",
                    user_agent="Mozilla/5.0 (demo seed)",
                )
            views_total += v_count
            c_count = max(1, v_count // 8)
            for _ in range(c_count):
                src = random.choice(sources)
                PropertyClick.objects.create(
                    property=prop,
                    click_type=src,
                    ip_address=f"192.168.{random.randint(0,255)}.{random.randint(1,254)}",
                )
                if prop.agency_id:
                    LeadEvent.objects.create(
                        property=prop,
                        agency=prop.agency,
                        phone=prop.agent_phone or None,
                        source=src,
                    )
                    leads_total += 1
                clicks_total += 1
            Property.objects.filter(id=prop.id).update(views_count=v_count)
        self.stdout.write(f"  + {views_total} views, {clicks_total} clicks, {leads_total} leads")

    def print_summary(self, superuser, agencies, properties):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("Seed complete -- login credentials (password = demo1234):"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(f"  superuser:        {superuser.email}                 -> /yakeey-control-panel/")
        for info in agencies:
            agency = info["agency"]
            self.stdout.write(f"  agency owner:     {info['owner'].email:<32}  ({agency.name})")
            self.stdout.write(f"  agency agent:     {info['agent'].email:<32}  ({agency.name})")
        self.stdout.write("")
        self.stdout.write(f"  Total properties in DB:  {Property.objects.count()}")
        self.stdout.write(f"  Total social posts:      {SocialPost.objects.count()}")
        self.stdout.write(f"  Total lead events:       {LeadEvent.objects.count()}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Run `python manage.py runserver` and login at /login with any of the above."))
