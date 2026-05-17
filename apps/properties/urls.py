"""Router registrations for properties endpoints."""
from rest_framework.routers import DefaultRouter

from apps.properties.views import PropertyViewSet


router = DefaultRouter()
router.register("properties", PropertyViewSet, basename="property")
