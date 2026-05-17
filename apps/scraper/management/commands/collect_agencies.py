"""Run PropertyFinder.ma agency collection from the command line."""
from django.core.management.base import BaseCommand

from apps.scraper.collector import PropertyFinderCollector


class Command(BaseCommand):
    """Collect public PropertyFinder.ma agency data."""

    help = "Collect publicly available agency contact data from PropertyFinder.ma."

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=50)
        parser.add_argument("--proxy", default=None)
        parser.add_argument("--delay-min", type=float, default=2)
        parser.add_argument("--delay-max", type=float, default=5)

    def handle(self, *args, **options):
        collector = PropertyFinderCollector(
            proxy=options["proxy"],
            delay_min=options["delay_min"],
            delay_max=options["delay_max"],
        )
        run = collector.run(max_pages=options["pages"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Collection {run.status}: pages={run.pages_visited}, "
                f"found={run.agencies_found}, new={run.agencies_new}"
            )
        )
