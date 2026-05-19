"""Admin configuration for location hierarchy models."""
from django.contrib import admin

from apps.locations.models import City, Country, District, Neighborhood


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "created_at"]
    search_fields = ["name", "code"]
    list_filter = ["code", "created_at"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "country", "latitude", "longitude"]
    search_fields = ["name", "slug", "country__name"]
    list_filter = ["country", "created_at"]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "city", "created_at"]
    search_fields = ["name", "slug", "city__name"]
    list_filter = ["city", "created_at"]


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "district", "latitude", "longitude"]
    search_fields = ["name", "slug", "district__name", "district__city__name"]
    list_filter = ["district__city", "district", "created_at"]
