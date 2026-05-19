"""ViewSets for property listing APIs."""
import logging
import threading
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.analytics.models import LeadEvent, PropertyClick, PropertyView
from apps.analytics.serializers import PropertyClickSerializer
from apps.analytics.utils import get_client_ip
from apps.properties import bulk_import as bulk_import_helpers
from apps.properties.filters import PropertyFilter
from apps.properties.models import Property
from apps.properties.permissions import IsAgencyUser
from apps.properties.serializers import PropertyDetailSerializer, PropertyListSerializer
from apps.social.models import SocialPost
from apps.social.serializers import SocialPostSerializer
from apps.subscriptions.models import Payment


logger = logging.getLogger(__name__)


BULK_IMPORTS = {}
BULK_IMPORT_LOCK = threading.Lock()


def _update_bulk_status(job_id, **fields):
    with BULK_IMPORT_LOCK:
        if job_id in BULK_IMPORTS:
            BULK_IMPORTS[job_id].update(fields)


def _process_bulk_media(job_id, property_ids):
    """Background worker: run media generation sequentially for each created property."""
    from celery_tasks.media import generate_media_for_property

    processed = 0
    failed = 0
    for property_id in property_ids:
        try:
            result = generate_media_for_property(str(property_id))
            if result.get("status") == "ready":
                processed += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Bulk import: media gen failed for property %s", property_id)
            failed += 1
        _update_bulk_status(
            job_id, processed=processed, failed_count=failed,
            progress=round((processed + failed) / len(property_ids) * 100, 1),
        )
    _update_bulk_status(
        job_id, state="complete", progress=100.0,
        processed=processed, failed_count=failed,
    )


class PropertyViewSet(ModelViewSet):
    """Property listing endpoints and public tracking actions."""

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = PropertyFilter
    search_fields = ["yakeey_ref", "description", "formatted_address", "main_address"]
    ordering_fields = ["price", "area", "listed_at", "created_at", "views_count"]
    ordering = ["-listed_at", "-updated_at"]

    def get_queryset(self):
        queryset = (
            Property.objects.select_related("city", "district", "neighborhood", "agency")
            .prefetch_related("images")
            .all()
        )
        if self.action in {"list", "featured", "similar"}:
            queryset = queryset.filter(status="LISTED")
        return queryset

    def get_serializer_class(self):
        if self.action in {"list", "featured", "similar", "search"}:
            return PropertyListSerializer
        return PropertyDetailSerializer

    def get_permissions(self):
        if self.action in {"create", "partial_update", "update", "boost", "regenerate_media", "bulk_import", "bulk_import_status"}:
            permission_classes = [IsAgencyUser]
        elif self.action == "destroy":
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]


    def perform_create(self, serializer):
        agency = getattr(self.request.user, "agency", None)
        if agency:
            serializer.save(agency=agency)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        property_obj = self.get_object()
        property_obj.status = "ARCHIVED"
        property_obj.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def search(self, request):
        """Full-text search listings while preserving normal property filters."""
        query = request.query_params.get("q", "").strip()
        queryset = self.filter_queryset(self.get_queryset().filter(status="LISTED"))
        if query:
            vector = (
                SearchVector("property_type", weight="A")
                + SearchVector("description", weight="B")
                + SearchVector("formatted_address", weight="B")
            )
            search_query = SearchQuery(query)
            queryset = (
                queryset.annotate(search=vector, rank=SearchRank(vector, search_query))
                .filter(search=search_query)
                .order_by("-rank", "-listed_at", "-updated_at")
            )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request):
        """Return featured public listings."""
        queryset = self.filter_queryset(self.get_queryset().filter(is_featured=True))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def similar(self, request, pk=None):
        """Return similar listings by neighborhood, category, type, or city."""
        property_obj = self.get_object()
        queryset = self.get_queryset().exclude(pk=property_obj.pk)

        if property_obj.neighborhood_id:
            queryset = queryset.filter(neighborhood_id=property_obj.neighborhood_id)
        else:
            queryset = queryset.filter(city_id=property_obj.city_id)

        queryset = queryset.filter(
            Q(property_category=property_obj.property_category)
            | Q(property_type=property_obj.property_type)
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def social(self, request, pk=None):
        """Return social performance for one listing."""
        property_obj = self.get_object()
        queryset = SocialPost.objects.filter(property=property_obj).select_related(
            "property"
        )
        totals = queryset.aggregate(
            total_likes=Sum("likes"),
            total_views=Sum("views"),
            total_shares=Sum("shares"),
        )
        serializer = SocialPostSerializer(queryset, many=True)
        return Response(
            {
                "summary": {
                    "likes": totals["total_likes"] or 0,
                    "views": totals["total_views"] or 0,
                    "shares": totals["total_shares"] or 0,
                    "posts_count": queryset.count(),
                },
                "posts": serializer.data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path="track-view",
    )
    def track_view(self, request, pk=None):
        """Record a property page view and increment its denormalized counter."""
        property_obj = self.get_object()
        PropertyView.objects.create(
            property=property_obj,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            referrer=request.META.get("HTTP_REFERER") or None,
            session_key=getattr(request.session, "session_key", None),
        )
        Property.objects.filter(pk=property_obj.pk).update(
            views_count=F("views_count") + 1
        )
        return Response({"status": "tracked"}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path="track-click",
    )
    def track_click(self, request, pk=None):
        """Record a public contact or engagement click for a property."""
        property_obj = self.get_object()
        serializer = PropertyClickSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        click = PropertyClick.objects.create(
            property=property_obj,
            click_type=serializer.validated_data["click_type"],
            ip_address=get_client_ip(request),
        )
        if click.click_type in {"call", "whatsapp", "email"}:
            LeadEvent.objects.create(
                property=property_obj,
                agency=property_obj.agency,
                phone=property_obj.agent_phone or None,
                source=click.click_type,
            )
        return Response({"status": "tracked"}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[AllowAny],
        url_path="bulk-import-template",
    )
    def bulk_import_template(self, request):
        """Return a small CSV template the user can fill in and re-upload."""
        response = HttpResponse(
            bulk_import_helpers.SAMPLE_CSV,
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="yakeey-bulk-import-template.csv"'
        return response

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAgencyUser],
        parser_classes=[MultiPartParser, FormParser],
        url_path="bulk-import",
    )
    def bulk_import(self, request):
        """Accept a CSV/Excel file and create listings + queue AI media generation."""
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "No file uploaded (expected field 'file')."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows, parse_errors = bulk_import_helpers.parse_file(file_obj)
        if not rows and parse_errors:
            return Response(
                {"error": "File could not be parsed.", "details": parse_errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_rows = 50
        if len(rows) > max_rows:
            return Response(
                {"error": f"Limit is {max_rows} rows per import. Got {len(rows)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        agency = request.user.agency
        created_ids = []
        row_errors = list(parse_errors)

        from apps.properties.signals import trigger_media_generation_on_create
        from django.db.models.signals import post_save

        post_save.disconnect(trigger_media_generation_on_create, sender=Property)
        try:
            for index, row in enumerate(rows):
                try:
                    with transaction.atomic():
                        prop = Property.objects.create(
                            agency=agency,
                            yakeey_ref=row["yakeey_ref"],
                            transaction_type=row["transaction_type"],
                            property_category=row["property_category"],
                            property_type=row.get("property_type", ""),
                            city=row["city"],
                            price=Decimal(str(row["price"])),
                            area=Decimal(str(row["area"])),
                            bedrooms=row.get("bedrooms", 0),
                            bathrooms=row.get("bathrooms", 0),
                            description=row.get("description", ""),
                            cover_image_url=row.get("cover_image_url", ""),
                        )
                    created_ids.append(prop.id)
                except Exception as exc:
                    row_errors.append(f"Row {index + 2} ({row.get('yakeey_ref', '?')}): {exc}")
        finally:
            post_save.connect(trigger_media_generation_on_create, sender=Property)

        job_id = uuid.uuid4().hex
        with BULK_IMPORT_LOCK:
            BULK_IMPORTS[job_id] = {
                "state": "running",
                "total": len(created_ids),
                "processed": 0,
                "failed_count": 0,
                "progress": 0.0,
                "row_errors": row_errors,
                "property_ids": [str(pid) for pid in created_ids],
            }

        if created_ids:
            thread = threading.Thread(
                target=_process_bulk_media,
                args=(job_id, created_ids),
                daemon=False,
            )
            thread.start()
        else:
            _update_bulk_status(job_id, state="complete", progress=100.0)

        return Response({
            "job_id": job_id,
            "created": len(created_ids),
            "skipped": len(row_errors),
            "row_errors": row_errors,
            "message": "Listings created. AI media generation started in background — poll /bulk-import-status/?job_id=… for progress.",
        }, status=status.HTTP_202_ACCEPTED)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAgencyUser],
        url_path="bulk-import-status",
    )
    def bulk_import_status(self, request):
        """Return the current state of a bulk-import job (poll this from the UI)."""
        job_id = request.query_params.get("job_id")
        if not job_id:
            return Response({"error": "job_id query param required"}, status=400)
        with BULK_IMPORT_LOCK:
            job = BULK_IMPORTS.get(job_id)
        if not job:
            return Response({"error": "Job not found (it may have expired)."}, status=404)
        return Response(job)

    @action(detail=True, methods=["post"], permission_classes=[IsAgencyUser], url_path="regenerate-media")
    def regenerate_media(self, request, pk=None):
        """Clear existing AI media + re-run captions + video generation for this property."""
        property_obj = self.get_object()
        user_agency_id = getattr(request.user, "agency_id", None)
        if not request.user.is_staff and property_obj.agency_id != user_agency_id:
            return Response(
                {"error": "You do not own this listing.", "code": "NOT_LISTING_OWNER"},
                status=status.HTTP_403_FORBIDDEN,
            )

        property_obj.media_status = "pending"
        property_obj.caption_fr = ""
        property_obj.caption_ar = ""
        property_obj.caption_hashtags = []
        property_obj.reel_url = ""
        property_obj.square_video_url = ""
        property_obj.media_generated_at = None
        property_obj.save(
            update_fields=[
                "media_status", "caption_fr", "caption_ar", "caption_hashtags",
                "reel_url", "square_video_url", "media_generated_at", "updated_at",
            ]
        )

        from celery_tasks.media import generate_media_for_property
        result = generate_media_for_property(str(property_obj.id))
        property_obj.refresh_from_db()
        return Response({
            "status": result.get("status", "unknown"),
            "media_status": property_obj.media_status,
            "caption_fr": property_obj.caption_fr,
            "caption_ar": property_obj.caption_ar,
            "caption_hashtags": property_obj.caption_hashtags,
            "reel_url": property_obj.reel_url,
            "square_video_url": property_obj.square_video_url,
            "media_generated_at": property_obj.media_generated_at,
            "error": result.get("error"),
        })

    @action(detail=True, methods=["post"], permission_classes=[IsAgencyUser])
    def boost(self, request, pk=None):
        """Create a one-time Stripe checkout session to boost a listing."""
        property_obj = self.get_object()
        user_agency_id = getattr(request.user, "agency_id", None)
        if not request.user.is_staff and property_obj.agency_id != user_agency_id:
            return Response(
                {"error": "You do not own this listing.", "code": "NOT_LISTING_OWNER"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not property_obj.agency_id:
            return Response(
                {"error": "This listing is not linked to an agency.", "code": "NO_AGENCY"},
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
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=property_obj.agency.email or getattr(request.user, "email", ""),
            line_items=[
                {
                    "price_data": {
                        "currency": "mad",
                        "unit_amount": 20000,
                        "product_data": {
                            "name": f"Listing boost {property_obj.yakeey_ref}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            success_url=request.build_absolute_uri(
                f"/api/v1/properties/{property_obj.id}/"
            ),
            cancel_url=request.build_absolute_uri(
                f"/api/v1/properties/{property_obj.id}/"
            ),
            metadata={
                "type": "listing_boost",
                "agency_id": str(property_obj.agency_id),
                "boost_property_id": str(property_obj.id),
            },
        )
        Payment.objects.create(
            agency=property_obj.agency,
            amount=Decimal("200.00"),
            currency="MAD",
            status="pending",
            gateway="stripe",
            gateway_payment_id=session.id,
            description=f"Listing boost for {property_obj.yakeey_ref}",
        )
        return Response({"checkout_url": session.url})
