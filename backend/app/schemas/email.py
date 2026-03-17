"""Pydantic schemas for email templates and events."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.email import EmailEventType


class EmailTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=500)
    body_html: str
    body_text: str | None = None
    variables: dict | None = None


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    variables: dict | None = None


class EmailTemplateRead(EmailTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EmailEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    event_type: EmailEventType
    occurred_at: datetime
    metadata_: dict | None = Field(None, alias="metadata")


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    step_id: uuid.UUID | None
    mailgun_message_id: str | None
    sent_at: datetime | None
    subject: str
    events: list[EmailEventRead] = []


class MailgunWebhookPayload(BaseModel):
    """Represents the incoming Mailgun webhook event data."""
    signature: dict  # contains timestamp, token, signature
    event_data: dict = Field(..., alias="event-data")
