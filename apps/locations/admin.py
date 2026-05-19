"""Admin registrations for location hierarchy."""
from django.contrib import admin

from apps.locations.models import City, Country, District, Neighborhood


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "country")
    search_fields = ("name", "slug")
    list_filter = ("country",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "city")
    search_fields = ("name", "slug")
    list_filter = ("city",)


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "district")
    search_fields = ("name", "slug")
    list_filter = ("district",)
