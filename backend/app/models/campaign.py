"""Campaign models for multi-step email outreach sequences."""

import enum
import uuid
from datetime import datetime, time

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    BOUNCED = "bounced"
    REPLIED = "replied"
    UNSUBSCRIBED = "unsubscribed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", native_enum=False),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    steps: Mapped[list["CampaignStep"]] = relationship(
        "CampaignStep",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignStep.step_order",
    )
    enrollments: Mapped[list["CampaignEnrollment"]] = relationship(
        "CampaignEnrollment", back_populates="campaign", cascade="all, delete-orphan"
    )
    creator: Mapped["User | None"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Campaign {self.name} ({self.status.value})>"


class CampaignStep(Base):
    __tablename__ = "campaign_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    send_window_start: Mapped[time | None] = mapped_column(Time, default=time(8, 0))
    send_window_end: Mapped[time | None] = mapped_column(Time, default=time(17, 0))

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="steps")
    template: Mapped["EmailTemplate"] = relationship("EmailTemplate")  # noqa: F821

    def __repr__(self) -> str:
        return f"<CampaignStep order={self.step_order} campaign={self.campaign_id}>"


class CampaignEnrollment(Base):
    __tablename__ = "campaign_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, name="enrollment_status", native_enum=False),
        nullable=False,
        default=EnrollmentStatus.ACTIVE,
    )
    current_step_order: Mapped[int] = mapped_column(Integer, default=1)
    next_send_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="enrollments")
    contact: Mapped["Contact"] = relationship("Contact", back_populates="enrollments")  # noqa: F821
    messages: Mapped[list["EmailMessage"]] = relationship(  # noqa: F821
        "EmailMessage", back_populates="enrollment"
    )

    def __repr__(self) -> str:
        return f"<CampaignEnrollment contact={self.contact_id} step={self.current_step_order}>"
