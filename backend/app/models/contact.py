"""Contact model representing a person at a school district."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class ContactRole(str, enum.Enum):
    SUPERINTENDENT = "superintendent"
    ASST_SUPERINTENDENT = "asst_superintendent"
    ESL_DIRECTOR = "esl_director"
    OTHER = "other"


class EmailStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VALID = "valid"
    INVALID = "invalid"
    RISKY = "risky"
    UNKNOWN = "unknown"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="superintendent",
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str | None] = mapped_column(String(20))
    suffix: Mapped[str | None] = mapped_column(String(20))

    email: Mapped[str | None] = mapped_column(String(255), index=True)
    email_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unverified",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    phone: Mapped[str | None] = mapped_column(String(20))
    confidence_score: Mapped[int] = mapped_column(Integer, default=0)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    district: Mapped["District"] = relationship(  # noqa: F821
        "District", back_populates="contacts"
    )
    sources: Mapped[list["ContactSource"]] = relationship(  # noqa: F821
        "ContactSource", back_populates="contact", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list["CampaignEnrollment"]] = relationship(  # noqa: F821
        "CampaignEnrollment", back_populates="contact"
    )

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.prefix, self.first_name, self.last_name, self.suffix) if p]
        return " ".join(parts)

    def __repr__(self) -> str:
        return f"<Contact {self.full_name} ({self.role.value})>"
