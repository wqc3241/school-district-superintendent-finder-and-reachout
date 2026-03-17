"""SQLAlchemy models package."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Import all models so Alembic can discover them.
from app.models.campaign import Campaign, CampaignEnrollment, CampaignStep  # noqa: E402, F401
from app.models.contact import Contact  # noqa: E402, F401
from app.models.contact_source import ContactSource  # noqa: E402, F401
from app.models.district import District  # noqa: E402, F401
from app.models.email import EmailEvent, EmailMessage, EmailTemplate  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
