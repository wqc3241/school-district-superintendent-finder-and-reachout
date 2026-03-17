"""NCES Common Core of Data (CCD) LEA Universe Survey importer.

Downloads the CCD directory CSV from the NCES website, parses district
records, and upserts them into the local ``districts`` table.

CLI usage::

    python -m scrapers.nces.ccd_importer [--year 2022] [--csv /path/to/local.csv]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CCD CSV column mapping (2022-23 layout — column names are stable across years)
# ---------------------------------------------------------------------------

# These are the columns we care about from the LEA Universe file.
_COLUMN_MAP: dict[str, str] = {
    "LEAID": "nces_id",
    "LEA_NAME": "name",
    "LSTATE": "state",
    "LSTREET1": "address_street",
    "LCITY": "city",
    "LZIP": "zip_code",
    "PHONE": "phone",
    "LOCALE": "locale_code",
    "TOTAL": "total_students",
    "MEMBER": "total_students",       # fallback column name
    "LEP": "ell_count",
    "ELL": "ell_count",               # fallback column name
}

# The NCES file download URL pattern.  The directory ZIP typically lives at a
# URL like the one below.  In practice the exact URL changes each release year,
# so we allow the caller to override it.
DEFAULT_CCD_URL = (
    "https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2223_w_1a_080623.zip"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DistrictRecord:
    """Parsed district row ready for DB upsert."""

    nces_id: str
    name: str
    state: str
    address_street: str | None
    city: str | None
    zip_code: str | None
    phone: str | None
    locale_code: str | None
    total_students: int | None
    ell_count: int | None
    ell_percentage: float | None


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class CCDImporter:
    """Download, parse, and upsert NCES CCD LEA data."""

    def __init__(
        self,
        *,
        url: str = DEFAULT_CCD_URL,
        timeout: float = DEFAULT_TIMEOUT * 5,
    ) -> None:
        self.url = url
        self.timeout = timeout

    # -- Download ------------------------------------------------------------

    async def download(self, *, dest: Path | None = None) -> bytes:
        """Download the CCD ZIP file and return the raw bytes.

        If *dest* is given the file is also written to disk for caching.
        """
        logger.info("Downloading CCD data from %s", self.url)
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()

        data = resp.content
        logger.info("Downloaded %d bytes", len(data))

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            logger.info("Saved to %s", dest)

        return data

    # -- Parse ---------------------------------------------------------------

    @staticmethod
    def _extract_csv_from_zip(data: bytes) -> str:
        """Extract the first CSV file found inside a ZIP archive."""
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError("No CSV file found inside the ZIP archive")
            target = csv_names[0]
            logger.info("Extracting %s from ZIP", target)
            return zf.read(target).decode("utf-8-sig")

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """Convert a value to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(str(value).strip().replace(",", ""))
        except (ValueError, TypeError):
            return None

    def parse_csv(self, csv_text: str) -> list[DistrictRecord]:
        """Parse the CCD CSV text into a list of DistrictRecord objects."""
        reader = csv.DictReader(io.StringIO(csv_text))
        records: list[DistrictRecord] = []

        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        # Build a runtime map from actual header names to our field names
        field_lookup: dict[str, str] = {}
        for col in reader.fieldnames:
            col_upper = col.strip().upper()
            if col_upper in _COLUMN_MAP:
                field_lookup[col.strip()] = _COLUMN_MAP[col_upper]

        for row in reader:
            mapped: dict[str, Any] = {}
            for csv_col, field_name in field_lookup.items():
                val = row.get(csv_col, "").strip()
                mapped[field_name] = val if val else None

            nces_id = mapped.get("nces_id")
            name = mapped.get("name")
            state = mapped.get("state")

            if not nces_id or not name or not state:
                continue

            total_students = self._safe_int(mapped.get("total_students"))
            ell_count = self._safe_int(mapped.get("ell_count"))

            ell_percentage: float | None = None
            if total_students and total_students > 0 and ell_count is not None:
                ell_percentage = round((ell_count / total_students) * 100, 2)

            records.append(
                DistrictRecord(
                    nces_id=str(nces_id),
                    name=str(name),
                    state=str(state),
                    address_street=mapped.get("address_street"),
                    city=mapped.get("city"),
                    zip_code=mapped.get("zip_code"),
                    phone=mapped.get("phone"),
                    locale_code=mapped.get("locale_code"),
                    total_students=total_students,
                    ell_count=ell_count,
                    ell_percentage=ell_percentage,
                )
            )

        logger.info("Parsed %d district records from CCD CSV", len(records))
        return records

    # -- Load from local file ------------------------------------------------

    def parse_file(self, path: Path) -> list[DistrictRecord]:
        """Parse a local CCD CSV or ZIP file."""
        data = path.read_bytes()
        if path.suffix.lower() == ".zip":
            csv_text = self._extract_csv_from_zip(data)
        else:
            csv_text = data.decode("utf-8-sig")
        return self.parse_csv(csv_text)

    # -- DB upsert -----------------------------------------------------------

    async def upsert_districts(
        self,
        records: list[DistrictRecord],
        db_session: Any,
    ) -> int:
        """Upsert district records into the database.

        Uses ``nces_id`` as the natural key.  Returns the number of rows
        affected (inserted + updated).

        *db_session* should be an async SQLAlchemy ``AsyncSession``.
        """
        from sqlalchemy import text

        upsert_sql = text("""
            INSERT INTO districts (
                nces_id, name, state, address_street, city, zip_code,
                phone, locale_code, total_students, ell_count, ell_percentage
            ) VALUES (
                :nces_id, :name, :state, :address_street, :city, :zip_code,
                :phone, :locale_code, :total_students, :ell_count, :ell_percentage
            )
            ON CONFLICT (nces_id) DO UPDATE SET
                name = EXCLUDED.name,
                state = EXCLUDED.state,
                address_street = EXCLUDED.address_street,
                city = EXCLUDED.city,
                zip_code = EXCLUDED.zip_code,
                phone = EXCLUDED.phone,
                locale_code = EXCLUDED.locale_code,
                total_students = EXCLUDED.total_students,
                ell_count = EXCLUDED.ell_count,
                ell_percentage = EXCLUDED.ell_percentage,
                updated_at = NOW()
        """)

        count = 0
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            for rec in batch:
                await db_session.execute(
                    upsert_sql,
                    {
                        "nces_id": rec.nces_id,
                        "name": rec.name,
                        "state": rec.state,
                        "address_street": rec.address_street,
                        "city": rec.city,
                        "zip_code": rec.zip_code,
                        "phone": rec.phone,
                        "locale_code": rec.locale_code,
                        "total_students": rec.total_students,
                        "ell_count": rec.ell_count,
                        "ell_percentage": rec.ell_percentage,
                    },
                )
                count += 1
            await db_session.commit()
            logger.info("Upserted batch %d-%d", i, i + len(batch))

        logger.info("Upserted %d district records total", count)
        return count

    # -- Full run ------------------------------------------------------------

    async def run(
        self,
        *,
        csv_path: Path | None = None,
        db_session: Any | None = None,
    ) -> list[DistrictRecord]:
        """Full import: download (or read local) -> parse -> optionally upsert."""
        if csv_path:
            records = self.parse_file(csv_path)
        else:
            raw = await self.download()
            csv_text = self._extract_csv_from_zip(raw)
            records = self.parse_csv(csv_text)

        if db_session is not None:
            await self.upsert_districts(records, db_session)

        return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import NCES CCD LEA Universe Survey data",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CCD_URL,
        help="URL to the CCD ZIP file (default: %(default)s)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to a local CSV or ZIP file instead of downloading",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Survey year (currently informational only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only, do not write to database",
    )
    return parser


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args()

    importer = CCDImporter(url=args.url)
    records = await importer.run(csv_path=args.csv, db_session=None)

    print(f"Parsed {len(records)} district records")
    if records:
        sample = records[0]
        print(f"  Sample: {sample.nces_id} | {sample.name} | {sample.state}")
        print(f"          Students: {sample.total_students}, ELL%: {sample.ell_percentage}")


if __name__ == "__main__":
    asyncio.run(_main())
