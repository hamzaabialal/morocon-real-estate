"""Run agency matching for collected PropertyFinder.ma records."""
from django.core.management.base import BaseCommand

from apps.scraper.matcher import match_collected_agencies


class Command(BaseCommand):
    """Match collected agency records against local Agency records."""

    help = "Match unprocessed collected agency records to agencies."

    def handle(self, *args, **options):
        stats = match_collected_agencies()
        self.stdout.write(
            self.style.SUCCESS(
                f"Matched={stats['matched']}, created={stats['created']}, "
                f"skipped={stats['skipped']}"
            )
        )
