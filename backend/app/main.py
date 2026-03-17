"""FastAPI application entry point with all routers registered."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import traceback
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session as get_db

from app.api.campaigns import router as campaigns_router
from app.api.contacts import router as contacts_router
from app.api.districts import router as districts_router
from app.api.webhooks import router as webhooks_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting %s", settings.app_name)
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="School District Superintendent Finder & Outreach API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(districts_router, prefix="/api/v1")
app.include_router(contacts_router, prefix="/api/v1")
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/api/v1/dashboard/stats")
async def dashboard_stats(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Quick dashboard stats from real data."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT COUNT(*) FROM districts"))
    total_districts = result.scalar()
    result = await db.execute(text("SELECT COUNT(*) FROM districts WHERE esl_program_status = true"))
    esl_districts = result.scalar()
    result = await db.execute(text("SELECT COUNT(*) FROM districts WHERE title_i_status = true"))
    title_i_districts = result.scalar()
    result = await db.execute(text("SELECT COUNT(*) FROM contacts"))
    total_contacts = result.scalar()
    result = await db.execute(text("SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL"))
    contacts_with_email = result.scalar()
    result = await db.execute(text("SELECT COUNT(*) FROM campaigns WHERE status = 'active'"))
    active_campaigns = result.scalar()
    return {
        "totalDistricts": total_districts,
        "districtsWithEsl": esl_districts,
        "districtsWithTitleI": title_i_districts,
        "totalContacts": total_contacts,
        "verifiedContacts": contacts_with_email,
        "unverifiedContacts": total_contacts - contacts_with_email,
        "activeCampaigns": active_campaigns,
        "emailsSentToday": 0,
        "emailsSentThisWeek": 0,
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
