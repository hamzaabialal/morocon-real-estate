"""Filtering helpers for property search APIs."""
import django_filters
from rest_framework.exceptions import ValidationError

from apps.properties.models import Property


class PropertyFilter(django_filters.FilterSet):
    """Filter property lists by location, listing attributes, price, area, and map box."""

    city = django_filters.CharFilter(field_name="city__slug", lookup_expr="iexact")
    district = django_filters.CharFilter(
        field_name="district__slug", lookup_expr="iexact"
    )
    neighborhood = django_filters.CharFilter(
        field_name="neighborhood__slug", lookup_expr="iexact"
    )
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    area_min = django_filters.NumberFilter(field_name="area", lookup_expr="gte")
    area_max = django_filters.NumberFilter(field_name="area", lookup_expr="lte")
    bbox = django_filters.CharFilter(method="filter_bbox")

    class Meta:
        model = Property
        fields = [
            "city",
            "district",
            "neighborhood",
            "transaction_type",
            "property_category",
            "bedrooms",
            "furnished",
            "is_featured",
        ]

    def filter_bbox(self, queryset, name, value):
        """Filter properties inside ?bbox=lng1,lat1,lng2,lat2."""
        try:
            lng1, lat1, lng2, lat2 = [float(part.strip()) for part in value.split(",")]
        except (TypeError, ValueError):
            raise ValidationError(
                {"bbox": "bbox must be four comma-separated numbers: lng1,lat1,lng2,lat2"}
            )

        min_lng, max_lng = sorted([lng1, lng2])
        min_lat, max_lat = sorted([lat1, lat2])
        return queryset.filter(
            longitude__gte=min_lng,
            longitude__lte=max_lng,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
        )
