"""High-performance public property marketplace API views."""
import uuid

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F, Q
from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.analytics.models import PropertyClick, PropertyView
from apps.analytics.utils import create_lead_event, get_client_ip
from apps.properties.models import Property
from apps.properties.serializers import PropertySerializer


class PropertyCursorPagination(CursorPagination):
    """Cursor pagination for deep marketplace browsing."""

    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-id"


class PropertyFilter(filters.FilterSet):
    """Frontend marketplace filter matrix."""

    city = filters.CharFilter(method="filter_city")
    property_type = filters.CharFilter(field_name="property_type", lookup_expr="iexact")
    transaction_type = filters.CharFilter(
        field_name="transaction_type", lookup_expr="iexact"
    )
    listing_type = filters.CharFilter(field_name="listing_type", lookup_expr="iexact")
    price_min = filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = filters.NumberFilter(field_name="price", lookup_expr="lte")
    area_min = filters.NumberFilter(field_name="area", lookup_expr="gte")
    area_max = filters.NumberFilter(field_name="area", lookup_expr="lte")
    bedrooms = filters.NumberFilter(field_name="bedrooms", lookup_expr="exact")
    bathrooms = filters.NumberFilter(field_name="bathrooms", lookup_expr="exact")

    class Meta:
        model = Property
        fields = [
            "city",
            "property_type",
            "transaction_type",
            "listing_type",
            "price_min",
            "price_max",
            "area_min",
            "area_max",
            "bedrooms",
            "bathrooms",
        ]

    def filter_city(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        query = Q(city__slug__iexact=value)
        try:
            query |= Q(city_id=uuid.UUID(value))
        except ValueError:
            pass
        return queryset.filter(query)


class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """Public search, listing, and detail API for scraped properties."""

    permission_classes = [AllowAny]
    serializer_class = PropertySerializer
    pagination_class = PropertyCursorPagination
    filterset_class = PropertyFilter
    search_fields = ["yakeey_ref", "description", "formatted_address", "main_address"]

    def get_queryset(self):
        return (
            Property.objects.select_related(
                "city",
                "district",
                "neighborhood",
                "agency",
            )
            .prefetch_related("images")
            .filter(status="LISTED")
            .order_by("-id")
        )

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def search(self, request):
        """Search listed properties using PostgreSQL full-text search."""
        query = request.query_params.get("q", "").strip()
        queryset = self.filter_queryset(self.get_queryset())
        if query:
            vector = (
                SearchVector("property_type", weight="A")
                + SearchVector("description", weight="B")
                + SearchVector("formatted_address", weight="B")
                + SearchVector("main_address", weight="B")
            )
            search_query = SearchQuery(query)
            queryset = (
                queryset.annotate(search=vector, rank=SearchRank(vector, search_query))
                .filter(search=search_query)
                .order_by("-rank", "-id")
            )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request):
        """Return featured public listings."""
        queryset = self.filter_queryset(self.get_queryset().filter(is_featured=True))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def similar(self, request, pk=None):
        """Return similar listings by location and property shape."""
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
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def view(self, request, pk=None):
        """Record a public property view."""
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

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def click(self, request, pk=None):
        """Record a public contact click."""
        property_obj = self.get_object()
        click_type = request.data.get("click_type")
        if click_type not in {"call", "whatsapp", "email", "share", "website"}:
            return Response(
                {"detail": "Invalid click_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        PropertyClick.objects.create(
            property=property_obj,
            click_type=click_type,
            ip_address=get_client_ip(request),
        )
        if click_type in {"call", "whatsapp", "email"}:
            create_lead_event(
                property_obj=property_obj,
                agency=property_obj.agency,
                phone=property_obj.agent_phone or None,
                source=click_type,
            )
        return Response({"status": "tracked"}, status=status.HTTP_200_OK)
