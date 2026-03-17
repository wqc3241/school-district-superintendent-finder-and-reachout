"""California CDE directory scraper.

Source: https://www.cde.ca.gov/ds/si/ds/pubschls.asp

The CDE provides a downloadable tab-delimited file of all public schools
and districts.  We filter for district-level records (``RecType == "District"``)
and extract administrator info.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile

from scrapers.base import RawContact
from scrapers.states.base_state import BaseStateScraper

logger = logging.getLogger(__name__)

# Direct download link for the public schools file (tab-delimited, zipped).
_CA_PUBSCHLS_URL = "https://www.cde.ca.gov/ds/si/ds/documents/pubschls.txt"
_CA_PUBSCHLS_ZIP_URL = "https://www.cde.ca.gov/ds/si/ds/documents/pubschls.zip"


class CaliforniaScraper(BaseStateScraper):
    state_code = "CA"
    source_name = "california_cde"
    source_url = "https://www.cde.ca.gov/ds/si/ds/pubschls.asp"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.download_url = _CA_PUBSCHLS_ZIP_URL

    async def scrape(self) -> list[RawContact]:
        client = await self._get_client()

        # Try the ZIP first, fall back to plain text
        text_content = await self._download_data(client)
        return self._parse_tab_file(text_content)

    async def _download_data(self, client: object) -> str:
        """Download the CDE data file, handling both ZIP and plain text."""
        from httpx import AsyncClient

        assert isinstance(client, AsyncClient)

        # Attempt ZIP download first
        try:
            resp = await client.get(_CA_PUBSCHLS_ZIP_URL)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = zf.namelist()
                txt_files = [n for n in names if n.lower().endswith(".txt")]
                target = txt_files[0] if txt_files else names[0]
                return zf.read(target).decode("utf-8-sig")
        except Exception:
            logger.info("ZIP download failed, trying plain text URL")

        # Fallback: plain text
        resp = await client.get(_CA_PUBSCHLS_URL)
        resp.raise_for_status()
        return resp.text

    def _parse_tab_file(self, text: str) -> list[RawContact]:
        """Parse the tab-delimited CDE public schools file.

        We only keep rows where the record type indicates a district
        (the ``RecType`` field) and where an administrator name is present.
        """
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        contacts: list[RawContact] = []

        if reader.fieldnames is None:
            logger.warning("CDE file has no header row")
            return contacts

        for row in reader:
            rec_type = (row.get("RecType") or row.get("Rec Type") or "").strip()

            # Only district-level records
            if rec_type.lower() not in ("district", "lea"):
                continue

            admin_name = (
                row.get("AdmFName1", "").strip()
                + " "
                + row.get("AdmLName1", "").strip()
            ).strip()

            if not admin_name:
                admin_name = (row.get("Administrator") or "").strip()

            district_name = (
                row.get("District") or row.get("DistrictName") or row.get("LEA") or ""
            ).strip()

            if not district_name or not admin_name:
                continue

            email = (row.get("AdmEmail1") or row.get("Email") or "").strip() or None
            phone = (row.get("Phone") or "").strip() or None

            street = (row.get("Street") or row.get("StreetAbr") or "").strip()
            city = (row.get("City") or "").strip()
            state = (row.get("State") or "CA").strip()
            zip_code = (row.get("Zip") or "").strip()
            address = ", ".join(filter(None, [street, city, state, zip_code])) or None

            nces_id = (row.get("NCESDist") or row.get("NCES_ID") or "").strip() or None

            contacts.append(
                RawContact(
                    district_name=district_name,
                    state="CA",
                    superintendent_name=admin_name,
                    email=email,
                    phone=phone,
                    address=address,
                    raw_data={
                        "nces_id": nces_id,
                        "rec_type": rec_type,
                        "county": (row.get("County") or "").strip(),
                        "source_url": self.source_url,
                    },
                )
            )

        logger.info("Parsed %d California district contacts", len(contacts))
        return contacts
