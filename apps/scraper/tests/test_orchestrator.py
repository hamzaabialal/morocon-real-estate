"""Tests for Sarouty scrape orchestration."""
import asyncio

import pytest

from apps.scraper import orchestrator
from apps.scraper.models import ScrapeJob


@pytest.mark.django_db
def test_run_full_sarouty_scrape_range_filters_and_batches(monkeypatch):
    scraped_ids = []

    monkeypatch.setattr(
        orchestrator,
        "is_already_scraped",
        lambda listing_id: listing_id == 2,
    )

    async def fake_scrape_listing(listing_id, job):
        scraped_ids.append((listing_id, job.id))
        return True

    monkeypatch.setattr(orchestrator, "scrape_listing", fake_scrape_listing)

    job = asyncio.run(
        orchestrator.run_full_sarouty_scrape(start_id=1, end_id=3, batch_size=2)
    )

    assert job.status == "completed"
    assert job.source == "sarouty"
    assert job.notes == "Range discovery found 2 new Sarouty listing IDs."
    assert [listing_id for listing_id, _ in scraped_ids] == [1, 3]
    assert ScrapeJob.objects.filter(id=job.id).exists()
