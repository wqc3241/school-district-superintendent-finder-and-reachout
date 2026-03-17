"""Illinois State Board of Education (ISBE) superintendent directory scraper.

Source: https://www.isbe.net/Pages/Superintendent-Directory.aspx

ISBE publishes a superintendent directory that can be scraped from their
website.  They also offer a downloadable spreadsheet through their data
portal.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from scrapers.base import RawContact
from scrapers.states.base_state import BaseStateScraper

logger = logging.getLogger(__name__)

_ISBE_DIRECTORY_URL = (
    "https://www.isbe.net/Pages/Superintendent-Directory.aspx"
)

# ISBE may also expose a downloadable Excel/CSV from their data portal.
_ISBE_DATA_PORTAL_URL = (
    "https://www.isbe.net/Pages/Illinois-State-Board-of-Education-Data.aspx"
)


class IllinoisScraper(BaseStateScraper):
    state_code = "IL"
    source_name = "illinois_isbe"
    source_url = _ISBE_DIRECTORY_URL

    async def scrape(self) -> list[RawContact]:
        client = await self._get_client()
        resp = await client.get(self.source_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        contacts: list[RawContact] = []

        # Try table-based parsing first
        contacts = self._parse_table(soup)
        if not contacts:
            contacts = self._parse_list_items(soup)
        if not contacts:
            contacts = self._parse_generic_blocks(soup)

        logger.info("Parsed %d Illinois superintendent records", len(contacts))
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
        """Parse a single table row into a RawContact."""
        try:
            district = self._clean(cells[0])
            name = self._clean(cells[1])

            if not district or not name:
                return None
            if self._is_header(district, name):
                return None

            address = self._clean(cells[2]) if len(cells) > 2 else None
            phone = self._extract_phone_from_cells(cells)
            email = self._extract_email_from_cells(cells)

            return RawContact(
                district_name=district,
                state="IL",
                superintendent_name=name,
                email=email,
                phone=phone,
                address=address,
                raw_data={"source_url": self.source_url},
            )
        except (IndexError, AttributeError):
            return None

    # -- List-item parsing ---------------------------------------------------

    def _parse_list_items(self, soup: BeautifulSoup) -> list[RawContact]:
        """Parse from definition lists or structured list items.

        Some ISBE pages use dl/dt/dd structures for the directory.
        """
        contacts: list[RawContact] = []

        # Look for definition lists
        for dl in soup.find_all("dl"):
            terms = dl.find_all("dt")
            defs = dl.find_all("dd")

            for dt, dd in zip(terms, defs):
                district = self._clean(dt)
                text = dd.get_text(separator="\n")
                lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

                if not district or not lines:
                    continue

                name = lines[0]
                email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
                phone_match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)

                address_parts = [
                    ln for ln in lines[1:]
                    if not re.search(r"[\w.+-]+@[\w.-]+\.\w+", ln)
                    and not re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", ln)
                ]

                contacts.append(
                    RawContact(
                        district_name=district,
                        state="IL",
                        superintendent_name=name,
                        email=email_match.group(0) if email_match else None,
                        phone=phone_match.group(0) if phone_match else None,
                        address=", ".join(address_parts[:2]) or None,
                        raw_data={"source_url": self.source_url, "parse_method": "dl"},
                    )
                )

        return contacts

    # -- Generic block parsing (last resort) ---------------------------------

    def _parse_generic_blocks(self, soup: BeautifulSoup) -> list[RawContact]:
        """Parse from generic content blocks as a last resort."""
        contacts: list[RawContact] = []

        # Look for the main content area
        content = soup.find("div", id=re.compile(r"content|main", re.I))
        if content is None:
            content = soup.find("main") or soup.body
        if content is None:
            return contacts

        # Look for repeated blocks
        blocks = content.find_all(
            "div",
            class_=re.compile(r"row|card|item|entry|district", re.I),
        )

        for block in blocks:
            text = block.get_text(separator="\n")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            if len(lines) < 2:
                continue

            district = lines[0]
            name = lines[1]

            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
            phone_match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)

            if district and name and len(name.split()) >= 2:
                contacts.append(
                    RawContact(
                        district_name=district,
                        state="IL",
                        superintendent_name=name,
                        email=email_match.group(0) if email_match else None,
                        phone=phone_match.group(0) if phone_match else None,
                        address=None,
                        raw_data={
                            "source_url": self.source_url,
                            "parse_method": "generic_block",
                        },
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
    def _extract_email_from_cells(cells: list[Tag]) -> str | None:
        for cell in cells:
            mailto = cell.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
            if mailto:
                href = mailto.get("href", "")
                if isinstance(href, list):
                    href = href[0]
                return href.replace("mailto:", "").strip()
            text = cell.get_text(strip=True)
            match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _extract_phone_from_cells(cells: list[Tag]) -> str | None:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)
            if match:
                return match.group(0)
        return None
