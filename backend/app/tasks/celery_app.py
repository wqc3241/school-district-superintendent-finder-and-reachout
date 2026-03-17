"""Celery application configuration with Redis broker."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "superintendent_finder",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.scraping",
        "app.tasks.enrichment",
        "app.tasks.campaign_processor",
        "app.tasks.scheduled",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result expiry
    result_expires=3600,

    # Rate limiting
    task_default_rate_limit="10/m",

    # Beat schedule is loaded from scheduled.py
    beat_schedule={},
)
