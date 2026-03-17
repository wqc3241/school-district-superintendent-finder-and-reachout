"""Florida DOE superintendent directory scraper.

Source: https://www.fldoe.org/accountability/data-sys/school-dis-data/superintendents.stml

The page contains an HTML table with columns:
District | Superintendent | Address | Phone | Fax | Email
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from scrapers.base import RawContact
from scrapers.states.base_state import BaseStateScraper

logger = logging.getLogger(__name__)


class FloridaScraper(BaseStateScraper):
    state_code = "FL"
    source_name = "florida_doe"
    source_url = (
        "https://www.fldoe.org/accountability/data-sys/"
        "school-dis-data/superintendents.stml"
    )

    async def scrape(self) -> list[RawContact]:
        client = await self._get_client()
        resp = await client.get(self.source_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        contacts: list[RawContact] = []

        # The superintendent listing is in a table; find the main data table.
        table = self._find_data_table(soup)
        if table is None:
            logger.warning("Could not find superintendent table on FL DOE page")
            return contacts

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            record = self._parse_row(cells)
            if record:
                contacts.append(record)

        logger.info("Parsed %d Florida superintendent records", len(contacts))
        return contacts

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _find_data_table(soup: BeautifulSoup) -> Tag | None:
        """Locate the main data table on the page.

        The page structure may include multiple tables; we look for one with
        header-like content mentioning 'superintendent' or 'district'.
        """
        for table in soup.find_all("table"):
            text = table.get_text(separator=" ").lower()
            if "superintendent" in text and "district" in text:
                return table
        # Fallback: return the largest table on the page
        tables = soup.find_all("table")
        if tables:
            return max(tables, key=lambda t: len(t.find_all("tr")))
        return None

    @staticmethod
    def _extract_email(cell: Tag) -> str | None:
        """Extract email from a cell, checking mailto links first."""
        mailto = cell.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
        if mailto:
            href = mailto.get("href", "")
            if isinstance(href, list):
                href = href[0]
            return href.replace("mailto:", "").strip()
        # Fallback: look for email-like text
        text = cell.get_text(strip=True)
        match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        return match.group(0) if match else None

    @staticmethod
    def _clean_text(cell: Tag) -> str:
        """Get cleaned text from a table cell."""
        return " ".join(cell.get_text(separator=" ").split()).strip()

    def _parse_row(self, cells: list[Tag]) -> RawContact | None:
        """Parse a table row into a RawContact.

        Expected columns (order may vary):
        0: District name
        1: Superintendent name
        2: Address (may span multiple lines)
        3: Phone
        4: Fax (ignored)
        5: Email
        """
        try:
            district = self._clean_text(cells[0])
            name = self._clean_text(cells[1])

            if not district or not name:
                return None

            # Skip header rows
            if "district" in district.lower() and "superintendent" in name.lower():
                return None

            address = self._clean_text(cells[2]) if len(cells) > 2 else None
            phone = self._clean_text(cells[3]) if len(cells) > 3 else None
            # cells[4] is fax — skip
            email = self._extract_email(cells[5]) if len(cells) > 5 else None

            return RawContact(
                district_name=district,
                state="FL",
                superintendent_name=name,
                email=email,
                phone=phone,
                address=address,
                raw_data={
                    "fax": self._clean_text(cells[4]) if len(cells) > 4 else None,
                    "source_url": self.source_url,
                },
            )
        except (IndexError, AttributeError) as exc:
            logger.debug("Skipping unparseable row: %s", exc)
            return None
