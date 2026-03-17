"""Contact CRUD and search/filter API endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.schemas.contact import (
    ContactCreate,
    ContactList,
    ContactRead,
    ContactSearch,
    ContactUpdate,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("/", response_model=ContactRead, status_code=201)
async def create_contact(data: ContactCreate, db: DbSession) -> ContactRead:
    service = ContactService(db)
    contact = await service.create(data)
    return ContactRead.model_validate(contact)


@router.get("/", response_model=ContactList)
async def list_contacts(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    state: str | None = Query(None, min_length=2, max_length=2),
    role: str | None = Query(None),
    email_status: str | None = Query(None),
    has_email: bool | None = Query(None),
    do_not_contact: bool | None = Query(None),
    min_confidence: int | None = Query(None, ge=0, le=100),
    query: str | None = Query(None),
) -> ContactList:
    service = ContactService(db)
    search = ContactSearch(
        state=state,
        role=role,
        email_status=email_status,
        has_email=has_email,
        do_not_contact=do_not_contact,
        min_confidence=min_confidence,
        query=query,
    )
    items, total = await service.search(search, page=page, size=size)

    read_items = []
    for item in items:
        contact = item["contact"]
        cr = ContactRead.model_validate(contact)
        cr.district_name = item["district_name"]
        cr.state = item["state"]
        read_items.append(cr)

    return ContactList(
        items=read_items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(contact_id: uuid.UUID, db: DbSession) -> ContactRead:
    service = ContactService(db)
    contact = await service.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactRead.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: uuid.UUID, data: ContactUpdate, db: DbSession
) -> ContactRead:
    service = ContactService(db)
    contact = await service.update(contact_id, data)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactRead.model_validate(contact)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: uuid.UUID, db: DbSession) -> None:
    service = ContactService(db)
    deleted = await service.delete(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")


@router.post("/{contact_id}/verify-email", response_model=ContactRead)
async def verify_contact_email(contact_id: uuid.UUID, db: DbSession) -> ContactRead:
    """Trigger email verification for a contact via Mailgun validation API."""
    service = ContactService(db)
    contact = await service.verify_email(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactRead.model_validate(contact)
