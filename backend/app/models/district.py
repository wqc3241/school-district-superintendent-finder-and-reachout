"""District model representing a school district from NCES data."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nces_id: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    website: Mapped[str | None] = mapped_column(Text)

    # ESL / ELL fields
    esl_program_status: Mapped[bool | None] = mapped_column(Boolean, default=False)
    ell_student_count: Mapped[int | None] = mapped_column(Integer)
    ell_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    title_iii_allocation: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    # Title I fields
    title_i_status: Mapped[bool | None] = mapped_column(Boolean, default=False)
    title_i_allocation: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        "Contact", back_populates="district", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<District {self.nces_id} - {self.name}, {self.state}>"
