"""Scrape the Sarouty.ma agency directory."""
import asyncio

from django.core.management.base import BaseCommand

from apps.scraper.agency_scraper import scrape_all_agencies


class Command(BaseCommand):
    help = "Scrape Sarouty.ma agency directory (Phase A)"

    def handle(self, *args, **options):
        summary = asyncio.run(scrape_all_agencies())
        self.stdout.write(
            self.style.SUCCESS(
                "Sarouty agency scrape completed: "
                f"total_found={summary['total_found']}, "
                f"created={summary['created']}, "
                f"updated={summary['updated']}"
            )
        )
