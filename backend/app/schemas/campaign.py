"""Pydantic schemas for campaign endpoints."""

import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.campaign import CampaignStatus, EnrollmentStatus


class CampaignStepBase(BaseModel):
    step_order: int = Field(..., ge=1)
    delay_days: int = Field(0, ge=0)
    template_id: uuid.UUID
    send_window_start: time | None = time(8, 0)
    send_window_end: time | None = time(17, 0)


class CampaignStepCreate(CampaignStepBase):
    pass


class CampaignStepRead(CampaignStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class CampaignBase(BaseModel):
    name: str = Field(..., max_length=255)


class CampaignCreate(CampaignBase):
    steps: list[CampaignStepCreate] | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    status: CampaignStatus | None = None


class CampaignRead(CampaignBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CampaignStatus
    created_by: uuid.UUID | None
    steps: list[CampaignStepRead] = []
    created_at: datetime
    updated_at: datetime


class CampaignList(BaseModel):
    items: list[CampaignRead]
    total: int
    page: int
    size: int


class EnrollContactsRequest(BaseModel):
    contact_ids: list[uuid.UUID]


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    contact_id: uuid.UUID
    status: EnrollmentStatus
    current_step_order: int
    next_send_at: datetime | None
    enrolled_at: datetime
