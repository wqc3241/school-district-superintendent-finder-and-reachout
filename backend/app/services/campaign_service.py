"""Campaign orchestration service."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campaign import (
    Campaign,
    CampaignEnrollment,
    CampaignStatus,
    CampaignStep,
    EnrollmentStatus,
)
from app.models.contact import Contact
from app.schemas.campaign import CampaignCreate, CampaignUpdate


class CampaignService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: CampaignCreate) -> Campaign:
        campaign = Campaign(name=data.name)
        self.db.add(campaign)
        await self.db.flush()

        if data.steps:
            for step_data in data.steps:
                step = CampaignStep(
                    campaign_id=campaign.id,
                    step_order=step_data.step_order,
                    delay_days=step_data.delay_days,
                    template_id=step_data.template_id,
                    send_window_start=step_data.send_window_start,
                    send_window_end=step_data.send_window_end,
                )
                self.db.add(step)
            await self.db.flush()

        await self.db.refresh(campaign)
        # Eagerly load steps for the response
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.steps))
            .where(Campaign.id == campaign.id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, campaign_id: uuid.UUID) -> Campaign | None:
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.steps))
            .where(Campaign.id == campaign_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, *, page: int = 1, size: int = 50
    ) -> tuple[list[Campaign], int]:
        count_stmt = select(func.count()).select_from(Campaign)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * size
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.steps))
            .order_by(Campaign.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, campaign_id: uuid.UUID, data: CampaignUpdate) -> Campaign | None:
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)

        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def delete(self, campaign_id: uuid.UUID) -> bool:
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            return False
        await self.db.delete(campaign)
        await self.db.flush()
        return True

    async def start(self, campaign_id: uuid.UUID) -> Campaign | None:
        """Activate a campaign. Only drafts or paused campaigns can be started."""
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            return None
        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise ValueError(
                f"Cannot start campaign in '{campaign.status.value}' status. "
                "Only 'draft' or 'paused' campaigns can be started."
            )
        if not campaign.steps:
            raise ValueError("Cannot start a campaign with no steps.")

        campaign.status = CampaignStatus.ACTIVE
        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def pause(self, campaign_id: uuid.UUID) -> Campaign | None:
        """Pause an active campaign."""
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            return None
        if campaign.status != CampaignStatus.ACTIVE:
            raise ValueError("Only active campaigns can be paused.")

        campaign.status = CampaignStatus.PAUSED
        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def enroll_contacts(
        self, campaign_id: uuid.UUID, contact_ids: list[uuid.UUID]
    ) -> list[CampaignEnrollment]:
        """Enroll contacts into a campaign with initial scheduling."""
        campaign = await self.get_by_id(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")

        # Get the first step to calculate initial send time
        first_step = next((s for s in campaign.steps if s.step_order == 1), None)
        if not first_step:
            raise ValueError("Campaign has no step with order 1")

        # Verify contacts exist and are contactable
        stmt = select(Contact).where(
            Contact.id.in_(contact_ids),
            Contact.do_not_contact.is_(False),
            Contact.email.isnot(None),
        )
        result = await self.db.execute(stmt)
        valid_contacts = list(result.scalars().all())

        # Check for existing enrollments to avoid duplicates
        existing_stmt = select(CampaignEnrollment.contact_id).where(
            CampaignEnrollment.campaign_id == campaign_id,
            CampaignEnrollment.contact_id.in_([c.id for c in valid_contacts]),
            CampaignEnrollment.status.in_(
                [EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED]
            ),
        )
        existing_result = await self.db.execute(existing_stmt)
        already_enrolled = set(existing_result.scalars().all())

        enrollments: list[CampaignEnrollment] = []
        now = datetime.now(UTC)

        for contact in valid_contacts:
            if contact.id in already_enrolled:
                continue

            next_send = now + timedelta(days=first_step.delay_days)
            enrollment = CampaignEnrollment(
                campaign_id=campaign_id,
                contact_id=contact.id,
                status=EnrollmentStatus.ACTIVE,
                current_step_order=1,
                next_send_at=next_send,
            )
            self.db.add(enrollment)
            enrollments.append(enrollment)

        await self.db.flush()
        for e in enrollments:
            await self.db.refresh(e)

        return enrollments

    async def list_enrollments(self, campaign_id: uuid.UUID) -> list[CampaignEnrollment]:
        stmt = (
            select(CampaignEnrollment)
            .where(CampaignEnrollment.campaign_id == campaign_id)
            .order_by(CampaignEnrollment.enrolled_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
