"""Admin configuration for collected PropertyFinder data."""
from django.contrib import admin

from apps.scraper.models import CollectedAgency, CollectionRun, ScrapeError, ScrapeJob


@admin.register(CollectedAgency)
class CollectedAgencyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "city_raw",
        "phone",
        "matched_agency",
        "match_confidence",
        "is_processed",
        "collected_at",
    ]
    search_fields = ["name", "phone", "email", "city_raw", "propertyfinder_id"]
    list_filter = ["is_processed", "city_raw", "collected_at"]


@admin.register(CollectionRun)
class CollectionRunAdmin(admin.ModelAdmin):
    list_display = [
        "started_at",
        "finished_at",
        "status",
        "pages_visited",
        "agencies_found",
        "agencies_new",
    ]
    search_fields = ["error_message"]
    list_filter = ["status", "started_at", "finished_at"]


@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display = [
        "source",
        "status",
        "records_scraped",
        "errors_count",
        "started_at",
        "finished_at",
    ]
    list_filter = ["source", "status", "started_at", "finished_at"]
    search_fields = ["notes"]


@admin.register(ScrapeError)
class ScrapeErrorAdmin(admin.ModelAdmin):
    list_display = ["job", "listing_id", "error_message", "created_at"]
    list_filter = ["job"]
    search_fields = ["listing_id", "url", "error_message"]
