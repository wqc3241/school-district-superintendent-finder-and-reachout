"""New York State Education Department (NYSED) superintendent directory scraper.

Source: https://www.nysed.gov/information-reporting-services/superintendent-directory

NYSED provides a searchable superintendent directory.  We scrape the full
listing page, which renders an HTML table of all district superintendents.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from scrapers.base import RawContact
from scrapers.states.base_state import BaseStateScraper

logger = logging.getLogger(__name__)

_NYSED_DIRECTORY_URL = (
    "https://www.nysed.gov/information-reporting-services/"
    "superintendent-directory"
)

# NYSED also exposes a data download page that may provide a CSV.
_NYSED_DATA_URL = (
    "https://data.nysed.gov/downloads.php"
)


class NewYorkScraper(BaseStateScraper):
    state_code = "NY"
    source_name = "new_york_nysed"
    source_url = _NYSED_DIRECTORY_URL

    async def scrape(self) -> list[RawContact]:
        client = await self._get_client()
        resp = await client.get(self.source_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        contacts: list[RawContact] = []

        # NYSED renders the directory as a table or a series of div blocks.
        # Try table first, then structured divs.
        contacts = self._parse_table(soup)
        if not contacts:
            contacts = self._parse_structured_divs(soup)

        logger.info("Parsed %d New York superintendent records", len(contacts))
        return contacts

    # -- Table parsing -------------------------------------------------------

    def _parse_table(self, soup: BeautifulSoup) -> list[RawContact]:
        """Parse superintendent data from an HTML table."""
        table = self._find_data_table(soup)
        if table is None:
            return []

        contacts: list[RawContact] = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            record = self._parse_table_row(cells)
            if record:
                contacts.append(record)

        return contacts

    def _parse_table_row(self, cells: list[Tag]) -> RawContact | None:
        """Parse a single table row.

        Expected layout (varies):
        0: District Name
        1: Superintendent Name
        2: Address / City / Zip
        3: Phone
        4: Email
        """
        try:
            district = self._clean(cells[0])
            name = self._clean(cells[1])

            if not district or not name:
                return None
            if self._is_header(district, name):
                return None

            address = self._clean(cells[2]) if len(cells) > 2 else None
            phone = self._extract_phone_from_cells(cells) if len(cells) > 3 else None
            email = self._extract_email(cells[-1]) if cells else None

            return RawContact(
                district_name=district,
                state="NY",
                superintendent_name=name,
                email=email,
                phone=phone,
                address=address,
                raw_data={"source_url": self.source_url},
            )
        except (IndexError, AttributeError):
            return None

    # -- Structured div parsing (fallback) -----------------------------------

    def _parse_structured_divs(self, soup: BeautifulSoup) -> list[RawContact]:
        """Parse superintendent data from structured div elements.

        Some NYSED pages render contact cards as div blocks instead of tables.
        """
        contacts: list[RawContact] = []

        # Look for repeated card-like structures
        cards = soup.find_all("div", class_=re.compile(r"views-row|card|district", re.I))
        if not cards:
            # Try article or li elements
            cards = soup.find_all(["article", "li"], class_=re.compile(r"district|superintendent", re.I))

        for card in cards:
            text = card.get_text(separator="\n")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            if len(lines) < 2:
                continue

            district = lines[0]
            name = lines[1] if len(lines) > 1 else ""

            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
            phone_match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)

            # Collect remaining lines as address
            address_parts = [
                ln for ln in lines[2:]
                if not re.search(r"[\w.+-]+@[\w.-]+\.\w+", ln)
                and not re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", ln)
            ]
            address = ", ".join(address_parts[:3]) or None

            if district and name:
                contacts.append(
                    RawContact(
                        district_name=district,
                        state="NY",
                        superintendent_name=name,
                        email=email_match.group(0) if email_match else None,
                        phone=phone_match.group(0) if phone_match else None,
                        address=address,
                        raw_data={"source_url": self.source_url, "parse_method": "div"},
                    )
                )

        return contacts

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _find_data_table(soup: BeautifulSoup) -> Tag | None:
        for table in soup.find_all("table"):
            text = table.get_text(separator=" ").lower()
            if "superintendent" in text or "district" in text:
                return table
        tables = soup.find_all("table")
        return max(tables, key=lambda t: len(t.find_all("tr"))) if tables else None

    @staticmethod
    def _clean(cell: Tag) -> str:
        return " ".join(cell.get_text(separator=" ").split()).strip()

    @staticmethod
    def _is_header(district: str, name: str) -> bool:
        d_lower = district.lower()
        n_lower = name.lower()
        return ("district" in d_lower and "superintendent" in n_lower) or d_lower == "district"

    @staticmethod
    def _extract_email(cell: Tag) -> str | None:
        mailto = cell.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
        if mailto:
            href = mailto.get("href", "")
            if isinstance(href, list):
                href = href[0]
            return href.replace("mailto:", "").strip()
        text = cell.get_text(strip=True)
        match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone_from_cells(cells: list[Tag]) -> str | None:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)
            if match:
                return match.group(0)
        return None
