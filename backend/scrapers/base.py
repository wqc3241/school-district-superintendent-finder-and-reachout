"""Base spider / adapter interface for all data scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 60.0
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SuperintendentFinder/1.0; "
        "+https://github.com/superintendent-finder)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# Core dataclasses shared across the pipeline
# ---------------------------------------------------------------------------


@dataclass
class RawContact:
    """Unprocessed contact record straight from a scraper."""

    district_name: str
    state: str
    superintendent_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedContact:
    """Cleaned, parsed contact ready for matching and storage."""

    nces_id: str | None
    district_name: str
    state: str
    first_name: str
    last_name: str
    prefix: str | None
    suffix: str | None
    email: str | None
    phone: str | None
    role: str  # "superintendent", "interim superintendent", etc.
    source: str  # e.g. "florida_doe", "nces_ccd"
    confidence_score: int  # 0-100
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Base spider
# ---------------------------------------------------------------------------


class BaseSpider(ABC):
    """Abstract base for every data source adapter.

    Subclasses must implement ``fetch`` which returns raw records.
    The ``run`` convenience method adds logging and timing.
    """

    name: str = "base"

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # -- HTTP helpers --------------------------------------------------------

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
    async def fetch(self) -> list[RawContact]:
        """Fetch raw contact records from the data source."""
        ...

    async def run(self) -> list[RawContact]:
        """Execute the spider with logging and cleanup."""
        logger.info("Spider %s starting", self.name)
        start = datetime.now(timezone.utc)
        try:
            results = await self.fetch()
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            logger.info(
                "Spider %s finished: %d records in %.1fs",
                self.name,
                len(results),
                elapsed,
            )
            return results
        except Exception:
            logger.exception("Spider %s failed", self.name)
            raise
        finally:
            await self.close()
