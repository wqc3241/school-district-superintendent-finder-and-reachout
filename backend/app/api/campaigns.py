"""Campaign CRUD, enrollment, and control API endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.schemas.campaign import (
    CampaignCreate,
    CampaignList,
    CampaignRead,
    CampaignUpdate,
    EnrollContactsRequest,
    EnrollmentRead,
)
from app.services.campaign_service import CampaignService

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/", response_model=CampaignRead, status_code=201)
async def create_campaign(data: CampaignCreate, db: DbSession) -> CampaignRead:
    service = CampaignService(db)
    campaign = await service.create(data)
    return CampaignRead.model_validate(campaign)


@router.get("/", response_model=CampaignList)
async def list_campaigns(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> CampaignList:
    service = CampaignService(db)
    items, total = await service.list(page=page, size=size)
    return CampaignList(
        items=[CampaignRead.model_validate(c) for c in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign_id: uuid.UUID, db: DbSession) -> CampaignRead:
    service = CampaignService(db)
    campaign = await service.get_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: uuid.UUID, data: CampaignUpdate, db: DbSession
) -> CampaignRead:
    service = CampaignService(db)
    campaign = await service.update(campaign_id, data)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(campaign_id: uuid.UUID, db: DbSession) -> None:
    service = CampaignService(db)
    deleted = await service.delete(campaign_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")


@router.post("/{campaign_id}/start", response_model=CampaignRead)
async def start_campaign(campaign_id: uuid.UUID, db: DbSession) -> CampaignRead:
    """Activate a campaign so enrollments start being processed."""
    service = CampaignService(db)
    campaign = await service.start(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignRead)
async def pause_campaign(campaign_id: uuid.UUID, db: DbSession) -> CampaignRead:
    """Pause an active campaign."""
    service = CampaignService(db)
    campaign = await service.pause(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignRead.model_validate(campaign)


@router.post("/{campaign_id}/enroll", response_model=list[EnrollmentRead], status_code=201)
async def enroll_contacts(
    campaign_id: uuid.UUID, data: EnrollContactsRequest, db: DbSession
) -> list[EnrollmentRead]:
    """Enroll one or more contacts into a campaign."""
    service = CampaignService(db)
    enrollments = await service.enroll_contacts(campaign_id, data.contact_ids)
    return [EnrollmentRead.model_validate(e) for e in enrollments]


@router.get("/{campaign_id}/enrollments", response_model=list[EnrollmentRead])
async def list_enrollments(campaign_id: uuid.UUID, db: DbSession) -> list[EnrollmentRead]:
    service = CampaignService(db)
    enrollments = await service.list_enrollments(campaign_id)
    return [EnrollmentRead.model_validate(e) for e in enrollments]
