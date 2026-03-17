"""Contact CRUD, search, and enrichment service."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.district import District
from app.schemas.contact import ContactCreate, ContactSearch, ContactUpdate
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class ContactService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: ContactCreate) -> Contact:
        contact = Contact(
            district_id=data.district_id,
            role=data.role,
            first_name=data.first_name,
            last_name=data.last_name,
            prefix=data.prefix,
            suffix=data.suffix,
            email=data.email,
            phone=data.phone,
            confidence_score=data.confidence_score,
            do_not_contact=data.do_not_contact,
        )
        self.db.add(contact)
        await self.db.flush()
        await self.db.refresh(contact)
        return contact

    async def get_by_id(self, contact_id: uuid.UUID) -> Contact | None:
        stmt = select(Contact).where(Contact.id == contact_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        filters: ContactSearch,
        *,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[dict], int]:
        """Search contacts with district name and state joined."""
        stmt = (
            select(
                Contact,
                District.name.label("district_name"),
                District.state.label("district_state"),
            )
            .join(District, Contact.district_id == District.id)
        )
        count_stmt = select(func.count()).select_from(Contact).join(District)

        if filters.state:
            stmt = stmt.where(District.state == filters.state.upper())
            count_stmt = count_stmt.where(District.state == filters.state.upper())

        if filters.role:
            stmt = stmt.where(Contact.role == filters.role)
            count_stmt = count_stmt.where(Contact.role == filters.role)

        if filters.email_status:
            stmt = stmt.where(Contact.email_status == filters.email_status)
            count_stmt = count_stmt.where(Contact.email_status == filters.email_status)

        if filters.has_email is True:
            stmt = stmt.where(Contact.email.isnot(None))
            count_stmt = count_stmt.where(Contact.email.isnot(None))
        elif filters.has_email is False:
            stmt = stmt.where(Contact.email.is_(None))
            count_stmt = count_stmt.where(Contact.email.is_(None))

        if filters.do_not_contact is not None:
            stmt = stmt.where(Contact.do_not_contact == filters.do_not_contact)
            count_stmt = count_stmt.where(Contact.do_not_contact == filters.do_not_contact)

        if filters.min_confidence is not None:
            stmt = stmt.where(Contact.confidence_score >= filters.min_confidence)
            count_stmt = count_stmt.where(Contact.confidence_score >= filters.min_confidence)

        if filters.query:
            pattern = f"%{filters.query}%"
            name_filter = or_(
                Contact.first_name.ilike(pattern),
                Contact.last_name.ilike(pattern),
                Contact.email.ilike(pattern),
                District.name.ilike(pattern),
            )
            stmt = stmt.where(name_filter)
            count_stmt = count_stmt.where(name_filter)

        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = stmt.order_by(Contact.last_name, Contact.first_name).offset(offset).limit(size)
        result = await self.db.execute(stmt)
        rows = result.all()

        items = []
        for contact, district_name, district_state in rows:
            items.append({
                "contact": contact,
                "district_name": district_name,
                "state": district_state,
            })

        return items, total

    async def update(self, contact_id: uuid.UUID, data: ContactUpdate) -> Contact | None:
        contact = await self.get_by_id(contact_id)
        if not contact:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contact, field, value)

        await self.db.flush()
        await self.db.refresh(contact)
        return contact

    async def delete(self, contact_id: uuid.UUID) -> bool:
        contact = await self.get_by_id(contact_id)
        if not contact:
            return False
        await self.db.delete(contact)
        await self.db.flush()
        return True

    async def verify_email(self, contact_id: uuid.UUID) -> Contact | None:
        """Verify a contact's email address via the Mailgun validation API."""
        contact = await self.get_by_id(contact_id)
        if not contact or not contact.email:
            return contact

        email_service = EmailService()
        validation_result = await email_service.verify_email(contact.email)

        if validation_result is None:
            contact.email_status = "unknown"
        elif validation_result.get("result") == "deliverable":
            contact.email_status = "valid"
            contact.confidence_score = min(100, contact.confidence_score + 20)
        elif validation_result.get("result") == "undeliverable":
            contact.email_status = "invalid"
        elif validation_result.get("risk") == "high":
            contact.email_status = "risky"
        else:
            contact.email_status = "unknown"

        contact.email_verified_at = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(contact)
        return contact
