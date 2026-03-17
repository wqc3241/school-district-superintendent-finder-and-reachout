"""Celery tasks for email verification and contact enrichment."""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def verify_contact_email(self, contact_id: str) -> dict:
    """Verify a single contact's email address via Mailgun validation API.

    Updates the contact record with the validation result.
    """
    logger.info("Verifying email for contact %s", contact_id)

    try:
        from datetime import UTC, datetime

        from sqlalchemy import create_engine, text

        from app.config import settings
        from app.services.email_service import EmailService

        engine = create_engine(settings.database_url_sync)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT email FROM contacts WHERE id = :id"),
                {"id": contact_id},
            ).fetchone()

            if not row or not row[0]:
                logger.warning("Contact %s has no email", contact_id)
                return {"contact_id": contact_id, "status": "no_email"}

            email = row[0]

        # Call Mailgun validation API
        email_service = EmailService()
        result = _run_async(email_service.verify_email(email))

        if result is None:
            status = "unknown"
        elif result.get("result") == "deliverable":
            status = "valid"
        elif result.get("result") == "undeliverable":
            status = "invalid"
        elif result.get("risk") == "high":
            status = "risky"
        else:
            status = "unknown"

        # Update contact in database
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE contacts SET email_status = :status, "
                    "email_verified_at = :verified_at WHERE id = :id"
                ),
                {
                    "status": status,
                    "verified_at": datetime.now(UTC),
                    "id": contact_id,
                },
            )
            conn.commit()

        logger.info("Email verification for %s: %s -> %s", contact_id, email, status)
        return {"contact_id": contact_id, "email": email, "status": status}

    except Exception as exc:
        logger.error("Email verification failed for %s: %s", contact_id, exc)
        raise self.retry(exc=exc)


@celery_app.task
def batch_verify_emails(contact_ids: list[str]) -> dict:
    """Dispatch email verification tasks for a batch of contacts."""
    dispatched = 0
    for contact_id in contact_ids:
        verify_contact_email.delay(contact_id)
        dispatched += 1

    logger.info("Dispatched %d email verification tasks", dispatched)
    return {"dispatched": dispatched}
