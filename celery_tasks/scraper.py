"""Celery tasks for scraper workflows."""
import logging

from celery import shared_task

from apps.scraper.collector import PropertyFinderCollector


logger = logging.getLogger(__name__)


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
