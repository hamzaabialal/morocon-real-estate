"""Router registrations for locations endpoints."""
from rest_framework.routers import DefaultRouter

from apps.locations.views import (
    CityViewSet,
    CountryViewSet,
    DistrictViewSet,
    MapClustersView,
    NeighborhoodViewSet,
)
from django.urls import path


router = DefaultRouter()
router.register("locations/countries", CountryViewSet, basename="country")
router.register("locations/cities", CityViewSet, basename="city")
router.register("locations/districts", DistrictViewSet, basename="district")
router.register(
    "locations/neighborhoods", NeighborhoodViewSet, basename="neighborhood"
)

urlpatterns = [
    path("locations/map-clusters/", MapClustersView.as_view(), name="map-clusters"),
]
