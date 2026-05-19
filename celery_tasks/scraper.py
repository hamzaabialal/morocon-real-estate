"""Celery tasks for scraper workflows."""
import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


@shared_task(name="run_nightly_sarouty_scrape", bind=True, max_retries=2)
def run_nightly_sarouty_scrape(self):
    """
    Nightly Celery Beat task - scrapes Sarouty for new listings.
    Deduplication is handled by Redis SET sarouty:scraped_ids (30-day TTL)
    and Property.objects.update_or_create on sarouty_id.
    So re-running never creates duplicates.
    """
    import asyncio

    from apps.scraper.orchestrator import run_full_scrape

    task_logger.info("Nightly Sarouty scrape started at %s", timezone.now())
    try:
        result = asyncio.run(run_full_scrape(max_pages=50, batch_size=25))
        task_logger.info("Nightly scrape completed: %s", result)
        return result
    except Exception as exc:
        task_logger.error("Nightly scrape failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


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


@shared_task
def scrape_propertyfinder(max_pages=3):
    """Run a PropertyFinder.ma scrape and persist CollectedAgency rows."""
    collector = PropertyFinderCollector()
    try:
        result = collector.run(max_pages=max_pages)
        logger.info("scrape_propertyfinder finished: %s", result)
        return result
    except Exception as exc:
        logger.exception("scrape_propertyfinder failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        collector.close()
