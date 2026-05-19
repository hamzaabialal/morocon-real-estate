"""URL configuration for the Yakeey API."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve as static_serve
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.agencies.urls import router as agencies_router
from apps.agencies.urls import urlpatterns as agencies_urlpatterns
from apps.analytics.urls import router as analytics_router
from apps.authentication.urls import urlpatterns as authentication_urlpatterns
from apps.locations.urls import router as locations_router
from apps.locations.urls import urlpatterns as locations_urlpatterns
from apps.media_engine.urls import router as media_engine_router
from apps.notifications.urls import router as notifications_router
from apps.properties.urls import router as properties_router
from apps.properties.views import short_url_redirect as _property_short_url_redirect
from apps.scraper.urls import router as scraper_router
from apps.scraper.urls import urlpatterns as scraper_urlpatterns
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


_TEMPLATES_DIR = settings.BASE_DIR / "templates"
_ASSETS_DIR = _TEMPLATES_DIR / "assets"
_MIRRORED_PAGES = [
    "homepage",
    "about", "dashboard", "features", "login", "map", "pricing", "properties", "signup",
    "dashboard/analytics", "dashboard/leads", "dashboard/billing",
    "dashboard/listings", "dashboard/social", "dashboard/media", "dashboard/settings",
    "properties/lv-992", "properties/rm-104", "properties/tg-558",
    "properties/rb-221", "properties/fz-014", "properties/es-770",
]

urlpatterns = [
    path("yakeey-control-panel/", admin.site.urls),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include((authentication_urlpatterns, "authentication"))),
    path("api/v1/", include((agencies_urlpatterns, "agencies"))),
    path("api/v1/", include((subscriptions_urlpatterns, "subscriptions"))),
    path("api/v1/", include((locations_urlpatterns, "locations"))),
    path("api/v1/", include((scraper_urlpatterns, "scraper"))),
    path("api/v1/", include((common_urlpatterns, "common"))),
    path("api/v1/", include(api_router.urls)),
    path("", TemplateView.as_view(template_name="homepage.html")),
    path("homepage", RedirectView.as_view(url="/", permanent=True)),
    path("homepage.html", RedirectView.as_view(url="/", permanent=True)),
    path("_flock.js", static_serve, {"path": "_flock.js", "document_root": _TEMPLATES_DIR}),
    path("assets/<path:path>", static_serve, {"document_root": _ASSETS_DIR}),
    *[
        path(page, TemplateView.as_view(template_name=f"{page}.html"))
        for page in _MIRRORED_PAGES if page != "homepage"
    ],
    *[
        path(f"{page}.html", RedirectView.as_view(url=f"/{page}", permanent=True))
        for page in _MIRRORED_PAGES if page != "homepage"
    ],
    path("properties/<uuid:property_id>", TemplateView.as_view(template_name="property_detail.html"), name="property-detail"),
    path("p/<str:short_code>", _property_short_url_redirect, name="property-short-url"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
