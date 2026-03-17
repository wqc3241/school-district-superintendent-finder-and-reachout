"""District business logic service."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.district import District
from app.schemas.district import DistrictCreate, DistrictUpdate


class DistrictService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: DistrictCreate) -> District:
        district = District(
            nces_id=data.nces_id,
            name=data.name,
            state=data.state.upper(),
            address=data.address,
            city=data.city,
            zip_code=data.zip_code,
            phone=data.phone,
            website=data.website,
            esl_program_status=data.esl_program_status,
            ell_student_count=data.ell_student_count,
            ell_percentage=data.ell_percentage,
            title_iii_allocation=data.title_iii_allocation,
            title_i_status=data.title_i_status,
            title_i_allocation=data.title_i_allocation,
            metadata_=data.metadata_,
        )
        self.db.add(district)
        await self.db.flush()
        await self.db.refresh(district)
        return district

    async def get_by_id(self, district_id: uuid.UUID) -> District | None:
        stmt = select(District).where(District.id == district_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_nces_id(self, nces_id: str) -> District | None:
        stmt = select(District).where(District.nces_id == nces_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 50,
        state: str | None = None,
        query: str | None = None,
        esl_only: bool = False,
        title_i_only: bool = False,
        funding_type: str | None = None,
    ) -> tuple[list[District], int]:
        stmt = select(District)
        count_stmt = select(func.count()).select_from(District)

        if state:
            stmt = stmt.where(District.state == state.upper())
            count_stmt = count_stmt.where(District.state == state.upper())

        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(District.name.ilike(pattern))
            count_stmt = count_stmt.where(District.name.ilike(pattern))

        if esl_only:
            stmt = stmt.where(District.esl_program_status.is_(True))
            count_stmt = count_stmt.where(District.esl_program_status.is_(True))

        if title_i_only:
            stmt = stmt.where(District.title_i_status.is_(True))
            count_stmt = count_stmt.where(District.title_i_status.is_(True))

        if funding_type == "title_i":
            # Title I ONLY — exclude districts that also have Title III
            stmt = stmt.where(
                District.title_i_status.is_(True),
                District.esl_program_status.isnot(True),
            )
            count_stmt = count_stmt.where(
                District.title_i_status.is_(True),
                District.esl_program_status.isnot(True),
            )
        elif funding_type == "title_iii":
            # Title III ONLY — exclude districts that also have Title I
            stmt = stmt.where(
                District.esl_program_status.is_(True),
                District.title_i_status.isnot(True),
            )
            count_stmt = count_stmt.where(
                District.esl_program_status.is_(True),
                District.title_i_status.isnot(True),
            )
        elif funding_type == "both":
            stmt = stmt.where(
                District.title_i_status.is_(True),
                District.esl_program_status.is_(True),
            )
            count_stmt = count_stmt.where(
                District.title_i_status.is_(True),
                District.esl_program_status.is_(True),
            )

        # Get total count
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        # Get page of results
        offset = (page - 1) * size
        stmt = stmt.order_by(District.name).offset(offset).limit(size)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, district_id: uuid.UUID, data: DistrictUpdate) -> District | None:
        district = await self.get_by_id(district_id)
        if not district:
            return None

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "state" and value:
                value = value.upper()
            setattr(district, field, value)

        await self.db.flush()
        await self.db.refresh(district)
        return district

    async def delete(self, district_id: uuid.UUID) -> bool:
        district = await self.get_by_id(district_id)
        if not district:
            return False
        await self.db.delete(district)
        await self.db.flush()
        return True
