"""Orchestration for full Sarouty API scrape runs."""
import asyncio
import logging
import math

from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.scraper.dedup import filter_unscraped_ids
from apps.scraper.listing_scraper import fetch_listing_page, scrape_and_save_listing
from apps.scraper.models import ScrapeJob

logger = logging.getLogger(__name__)


async def run_full_sarouty_scrape(
    max_pages: int = 50,
    batch_size: int = 25,
) -> ScrapeJob:
    """Full API pipeline: page discovery, scrape listings, return completed job."""
    job = await sync_to_async(ScrapeJob.objects.create, thread_sensitive=True)(
        source="sarouty",
        status="running",
        started_at=timezone.now(),
    )

    try:
        safe_batch_size = max(1, batch_size)
        page_limit = 50
        first_payload = await fetch_listing_page(page=1, limit=page_limit)
        listings, meta = _extract_listings_and_meta(first_payload)
        total = int(meta.get("total") or len(listings))
        total_pages = int(
            meta.get("total_pages")
            or math.ceil(total / page_limit)
            or 1
        )
        if max_pages is not None:
            total_pages = min(total_pages, max(1, max_pages))

        job.notes = f"Sarouty API discovery found {total} listings across {total_pages} pages."
        await sync_to_async(job.save, thread_sensitive=True)(update_fields=["notes"])

        for page in range(1, total_pages + 1):
            if page == 1:
                page_listings = listings
            else:
                payload = await fetch_listing_page(page=page, limit=page_limit)
                page_listings, _ = _extract_listings_and_meta(payload)

            if page_listings:
                page_listings = await _filter_unscraped_listings(page_listings)
                for index in range(0, len(page_listings), safe_batch_size):
                    batch = page_listings[index : index + safe_batch_size]
                    await asyncio.gather(
                        *(
                            scrape_and_save_listing(listing, job)
                            for listing in batch
                        ),
                        return_exceptions=True,
                    )

            if page % 10 == 0 or page == total_pages:
                logger.info(
                    "Sarouty scrape progress: page %s/%s, scraped=%s, errors=%s",
                    page,
                    total_pages,
                    job.records_scraped,
                    job.errors_count,
                )

        job.status = "completed"
        job.finished_at = timezone.now()
        await sync_to_async(job.save, thread_sensitive=True)(
            update_fields=["status", "finished_at"]
        )
        return job
    except Exception as exc:
        logger.exception("Sarouty API scrape pipeline failed")
        job.status = "failed"
        job.finished_at = timezone.now()
        job.notes = f"{job.notes or ''}\nPipeline failed: {exc}".strip()
        await sync_to_async(job.save, thread_sensitive=True)(
            update_fields=["status", "finished_at", "notes"]
        )
        return job


def _extract_listings_and_meta(payload: dict | None) -> tuple[list[dict], dict]:
    if not isinstance(payload, dict):
        return [], {}
    data = payload.get("data")
    if not isinstance(data, dict):
        return [], {}
    listings = data.get("data") if isinstance(data.get("data"), list) else []
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return listings, meta


async def _filter_unscraped_listings(listings: list[dict]) -> list[dict]:
    listing_ids = []
    for listing in listings:
        listing_id = listing.get("property_id")
        if listing_id is not None:
            listing_ids.append(int(listing_id))

    unscraped_ids = await sync_to_async(filter_unscraped_ids, thread_sensitive=True)(
        listing_ids
    )
    filtered = []
    for listing in listings:
        listing_id = listing.get("property_id")
        if listing_id is None or int(listing_id) in unscraped_ids:
            filtered.append(listing)
    return filtered
