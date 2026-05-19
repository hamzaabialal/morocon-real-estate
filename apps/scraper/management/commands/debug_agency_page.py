"""Fetch and save the raw Sarouty agency directory HTML for parser debugging."""
import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


AGENCY_DIRECTORY_URL = "https://www.sarouty.ma/trouver-une-agence/"


class Command(BaseCommand):
    help = "Fetch Sarouty's agency directory page and save raw HTML."

    def handle(self, *args, **options):
        response = httpx.get(
            AGENCY_DIRECTORY_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8",
            },
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()

        output_path = settings.BASE_DIR / "debug_agency_page.html"
        output_path.write_text(response.text, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {len(response.text)} bytes from {response.url} to {output_path}"
            )
        )
