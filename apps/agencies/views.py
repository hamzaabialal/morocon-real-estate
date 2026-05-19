"""Authentication and agency profile views."""
from datetime import timedelta
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from apps.agencies.models import Agency, User
from apps.agencies.permissions import IsAgencyOwnerOrAdmin
from apps.agencies.serializers import (
    AgencyPublicSerializer,
    AgencySerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)
from apps.analytics.models import LeadEvent, PropertyClick, PropertyView
from apps.properties.models import Property
from apps.properties.serializers import PropertyListSerializer
from apps.social.models import SocialPost
from apps.social.serializers import SocialPostSerializer


class RegisterView(APIView):
    """Create an agency and owner user in one transaction."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agency = Agency.objects.create(
            name=data["agency_name"],
            phone=data["phone"],
            email=data["email"],
            source="self_registered",
        )
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            role=User.Role.AGENCY_OWNER,
            agency=agency,
        )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "agency": AgencySerializer(agency).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Authenticate an email/password pair and return JWT tokens."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class LogoutView(APIView):
    """Blacklist a refresh token to log the user out."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required.", "code": "REFRESH_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgencyViewSet(ReadOnlyModelViewSet):
    """Public agency endpoints plus current agency profile management."""

    queryset = Agency.objects.select_related("city", "subscription_plan").all()
    serializer_class = AgencyPublicSerializer

    def get_serializer_class(self):
        if self.action == "me":
            return AgencySerializer
        return AgencyPublicSerializer

    @action(
        detail=False,
        methods=["get", "patch"],
        permission_classes=[IsAgencyOwnerOrAdmin],
        url_path="me",
    )
    def me(self, request):
        """Retrieve or update the current user's agency profile."""
        agency = request.user.agency
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.method == "PATCH":
            serializer = AgencySerializer(agency, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(AgencySerializer(agency).data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAgencyOwnerOrAdmin],
        url_path="me/analytics",
    )
    def analytics(self, request):
        """Return analytics for the current agency over a requested period."""
        agency = request.user.agency
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_days = {"7d": 7, "30d": 30, "90d": 90}
        period = request.query_params.get("period", "30d")
        if period not in period_days:
            return Response(
                {"error": "Invalid period. Use 7d, 30d, or 90d.", "code": "INVALID_PERIOD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        days = period_days[period]
        start_date = timezone.localdate() - timedelta(days=days - 1)
        previous_start = start_date - timedelta(days=days)
        previous_end = start_date - timedelta(days=1)

        property_ids = list(agency.properties.values_list("id", flat=True))
        views_qs = PropertyView.objects.filter(
            property_id__in=property_ids, created_at__date__gte=start_date
        )
        clicks_qs = PropertyClick.objects.filter(
            property_id__in=property_ids, created_at__date__gte=start_date
        )
        leads_qs = LeadEvent.objects.filter(
            agency=agency, created_at__date__gte=start_date
        )
        previous_views = PropertyView.objects.filter(
            property_id__in=property_ids,
            created_at__date__gte=previous_start,
            created_at__date__lte=previous_end,
        ).count()
        previous_clicks = PropertyClick.objects.filter(
            property_id__in=property_ids,
            created_at__date__gte=previous_start,
            created_at__date__lte=previous_end,
        ).count()

        views_by_date = {
            item["date"]: item["views"]
            for item in views_qs.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(views=Count("id"))
        }
        clicks_by_date = {
            item["date"]: item["clicks"]
            for item in clicks_qs.annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(clicks=Count("id"))
        }
        daily_views = []
        for index in range(days):
            day = start_date + timedelta(days=index)
            daily_views.append(
                {
                    "date": day.isoformat(),
                    "views": views_by_date.get(day, 0),
                    "clicks": clicks_by_date.get(day, 0),
                }
            )

        view_counts = {
            item["property_id"]: item["views"]
            for item in views_qs.values("property_id").annotate(views=Count("id"))
        }
        click_counts = {
            item["property_id"]: item["clicks"]
            for item in clicks_qs.values("property_id").annotate(clicks=Count("id"))
        }
        properties_by_id = {
            property_obj.id: property_obj
            for property_obj in Property.objects.filter(id__in=property_ids)
        }
        top_ids = sorted(
            property_ids,
            key=lambda property_id: (
                view_counts.get(property_id, 0),
                click_counts.get(property_id, 0),
            ),
            reverse=True,
        )[:5]
        top_listings = [
            {
                "id": str(property_id),
                "title": self.property_title(properties_by_id[property_id]),
                "views": view_counts.get(property_id, 0),
                "clicks": click_counts.get(property_id, 0),
                "cover_image_url": properties_by_id[property_id].cover_image_url,
            }
            for property_id in top_ids
            if property_id in properties_by_id
            and (view_counts.get(property_id, 0) or click_counts.get(property_id, 0))
        ]
        by_source = self.build_source_breakdown(views_qs)

        return Response(
            {
                "summary": {
                    "total_views": views_qs.count(),
                    "total_clicks": clicks_qs.count(),
                    "total_leads": leads_qs.count(),
                    "views_change_pct": self.percent_change(views_qs.count(), previous_views),
                    "clicks_change_pct": self.percent_change(clicks_qs.count(), previous_clicks),
                },
                "daily_views": daily_views,
                "top_listings": top_listings,
                "by_source": by_source,
            }
        )

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAgencyOwnerOrAdmin],
        url_path="me/leads",
    )
    def leads(self, request):
        """Return paginated leads for the current agency."""
        agency = request.user.agency
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )
        queryset = LeadEvent.objects.filter(agency=agency).select_related("property")
        page = self.paginate_queryset(queryset)
        lead_events = page if page is not None else queryset
        data = [
            {
                "id": str(lead.id),
                "property_id": str(lead.property_id),
                "property_title": self.property_title(lead.property),
                "source": lead.source,
                "masked_phone": self.mask_phone(lead.phone),
                "created_at": lead.created_at,
            }
            for lead in lead_events
        ]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAgencyOwnerOrAdmin],
        url_path="me/listings",
    )
    def my_listings(self, request):
        """Return agency listings with performance stats."""
        agency = request.user.agency
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )
        queryset = agency.properties.annotate(clicks_count=Count("analytics_clicks"))
        data = [
            {
                "id": str(property_obj.id),
                "yakeey_ref": property_obj.yakeey_ref,
                "title": self.property_title(property_obj),
                "price": property_obj.price,
                "status": property_obj.status,
                "views_count": property_obj.views_count,
                "clicks_count": property_obj.clicks_count,
                "days_listed": self.days_listed(property_obj),
                "is_featured": property_obj.is_featured,
                "cover_image_url": property_obj.cover_image_url,
                "media_status": property_obj.media_status,
                "media_generated_at": property_obj.media_generated_at,
                "reel_url": property_obj.reel_url,
                "square_video_url": property_obj.square_video_url,
                "caption_fr": property_obj.caption_fr,
                "caption_ar": property_obj.caption_ar,
                "caption_hashtags": property_obj.caption_hashtags,
            }
            for property_obj in queryset
        ]
        return Response(data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAgencyOwnerOrAdmin],
        url_path="me/social",
    )
    def social(self, request):
        """Return social posts for the current agency's properties."""
        agency = request.user.agency
        if agency is None:
            return Response(
                {"error": "No agency is linked to this user.", "code": "NO_AGENCY"},
                status=status.HTTP_404_NOT_FOUND,
            )
        queryset = SocialPost.objects.filter(property__agency=agency).select_related(
            "property"
        )
        page = self.paginate_queryset(queryset)
        social_posts = page if page is not None else queryset
        serializer = SocialPostSerializer(social_posts, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def listings(self, request, pk=None):
        """Return public listings for an agency."""
        agency = self.get_object()
        queryset = agency.properties.filter(status="LISTED").select_related(
            "city", "district", "neighborhood"
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PropertyListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PropertyListSerializer(queryset, many=True)
        return Response(serializer.data)

    def property_title(self, property_obj):
        """Build a display title for properties until a dedicated title field exists."""
        if property_obj.formatted_address:
            return property_obj.formatted_address
        return f"{property_obj.get_property_category_display()} {property_obj.yakeey_ref}".strip()

    def percent_change(self, current, previous):
        """Return percentage change from previous period."""
        if previous == 0:
            return 100.0 if current else 0.0
        return round(((current - previous) / previous) * 100, 1)

    def build_source_breakdown(self, views_qs):
        """Group view events by high-level referrer source."""
        sources = {"direct": 0}
        for view in views_qs.only("referrer"):
            source = self.referrer_source(view.referrer)
            sources[source] = sources.get(source, 0) + 1
        return sources

    def referrer_source(self, referrer):
        """Normalize a referrer URL into a dashboard source key."""
        if not referrer:
            return "direct"
        host = urlparse(referrer).netloc.lower()
        if "instagram" in host:
            return "instagram"
        if "facebook" in host or "fb." in host:
            return "facebook"
        if "tiktok" in host:
            return "tiktok"
        if "youtube" in host:
            return "youtube"
        return "direct"

    def mask_phone(self, phone):
        """Mask a phone number, showing only the final four digits."""
        if not phone:
            return None
        digits = "".join(character for character in phone if character.isdigit())
        return f"****{digits[-4:]}" if len(digits) >= 4 else "****"

    def days_listed(self, property_obj):
        """Return the number of days since listed_at or created_at."""
        start = property_obj.listed_at or property_obj.created_at
        if not start:
            return None
        return max((timezone.now() - start).days, 0)
