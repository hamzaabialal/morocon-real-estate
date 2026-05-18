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
        "celery_tasks.notifications",
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
    "send-weekly-agency-report-monday-9am": {
        "task": "celery_tasks.notifications.send_weekly_agency_report",
        "schedule": crontab(minute=0, hour=9, day_of_week="monday"),
    },
    "run-sarouty-agencies-monthly": {
        "task": "celery_tasks.scraper.run_sarouty_agency_scrape",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),
        "options": {"timezone": "Africa/Casablanca"},
    },
    "run-sarouty-listings-daily": {
        "task": "celery_tasks.scraper.run_sarouty_listing_discovery",
        "schedule": crontab(hour=2, minute=0),
        "options": {"timezone": "Africa/Casablanca"},
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
