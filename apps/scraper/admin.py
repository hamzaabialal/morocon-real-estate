"""Admin registrations for scraper bookkeeping."""
from django.contrib import admin

from apps.scraper.models import CollectedAgency, CollectionRun


@admin.register(CollectedAgency)
class CollectedAgencyAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "city_raw", "match_confidence", "matched_agency", "is_processed", "collected_at")
    list_filter = ("is_processed",)
    search_fields = ("name", "phone", "email", "propertyfinder_id")
    readonly_fields = ("id", "collected_at")


@admin.register(CollectionRun)
class CollectionRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "finished_at", "status", "pages_visited", "agencies_found", "agencies_new")
    list_filter = ("status",)
    readonly_fields = ("started_at", "finished_at", "pages_visited", "agencies_found", "agencies_new")
