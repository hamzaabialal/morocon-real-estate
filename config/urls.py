"""URL configuration for the Yakeey API."""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.agencies.urls import router as agencies_router
from apps.agencies.urls import urlpatterns as agencies_urlpatterns
from apps.analytics.urls import router as analytics_router
from apps.locations.urls import router as locations_router
from apps.locations.urls import urlpatterns as locations_urlpatterns
from apps.media_engine.urls import router as media_engine_router
from apps.notifications.urls import router as notifications_router
from apps.properties.urls import router as properties_router
from apps.scraper.urls import router as scraper_router
from apps.social.urls import router as social_router
from apps.subscriptions.urls import router as subscriptions_router
from apps.subscriptions.urls import urlpatterns as subscriptions_urlpatterns
from common.urls import urlpatterns as common_urlpatterns


api_router = DefaultRouter()

for app_router in (
    properties_router,
    agencies_router,
    locations_router,
    analytics_router,
    scraper_router,
    subscriptions_router,
    notifications_router,
    media_engine_router,
    social_router,
):
    for prefix, viewset, basename in app_router.registry:
        api_router.register(prefix, viewset, basename=basename)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include((agencies_urlpatterns, "agencies"))),
    path("api/v1/", include((subscriptions_urlpatterns, "subscriptions"))),
    path("api/v1/", include((locations_urlpatterns, "locations"))),
    path("api/v1/", include((common_urlpatterns, "common"))),
    path("api/v1/", include(api_router.urls)),
]
