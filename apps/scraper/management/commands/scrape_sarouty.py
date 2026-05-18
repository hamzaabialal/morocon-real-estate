"""Run the full Sarouty scraping pipeline."""
import asyncio

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.scraper.orchestrator import run_full_sarouty_scrape


class Command(BaseCommand):
    help = "Run the full Sarouty.ma scrape pipeline"

    def add_arguments(self, parser):
        parser.add_argument("--start-id", type=int, dest="start_id")
        parser.add_argument("--end-id", type=int, dest="end_id")
        parser.add_argument("--batch-size", type=int, default=100, dest="batch_size")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Scrape the provided range even if IDs are already marked scraped.",
        )

    def handle(self, *args, **options):
        start_id = options["start_id"]
        end_id = options["end_id"]
        batch_size = options["batch_size"]
        force = options["force"]

        if (start_id is None) != (end_id is None):
            raise CommandError("--start-id and --end-id must be provided together.")
        if start_id is not None and start_id > end_id:
            raise CommandError("--start-id must be less than or equal to --end-id.")
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")

        job = asyncio.run(
            run_full_sarouty_scrape(
                start_id=start_id,
                end_id=end_id,
                batch_size=batch_size,
                force=force,
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
