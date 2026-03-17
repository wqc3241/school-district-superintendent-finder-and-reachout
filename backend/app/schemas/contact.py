"""Pydantic schemas for contact endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContactBase(BaseModel):
    district_id: uuid.UUID
    role: str = "superintendent"
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    prefix: str | None = None
    suffix: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    confidence_score: int = Field(0, ge=0, le=100)
    do_not_contact: bool = False


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    role: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    confidence_score: int | None = Field(None, ge=0, le=100)
    do_not_contact: bool | None = None


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    district_id: uuid.UUID
    role: str
    first_name: str
    last_name: str
    prefix: str | None = None
    suffix: str | None = None
    email: str | None = None
    email_status: str
    email_verified_at: datetime | None = None
    phone: str | None = None
    confidence_score: int
    do_not_contact: bool
    created_at: datetime
    updated_at: datetime
    # Joined fields from district
    district_name: str | None = None
    state: str | None = None


class ContactList(BaseModel):
    items: list[ContactRead]
    total: int
    page: int
    size: int


class ContactSearch(BaseModel):
    """Search/filter parameters for contacts."""
    state: str | None = None
    role: str | None = None
    email_status: str | None = None
    has_email: bool | None = None
    do_not_contact: bool | None = None
    min_confidence: int | None = Field(None, ge=0, le=100)
    query: str | None = None
