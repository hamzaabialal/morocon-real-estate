"""Read-only API viewsets for locations."""
from django.db.models import Avg, Count, Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.locations.models import City, Country, District, Neighborhood
from apps.locations.serializers import (
    CitySerializer,
    CountrySerializer,
    DistrictSerializer,
    NeighborhoodSerializer,
)
from apps.properties.models import Property


def parse_bbox(value):
    """Parse ?bbox=lng1,lat1,lng2,lat2 into min/max longitude/latitude."""
    try:
        lng1, lat1, lng2, lat2 = [float(part.strip()) for part in value.split(",")]
    except (AttributeError, TypeError, ValueError):
        return None
    min_lng, max_lng = sorted([lng1, lng2])
    min_lat, max_lat = sorted([lat1, lat2])
    return min_lng, min_lat, max_lng, max_lat


class CountryViewSet(ReadOnlyModelViewSet):
    """List and retrieve countries."""

    queryset = Country.objects.all()
    serializer_class = CountrySerializer


class CityViewSet(ReadOnlyModelViewSet):
    """List and retrieve cities."""

    serializer_class = CitySerializer

    def get_queryset(self):
        return City.objects.select_related("country").annotate(
            property_count=Count(
                "properties", filter=Q(properties__status="LISTED"), distinct=True
            )
        ).order_by("name")


class DistrictViewSet(ReadOnlyModelViewSet):
    """List and retrieve districts."""

    queryset = District.objects.select_related("city", "city__country").all()
    serializer_class = DistrictSerializer


class NeighborhoodViewSet(ReadOnlyModelViewSet):
    """List and retrieve neighborhoods."""

    queryset = Neighborhood.objects.select_related(
        "district", "district__city", "district__city__country"
    ).all()
    serializer_class = NeighborhoodSerializer


class MapClustersView(APIView):
    """Return property clusters for map rendering."""

    permission_classes = [AllowAny]

    def get(self, request):
        bbox = parse_bbox(request.query_params.get("bbox"))
        if bbox is None:
            return Response(
                {"error": "bbox must be lng1,lat1,lng2,lat2", "code": "INVALID_BBOX"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        min_lng, min_lat, max_lng, max_lat = bbox
        try:
            zoom = int(request.query_params.get("zoom", 10))
        except ValueError:
            zoom = 10

        queryset = Property.objects.filter(
            status="LISTED",
            latitude__isnull=False,
            longitude__isnull=False,
            longitude__gte=min_lng,
            longitude__lte=max_lng,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
        )

        if zoom < 10:
            rows = (
                queryset.values("city__name")
                .annotate(
                    count=Count("id"),
                    lat=Avg("latitude"),
                    lng=Avg("longitude"),
                )
                .order_by("city__name")
            )
            return Response(
                [
                    {
                        "city": row["city__name"],
                        "lat": row["lat"],
                        "lng": row["lng"],
                        "count": row["count"],
                    }
                    for row in rows
                ]
            )

        rows = (
            queryset.filter(neighborhood__isnull=False)
            .values("neighborhood__name")
            .annotate(count=Count("id"), lat=Avg("latitude"), lng=Avg("longitude"))
            .order_by("neighborhood__name")
        )
        return Response(
            [
                {
                    "neighborhood": row["neighborhood__name"],
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "count": row["count"],
                }
                for row in rows
            ]
        )
