"""Run a local Celery worker with the project's default worker settings."""
import subprocess

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Start a Celery worker for local development."""

    help = "Run: celery -A celery_app worker --loglevel=info -c 2"

    def handle(self, *args, **options):
        command = ["celery", "-A", "celery_app", "worker", "--loglevel=info", "-c", "2"]
        self.stdout.write("Running: " + " ".join(command))
        try:
            completed = subprocess.run(command, check=False)
        except FileNotFoundError as exc:
            raise CommandError(
                "Celery executable was not found. Activate your virtualenv or install requirements."
            ) from exc
        if completed.returncode:
            raise CommandError(f"Celery worker exited with code {completed.returncode}.")
