"""Celery tasks for scraper workflows."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def run_sarouty_agency_scrape():
    """Monthly: scrape agency directory."""
    import asyncio
    from apps.scraper.agency_scraper import scrape_all_agencies

    result = asyncio.run(scrape_all_agencies())
    logger.info("Agency scrape complete: %s", result)
    return result


@shared_task
def run_sarouty_listing_discovery():
    """Daily: discover and scrape new listings."""
    import asyncio
    from apps.scraper.orchestrator import run_full_sarouty_scrape

    job = asyncio.run(run_full_sarouty_scrape())
    logger.info(
        "Listing scrape complete: %s scraped, %s errors",
        job.records_scraped,
        job.errors_count,
    )
    return {
        "job_id": str(job.id),
        "records_scraped": job.records_scraped,
        "errors_count": job.errors_count,
        "status": job.status,
    }


@shared_task
def scrape_sarouty_listing(listing_id: int, job_id: str):
    """Per-listing task for a queue-based approach."""
    import asyncio
    from apps.scraper.listing_scraper import scrape_listing
    from apps.scraper.models import ScrapeJob

    job = ScrapeJob.objects.get(id=job_id)
    return asyncio.run(scrape_listing(listing_id, job))


@shared_task
def run_yakeey_enrichment(file_path: str):
    """Manual trigger for Yakeey enrichment."""
    from django.core.management import call_command

    call_command("enrich_from_yakeey", file=file_path)
    return {"file_path": file_path}