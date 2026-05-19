"""Orchestration for full Sarouty scrape runs."""
import asyncio

from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.scraper.dedup import is_already_scraped
from apps.scraper.listing_discovery import run_discovery
from apps.scraper.listing_scraper import scrape_listing
from apps.scraper.models import ScrapeJob


async def run_full_sarouty_scrape(
    start_id: int = None,
    end_id: int = None,
    batch_size: int = 100,
    force: bool = False,
) -> ScrapeJob:
    """Full pipeline: discovery or range, scrape each listing, return job."""
    job = await sync_to_async(ScrapeJob.objects.create, thread_sensitive=True)(
        source="sarouty",
        status="running",
        started_at=timezone.now(),
        start_id=start_id,
        end_id=end_id,
    )

    try:
        if start_id is not None and end_id is not None:
            listing_ids = (
                list(range(start_id, end_id + 1))
                if force
                else await _new_ids_from_range(start_id, end_id)
            )
            job.notes = f"Range discovery found {len(listing_ids)} new Sarouty listing IDs."
            await sync_to_async(job.save, thread_sensitive=True)(update_fields=["notes"])
        else:
            listing_ids = await run_discovery(job)

        safe_batch_size = max(1, batch_size)
        for index in range(0, len(listing_ids), safe_batch_size):
            batch = listing_ids[index : index + safe_batch_size]
            await asyncio.gather(*(scrape_listing(listing_id, job) for listing_id in batch))

        job.status = "completed"
        job.finished_at = timezone.now()
        await sync_to_async(job.save, thread_sensitive=True)(
            update_fields=["status", "finished_at"]
        )
        return job
    except Exception as exc:
        job.status = "failed"
        job.finished_at = timezone.now()
        job.notes = f"{job.notes or ''}\nPipeline failed: {exc}".strip()
        await sync_to_async(job.save, thread_sensitive=True)(
            update_fields=["status", "finished_at", "notes"]
        )
        return job


async def _new_ids_from_range(start_id: int, end_id: int) -> list[int]:
    ids = []
    for listing_id in range(start_id, end_id + 1):
        already_scraped = await sync_to_async(is_already_scraped, thread_sensitive=True)(
            listing_id
        )
        if not already_scraped:
            ids.append(listing_id)
    return ids
