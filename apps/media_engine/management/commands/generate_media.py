"""Run media generation queueing from the command line."""
from django.core.management.base import BaseCommand

from celery_tasks.media import generate_media_batch


class Command(BaseCommand):
    """Queue media generation for pending properties."""

    help = "Queue media generation for pending properties."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        result = generate_media_batch.run(limit=options["limit"])
        self.stdout.write(
            self.style.SUCCESS(f"Queued {result['queued']} properties for media generation.")
        )
