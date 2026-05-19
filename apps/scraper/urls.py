"""Router registrations for scraper endpoints."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.scraper.views import (
    RetryScrapeJobView,
    ScrapeErrorViewSet,
    ScrapeJobViewSet,
    StartSaroutyScrapeView,
    StartYakeeyEnrichView,
)


router = DefaultRouter()
router.register("admin/scrape/jobs", ScrapeJobViewSet, basename="scrape-jobs")
router.register("admin/scrape/errors", ScrapeErrorViewSet, basename="scrape-errors")

urlpatterns = [
    path(
        "admin/scrape/sarouty/start/",
        StartSaroutyScrapeView.as_view(),
        name="start-sarouty-scrape",
    ),
    path(
        "admin/scrape/yakeey/enrich/",
        StartYakeeyEnrichView.as_view(),
        name="start-yakeey-enrich",
    ),
    path(
        "admin/scrape/retry/<uuid:job_id>/",
        RetryScrapeJobView.as_view(),
        name="retry-scrape-job",
    ),
] + router.urls
