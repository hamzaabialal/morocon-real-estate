"""Tests for Sarouty API scrape orchestration."""
import asyncio

import pytest

from apps.scraper import orchestrator
from apps.scraper.models import ScrapeJob


@pytest.mark.django_db
def test_run_full_sarouty_scrape_pages_and_batches(monkeypatch):
    scraped_ids = []

    async def fake_fetch_listing_page(page, limit=10):
        return {
            "data": {
                "data": [
                    {"property_id": page * 10 + 1},
                    {"property_id": page * 10 + 2},
                ],
                "meta": {"total": 4, "page": page, "limit": limit, "total_pages": 2},
            }
        }

    async def fake_scrape_and_save_listing(listing, job):
        scraped_ids.append((listing["property_id"], job.id))
        return True

    monkeypatch.setattr(orchestrator, "fetch_listing_page", fake_fetch_listing_page)
    monkeypatch.setattr(
        orchestrator,
        "scrape_and_save_listing",
        fake_scrape_and_save_listing,
    )

    job = asyncio.run(orchestrator.run_full_sarouty_scrape(max_pages=2, batch_size=2))

    assert job.status == "completed"
    assert job.source == "sarouty"
    assert job.notes == "Sarouty API discovery found 4 listings across 2 pages."
    assert [listing_id for listing_id, _ in scraped_ids] == [11, 12, 21, 22]
    assert ScrapeJob.objects.filter(id=job.id).exists()
