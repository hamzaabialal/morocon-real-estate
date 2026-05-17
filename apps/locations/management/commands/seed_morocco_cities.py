"""Seed Morocco and core launch cities."""
from django.core.management.base import BaseCommand

from apps.locations.models import City, Country


MOROCCO_CITIES = [
    "Casablanca",
    "Rabat",
    "Marrakech",
    "Fès",
    "Tanger",
    "Agadir",
    "Mohammedia",
    "Salé",
    "Kenitra",
    "Meknès",
    "Bouskoura",
    "Dar Bouazza",
    "El Jadida",
    "Bouznika",
    "Témara",
    "Skhirate",
]


class Command(BaseCommand):
    """Create the Morocco country record and seed launch cities."""

    help = "Seed Morocco country and core Moroccan cities."

    def handle(self, *args, **options):
        country, country_created = Country.objects.update_or_create(
            code="MA", defaults={"name": "Morocco"}
        )

        created = 0
        existing = 0
        for city_name in MOROCCO_CITIES:
            _, was_created = City.objects.get_or_create(
                name=city_name,
                country=country,
            )
            if was_created:
                created += 1
            else:
                existing += 1

        country_status = "created" if country_created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Morocco country {country_status}; "
                f"{created} cities created, {existing} already existed."
            )
        )
