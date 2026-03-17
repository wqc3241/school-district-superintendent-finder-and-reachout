"""Celery task that processes due campaign enrollments and sends emails.

Runs every minute via Celery Beat. For each enrollment whose next_send_at has
passed and whose status is 'active', it renders the template, sends via Mailgun,
records the EmailMessage, and schedules the next step.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text

from app.config import settings
from app.services.email_service import EmailService, EmailSendError, TemplateRenderError
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="process_due_enrollments")
def process_due_enrollments() -> dict:
    """Process all enrollments that are due to send.

    Steps:
    1. Query enrollments where next_send_at <= now() AND status = 'active'
       AND the parent campaign is also active.
    2. For each enrollment, look up the current step's template.
    3. Render the template with contact + district variables.
    4. Send via Mailgun API.
    5. Record the EmailMessage.
    6. Advance to next step or mark completed.
    """
    engine = create_engine(settings.database_url_sync)
    email_service = EmailService()

    now = datetime.now(UTC)
    processed = 0
    errors = 0
    sent_today = _get_today_send_count(engine)

    if sent_today >= settings.daily_email_limit:
        logger.warning(
            "Daily email limit reached (%d/%d). Skipping processing.",
            sent_today,
            settings.daily_email_limit,
        )
        return {"processed": 0, "errors": 0, "reason": "daily_limit_reached"}

    with engine.connect() as conn:
        # Query due enrollments with campaign and step info
        rows = conn.execute(
            text("""
                SELECT
                    ce.id AS enrollment_id,
                    ce.contact_id,
                    ce.campaign_id,
                    ce.current_step_order,
                    cs.id AS step_id,
                    cs.template_id,
                    cs.delay_days,
                    et.subject,
                    et.body_html,
                    et.body_text,
                    c.first_name,
                    c.last_name,
                    c.prefix,
                    c.email AS contact_email,
                    c.role AS contact_role,
                    d.name AS district_name,
                    d.state AS district_state,
                    d.city AS district_city
                FROM campaign_enrollments ce
                JOIN campaigns camp ON camp.id = ce.campaign_id
                JOIN campaign_steps cs ON cs.campaign_id = ce.campaign_id
                    AND cs.step_order = ce.current_step_order
                JOIN email_templates et ON et.id = cs.template_id
                JOIN contacts c ON c.id = ce.contact_id
                JOIN districts d ON d.id = c.district_id
                WHERE ce.next_send_at <= :now
                    AND ce.status = 'active'
                    AND camp.status = 'active'
                    AND c.do_not_contact = false
                ORDER BY ce.next_send_at
                LIMIT 100
            """),
            {"now": now},
        ).fetchall()

        for row in rows:
            if sent_today >= settings.daily_email_limit:
                logger.warning("Hit daily email limit mid-batch. Stopping.")
                break

            try:
                # Build template variables
                variables = {
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "prefix": row.prefix or "",
                    "contact_role": row.contact_role,
                    "district_name": row.district_name,
                    "district_state": row.district_state,
                    "district_city": row.district_city or "",
                    "app_name": settings.app_name,
                }

                # Render template
                rendered = email_service.render_template(
                    subject_template=row.subject,
                    body_html_template=row.body_html,
                    variables=variables,
                    body_text_template=row.body_text,
                )

                # Send email
                mailgun_id = _run_async(
                    email_service.send_email(
                        to_email=row.contact_email,
                        subject=rendered["subject"],
                        body_html=rendered["body_html"],
                        body_text=rendered.get("body_text"),
                        custom_variables={
                            "enrollment_id": str(row.enrollment_id),
                            "step_id": str(row.step_id),
                        },
                    )
                )

                # Record EmailMessage
                conn.execute(
                    text("""
                        INSERT INTO email_messages
                            (id, enrollment_id, step_id, mailgun_message_id,
                             sent_at, subject, body_html)
                        VALUES
                            (gen_random_uuid(), :enrollment_id, :step_id,
                             :mailgun_id, :sent_at, :subject, :body_html)
                    """),
                    {
                        "enrollment_id": str(row.enrollment_id),
                        "step_id": str(row.step_id),
                        "mailgun_id": mailgun_id,
                        "sent_at": now,
                        "subject": rendered["subject"],
                        "body_html": rendered["body_html"],
                    },
                )

                # Advance to next step or mark completed
                next_step_row = conn.execute(
                    text("""
                        SELECT step_order, delay_days
                        FROM campaign_steps
                        WHERE campaign_id = :campaign_id
                            AND step_order > :current_order
                        ORDER BY step_order
                        LIMIT 1
                    """),
                    {
                        "campaign_id": str(row.campaign_id),
                        "current_order": row.current_step_order,
                    },
                ).fetchone()

                if next_step_row:
                    next_send = now + timedelta(days=next_step_row.delay_days)
                    conn.execute(
                        text("""
                            UPDATE campaign_enrollments
                            SET current_step_order = :next_order,
                                next_send_at = :next_send
                            WHERE id = :enrollment_id
                        """),
                        {
                            "next_order": next_step_row.step_order,
                            "next_send": next_send,
                            "enrollment_id": str(row.enrollment_id),
                        },
                    )
                else:
                    # No more steps -- mark enrollment as completed
                    conn.execute(
                        text("""
                            UPDATE campaign_enrollments
                            SET status = 'completed', next_send_at = NULL
                            WHERE id = :enrollment_id
                        """),
                        {"enrollment_id": str(row.enrollment_id)},
                    )

                conn.commit()
                processed += 1
                sent_today += 1

                logger.info(
                    "Sent step %d to %s for enrollment %s",
                    row.current_step_order,
                    row.contact_email,
                    row.enrollment_id,
                )

            except TemplateRenderError as exc:
                logger.error(
                    "Template render error for enrollment %s: %s", row.enrollment_id, exc
                )
                errors += 1

            except EmailSendError as exc:
                logger.error(
                    "Email send error for enrollment %s: %s", row.enrollment_id, exc
                )
                errors += 1

            except Exception as exc:
                logger.exception(
                    "Unexpected error processing enrollment %s: %s", row.enrollment_id, exc
                )
                errors += 1

    logger.info("Campaign processor finished: %d sent, %d errors", processed, errors)
    return {"processed": processed, "errors": errors}


def _get_today_send_count(engine) -> int:
    """Get the number of emails already sent today."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM email_messages WHERE sent_at >= :today_start"),
            {"today_start": today_start},
        )
        return result.scalar_one()
