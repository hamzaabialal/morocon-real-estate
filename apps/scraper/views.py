"""Internal admin API views for scraper monitoring and control."""
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scraper.models import ScrapeError, ScrapeJob
from apps.scraper.serializers import ScrapeErrorSerializer, ScrapeJobSerializer
from celery_tasks.scraper import (
    run_sarouty_listing_discovery,
    run_yakeey_enrichment,
    scrape_sarouty_listing,
)


class ScrapeJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ScrapeJob.objects.all().order_by("-created_at")
    serializer_class = ScrapeJobSerializer


class ScrapeErrorViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ScrapeError.objects.all().order_by("-created_at")
    serializer_class = ScrapeErrorSerializer


class StartSaroutyScrapeView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        run_sarouty_listing_discovery.delay()
        return Response(
            {"status": "started", "message": "Sarouty scrape queued"},
            status=status.HTTP_202_ACCEPTED,
        )


class StartYakeeyEnrichView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file_path = request.data.get("file_path")
        if not file_path:
            return Response(
                {"detail": "file_path is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        run_yakeey_enrichment.delay(file_path)
        return Response({"status": "started"}, status=status.HTTP_202_ACCEPTED)


class RetryScrapeJobView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, job_id):
        errors = ScrapeError.objects.filter(
            job_id=job_id,
            listing_id__isnull=False,
        )
        queued = 0
        for error in errors:
            scrape_sarouty_listing.delay(error.listing_id, str(job_id))
            queued += 1
        return Response({"queued": queued}, status=status.HTTP_202_ACCEPTED)
