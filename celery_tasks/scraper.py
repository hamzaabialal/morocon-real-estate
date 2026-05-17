"""Celery tasks for scraper workflows."""
from celery import shared_task


@shared_task
def scrape_propertyfinder():
    """Placeholder for Phase 2 PropertyFinder.ma scraping."""
    return {"status": "disabled_placeholder"}
