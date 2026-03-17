"""Celery Beat schedule configuration.

Import this module to register the periodic tasks with the Celery Beat scheduler.
"""

from celery.schedules import crontab

from app.tasks.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Process due campaign enrollments every minute
    "process-due-enrollments": {
        "task": "process_due_enrollments",
        "schedule": 60.0,  # every 60 seconds
        "options": {"queue": "campaigns"},
    },
    # Run batch email verification daily at 2 AM UTC
    "daily-email-verification": {
        "task": "app.tasks.enrichment.batch_verify_emails",
        "schedule": crontab(hour=2, minute=0),
        "args": ([],),  # Populated dynamically by a separate query task
        "options": {"queue": "enrichment"},
    },
}
