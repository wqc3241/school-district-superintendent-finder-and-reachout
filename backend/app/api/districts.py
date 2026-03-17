"""District CRUD API endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.schemas.district import DistrictCreate, DistrictList, DistrictRead, DistrictUpdate
from app.services.district_service import DistrictService

router = APIRouter(prefix="/districts", tags=["districts"])


@router.post("/", response_model=DistrictRead, status_code=201)
async def create_district(data: DistrictCreate, db: DbSession) -> DistrictRead:
    service = DistrictService(db)
    district = await service.create(data)
    return DistrictRead.model_validate(district)


@router.get("/", response_model=DistrictList)
async def list_districts(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    state: str | None = Query(None, min_length=2, max_length=2),
    query: str | None = Query(None),
    esl_only: bool = Query(False),
    title_i_only: bool = Query(False),
    funding_type: str | None = Query(None, description="Filter by funding: title_i, title_iii, both"),
) -> DistrictList:
    service = DistrictService(db)
    items, total = await service.list(
        page=page,
        size=size,
        state=state,
        query=query,
        esl_only=esl_only,
        title_i_only=title_i_only,
        funding_type=funding_type,
    )
    return DistrictList(
        items=[DistrictRead.model_validate(d) for d in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{district_id}", response_model=DistrictRead)
async def get_district(district_id: uuid.UUID, db: DbSession) -> DistrictRead:
    service = DistrictService(db)
    district = await service.get_by_id(district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return DistrictRead.model_validate(district)


@router.patch("/{district_id}", response_model=DistrictRead)
async def update_district(
    district_id: uuid.UUID, data: DistrictUpdate, db: DbSession
) -> DistrictRead:
    service = DistrictService(db)
    district = await service.update(district_id, data)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    return DistrictRead.model_validate(district)


@router.delete("/{district_id}", status_code=204)
async def delete_district(district_id: uuid.UUID, db: DbSession) -> None:
    service = DistrictService(db)
    deleted = await service.delete(district_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="District not found")
