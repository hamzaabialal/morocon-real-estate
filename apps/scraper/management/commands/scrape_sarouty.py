"""Run the full Sarouty API scraping pipeline."""
import asyncio

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.scraper.orchestrator import run_full_sarouty_scrape


class Command(BaseCommand):
    help = "Run the full Sarouty.ma API scrape pipeline"

    def add_arguments(self, parser):
        parser.add_argument("--max-pages", type=int, dest="max_pages")
        parser.add_argument("--batch-size", type=int, default=25, dest="batch_size")

    def handle(self, *args, **options):
        max_pages = options["max_pages"]
        batch_size = options["batch_size"]

        if max_pages is not None and max_pages < 1:
            raise CommandError("--max-pages must be at least 1.")
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")

        job = asyncio.run(
            run_full_sarouty_scrape(
                max_pages=max_pages,
                batch_size=batch_size,
            )
        )

        duration = ""
        if job.started_at and job.finished_at:
            duration = str(job.finished_at - job.started_at)
        elif job.started_at:
            duration = str(timezone.now() - job.started_at)

        self.stdout.write(
            self.style.SUCCESS(
                "Sarouty scrape completed: "
                f"job={job.id}, status={job.status}, "
                f"records_scraped={job.records_scraped}, "
                f"errors_count={job.errors_count}, "
                f"duration={duration}"
            )
        )
