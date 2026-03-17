"""Mailgun webhook receiver for email delivery events."""

import hashlib
import hmac
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import DbSession
from app.config import settings
from app.models.campaign import CampaignEnrollment, EnrollmentStatus
from app.models.email import EmailEvent, EmailEventType, EmailMessage

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# Map Mailgun event names to our enum values
MAILGUN_EVENT_MAP: dict[str, EmailEventType] = {
    "accepted": EmailEventType.SENT,
    "delivered": EmailEventType.DELIVERED,
    "opened": EmailEventType.OPENED,
    "clicked": EmailEventType.CLICKED,
    "failed": EmailEventType.BOUNCED,
    "complained": EmailEventType.COMPLAINED,
    "unsubscribed": EmailEventType.UNSUBSCRIBED,
}

# Events that should change enrollment status
TERMINAL_EVENTS: dict[EmailEventType, EnrollmentStatus] = {
    EmailEventType.BOUNCED: EnrollmentStatus.BOUNCED,
    EmailEventType.COMPLAINED: EnrollmentStatus.UNSUBSCRIBED,
    EmailEventType.UNSUBSCRIBED: EnrollmentStatus.UNSUBSCRIBED,
}


def verify_mailgun_signature(
    timestamp: str, token: str, signature: str, signing_key: str
) -> bool:
    """Verify Mailgun webhook signature using HMAC-SHA256."""
    encoded_key = signing_key.encode("utf-8")
    data = f"{timestamp}{token}".encode("utf-8")
    expected = hmac.new(encoded_key, data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/mailgun")
async def handle_mailgun_webhook(request: Request, db: DbSession) -> dict[str, str]:
    """Receive and process Mailgun webhook events.

    Verifies the HMAC signature, maps the event type, stores it,
    and updates enrollment status for terminal events (bounce, complaint, unsub).
    """
    body = await request.json()

    # Verify signature
    sig_data = body.get("signature", {})
    timestamp = sig_data.get("timestamp", "")
    token = sig_data.get("token", "")
    signature = sig_data.get("signature", "")

    if not verify_mailgun_signature(
        timestamp, token, signature, settings.mailgun_webhook_signing_key
    ):
        logger.warning("Invalid Mailgun webhook signature received")
        raise HTTPException(status_code=406, detail="Invalid signature")

    # Parse event data
    event_data = body.get("event-data", {})
    event_name = event_data.get("event", "").lower()
    mailgun_message_id = event_data.get("message", {}).get("headers", {}).get("message-id", "")
    event_timestamp = event_data.get("timestamp")

    event_type = MAILGUN_EVENT_MAP.get(event_name)
    if not event_type:
        logger.info("Ignoring unknown Mailgun event: %s", event_name)
        return {"status": "ignored", "reason": f"unknown event type: {event_name}"}

    # Find the matching EmailMessage
    stmt = select(EmailMessage).where(EmailMessage.mailgun_message_id == mailgun_message_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        logger.warning("No message found for Mailgun ID: %s", mailgun_message_id)
        return {"status": "ignored", "reason": "message not found"}

    # Store the event
    occurred_at = (
        datetime.fromtimestamp(float(event_timestamp), tz=UTC)
        if event_timestamp
        else datetime.now(UTC)
    )
    email_event = EmailEvent(
        message_id=message.id,
        event_type=event_type,
        occurred_at=occurred_at,
        metadata_=event_data,
    )
    db.add(email_event)

    # Update enrollment status for terminal events
    if event_type in TERMINAL_EVENTS:
        enrollment_stmt = select(CampaignEnrollment).where(
            CampaignEnrollment.id == message.enrollment_id
        )
        enrollment_result = await db.execute(enrollment_stmt)
        enrollment = enrollment_result.scalar_one_or_none()
        if enrollment:
            enrollment.status = TERMINAL_EVENTS[event_type]
            logger.info(
                "Updated enrollment %s status to %s due to %s event",
                enrollment.id,
                enrollment.status.value,
                event_type.value,
            )

    logger.info("Processed Mailgun %s event for message %s", event_type.value, message.id)
    return {"status": "ok"}
