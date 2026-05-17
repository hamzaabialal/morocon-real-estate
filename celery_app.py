"""Celery application configuration for Yakeey."""
import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery(
    "yakeey",
    include=[
        "celery_tasks.analytics",
        "celery_tasks.properties",
        "celery_tasks.media",
        "celery_tasks.scraper",
        "celery_tasks.social",
    ],
)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND
app.conf.timezone = settings.CELERY_TIMEZONE

beat_schedule = {
    "aggregate-daily-analytics-midnight": {
        "task": "celery_tasks.analytics.aggregate_daily_analytics",
        "schedule": crontab(minute=0, hour=0),
    },
    "schedule-social-posts-9am": {
        "task": "celery_tasks.social.schedule_social_posts",
        "schedule": crontab(minute=0, hour=9),
    },
}

if settings.CELERY_SCRAPE_PROPERTYFINDER_ENABLED:
    beat_schedule["scrape-propertyfinder-every-24h"] = {
        "task": "celery_tasks.scraper.scrape_propertyfinder",
        "schedule": crontab(minute=0, hour=3),
    }

app.conf.beat_schedule = beat_schedule


@app.task(bind=True)
def debug_task(self):
    """Print the current Celery request for debugging worker setup."""
    print(f"Request: {self.request!r}")
