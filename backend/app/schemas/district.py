"""Pydantic schemas for district endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DistrictBase(BaseModel):
    nces_id: str = Field(..., max_length=12)
    name: str = Field(..., max_length=255)
    state: str = Field(..., min_length=2, max_length=2)
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    website: str | None = None
    esl_program_status: bool | None = False
    ell_student_count: int | None = None
    ell_percentage: float | None = Field(None, ge=0, le=100)
    title_iii_allocation: Decimal | None = None
    title_i_status: bool | None = False
    title_i_allocation: Decimal | None = None
    metadata_: dict | None = Field(None, alias="metadata")


class DistrictCreate(DistrictBase):
    pass


class DistrictUpdate(BaseModel):
    name: str | None = None
    state: str | None = Field(None, min_length=2, max_length=2)
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    website: str | None = None
    esl_program_status: bool | None = None
    ell_student_count: int | None = None
    ell_percentage: float | None = None
    title_iii_allocation: Decimal | None = None
    title_i_status: bool | None = None
    title_i_allocation: Decimal | None = None
    metadata_: dict | None = Field(None, alias="metadata")


class DistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    nces_id: str
    name: str
    state: str
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    website: str | None = None
    esl_program_status: bool | None = False
    ell_student_count: int | None = None
    ell_percentage: float | None = None
    title_iii_allocation: Decimal | None = None
    title_i_status: bool | None = False
    title_i_allocation: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class DistrictList(BaseModel):
    items: list[DistrictRead]
    total: int
    page: int
    size: int
