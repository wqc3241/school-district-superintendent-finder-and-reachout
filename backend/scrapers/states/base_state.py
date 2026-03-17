"""Abstract base class for state DOE superintendent scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT, NormalizedContact, RawContact
from scrapers.utils import parse_name, standardize_address, standardize_phone

logger = logging.getLogger(__name__)


class BaseStateScraper(ABC):
    """Base class that all state DOE scrapers inherit from.

    Subclasses must set the class-level attributes and implement ``scrape``.
    The ``run`` method calls ``scrape`` then normalizes every record.
    """

    state_code: str = ""
    source_name: str = ""
    source_url: str = ""

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- Interface -----------------------------------------------------------

    @abstractmethod
    async def scrape(self) -> list[RawContact]:
        """Scrape raw superintendent contacts from the state DOE site."""
        ...

    # -- Normalization -------------------------------------------------------

    def normalize(self, raw: RawContact) -> NormalizedContact:
        """Convert a RawContact into a NormalizedContact with parsed fields."""
        parsed = parse_name(raw.superintendent_name)

        return NormalizedContact(
            nces_id=None,  # filled later by pipeline matching
            district_name=raw.district_name.strip(),
            state=raw.state.upper(),
            first_name=parsed.get("first") or "",
            last_name=parsed.get("last") or "",
            prefix=parsed.get("prefix"),
            suffix=parsed.get("suffix"),
            email=raw.email.strip().lower() if raw.email else None,
            phone=standardize_phone(raw.phone),
            role="superintendent",
            source=self.source_name,
            confidence_score=self._compute_confidence(raw),
            scraped_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _compute_confidence(raw: RawContact) -> int:
        """Heuristic confidence score (0-100) based on data completeness."""
        score = 50  # base score for having a name + district
        if raw.email:
            score += 20
        if raw.phone:
            score += 10
        if raw.address:
            score += 10
        if raw.superintendent_name and len(raw.superintendent_name.split()) >= 2:
            score += 10
        return min(score, 100)

    # -- Run -----------------------------------------------------------------

    async def run(self) -> list[NormalizedContact]:
        """Scrape and normalize all contacts."""
        logger.info(
            "Starting %s scraper for %s", self.source_name, self.state_code
        )
        try:
            raw = await self.scrape()
            logger.info("Scraped %d raw contacts from %s", len(raw), self.source_name)
            normalized = [self.normalize(r) for r in raw]
            return normalized
        finally:
            await self.close()
