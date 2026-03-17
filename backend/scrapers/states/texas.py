"""Texas Education Agency (TEA) superintendent directory scraper.

Source: https://tea.texas.gov/texas-schools/general-information/school-district-locator

TEA provides an AskTED directory with superintendent contact info. The
directory is searchable at https://tea4avholly.tea.state.tx.us/tea.askted.web/Forms/Home.aspx
and also provides a downloadable district directory.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

from scrapers.base import RawContact
from scrapers.states.base_state import BaseStateScraper

logger = logging.getLogger(__name__)

# AskTED directory download — CSV of all district contacts
_TEA_DIRECTORY_URL = (
    "https://tea4avholly.tea.state.tx.us/tea.askted.web/Forms/"
    "DownloadFile.aspx?type=SuperintendentsByDistrict"
)

# Fallback: scrape the HTML district locator page
_TEA_LOCATOR_URL = (
    "https://tea.texas.gov/texas-schools/general-information/"
    "school-district-locator"
)


class TexasScraper(BaseStateScraper):
    state_code = "TX"
    source_name = "texas_tea"
    source_url = _TEA_LOCATOR_URL

    async def scrape(self) -> list[RawContact]:
        client = await self._get_client()
        contacts: list[RawContact] = []

        # Strategy 1: try AskTED CSV download
        try:
            contacts = await self._scrape_askted_csv(client)
            if contacts:
                return contacts
        except Exception as exc:
            logger.info("AskTED CSV download failed (%s), falling back to HTML", exc)

        # Strategy 2: scrape the TEA locator HTML page
        contacts = await self._scrape_locator_html(client)
        return contacts

    async def _scrape_askted_csv(self, client: object) -> list[RawContact]:
        """Download and parse the AskTED superintendent CSV."""
        import csv
        import io

        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)

        resp = await client.get(_TEA_DIRECTORY_URL)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        contacts: list[RawContact] = []

        for row in reader:
            district = (
                row.get("District Name")
                or row.get("DISTRICT NAME")
                or row.get("Organization Name")
                or ""
            ).strip()

            name = (
                row.get("Superintendent Name")
                or row.get("SUPERINTENDENT NAME")
                or row.get("First Name", "")
                + " "
                + row.get("Last Name", "")
            ).strip()

            if not district or not name:
                continue

            email = (
                row.get("Email")
                or row.get("EMAIL")
                or row.get("Superintendent Email")
                or ""
            ).strip() or None

            phone = (
                row.get("Phone")
                or row.get("PHONE")
                or row.get("Superintendent Phone")
                or ""
            ).strip() or None

            street = (row.get("Address") or row.get("ADDRESS") or "").strip()
            city = (row.get("City") or row.get("CITY") or "").strip()
            state = (row.get("State") or "TX").strip()
            zip_code = (row.get("Zip") or row.get("ZIP") or "").strip()
            address = ", ".join(filter(None, [street, city, state, zip_code])) or None

            contacts.append(
                RawContact(
                    district_name=district,
                    state="TX",
                    superintendent_name=name,
                    email=email,
                    phone=phone,
                    address=address,
                    raw_data={
                        "district_id": (
                            row.get("District Number")
                            or row.get("DISTRICT NUMBER")
                            or ""
                        ).strip(),
                        "source": "askted_csv",
                        "source_url": _TEA_DIRECTORY_URL,
                    },
                )
            )

        logger.info("Parsed %d Texas contacts from AskTED CSV", len(contacts))
        return contacts

    async def _scrape_locator_html(self, client: object) -> list[RawContact]:
        """Fallback: scrape the TEA HTML locator page."""
        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)

        resp = await client.get(_TEA_LOCATOR_URL)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        contacts: list[RawContact] = []

        # Look for a table or structured listing
        table = self._find_data_table(soup)
        if table is None:
            logger.warning("No district table found on TEA locator page")
            return contacts

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            district = self._clean(cells[0])
            name = self._clean(cells[1])

            if not district or not name:
                continue
            if "district" in district.lower() and "superintendent" in name.lower():
                continue

            email = self._extract_email(cells[-1]) if cells else None
            phone = self._extract_phone(cells) if len(cells) > 2 else None
            address = self._clean(cells[2]) if len(cells) > 2 else None

            contacts.append(
                RawContact(
                    district_name=district,
                    state="TX",
                    superintendent_name=name,
                    email=email,
                    phone=phone,
                    address=address,
                    raw_data={"source": "tea_locator", "source_url": _TEA_LOCATOR_URL},
                )
            )

        logger.info("Parsed %d Texas contacts from HTML", len(contacts))
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
    def _extract_phone(cells: list[Tag]) -> str | None:
        for cell in cells:
            text = cell.get_text(strip=True)
            match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", text)
            if match:
                return match.group(0)
        return None
