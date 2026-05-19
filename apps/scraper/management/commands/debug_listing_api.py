"""Fetch Sarouty's listing API endpoints for debugging."""
import json

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


ENDPOINTS = {
    "properties": "https://b2c-be-prod.api.sarouty.ma/api/properties?limit=6&page=1",
    "properties_sale": (
        "https://b2c-be-prod.api.sarouty.ma/api/properties"
        "?limit=6&page=1&transaction_type=sale"
    ),
    "properties_rent": (
        "https://b2c-be-prod.api.sarouty.ma/api/properties"
        "?limit=6&page=1&transaction_type=rent"
    ),
    "property_850000": "https://b2c-be-prod.api.sarouty.ma/api/properties/850000",
}


class Command(BaseCommand):
    help = "Fetch Sarouty's listing API responses and save them as JSON files."

    def handle(self, *args, **options):
        with httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            },
        ) as client:
            for name, url in ENDPOINTS.items():
                output_path = settings.BASE_DIR / f"debug_listing_api_{name}.json"
                try:
                    response = client.get(url)
                    payload = _decode_json(response)
                    output_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    keys = list(payload.keys()) if isinstance(payload, dict) else []
                    self.stdout.write(
                        f"{name}: HTTP {response.status_code}, keys={keys}, "
                        f"saved={output_path.name}"
                    )
                except Exception as exc:
                    error_payload = {"error": str(exc), "url": url}
                    output_path.write_text(
                        json.dumps(error_payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"{name}: failed ({exc}), saved={output_path.name}"
                        )
                    )


def _decode_json(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return {
            "status_code": response.status_code,
            "text": response.text,
        }
