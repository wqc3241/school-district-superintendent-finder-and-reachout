"""Ed Data Express Title III funding data importer.

Downloads Title III allocation data, matches it to existing districts by
NCES ID, and updates their ``title_iii_allocation`` and ``esl_program_status``
fields.

CLI usage::

    python -m scrapers.nces.title_iii [--csv /path/to/local.csv]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

# The Ed Data Express Title III allocations page.  The actual downloadable CSV
# URL may change between fiscal years; this is a representative starting point.
DEFAULT_TITLE_III_URL = (
    "https://eddataexpress.ed.gov/download/data-library/"
    "title-iii-english-language-acquisition-state-grants.csv"
)


@dataclass
class TitleIIIRecord:
    """Single Title III allocation record."""

    nces_id: str
    district_name: str
    state: str
    allocation: float  # dollar amount
    fiscal_year: int | None


class TitleIIIImporter:
    """Download and import Title III allocation data."""

    def __init__(
        self,
        *,
        url: str = DEFAULT_TITLE_III_URL,
        timeout: float = DEFAULT_TIMEOUT * 3,
    ) -> None:
        self.url = url
        self.timeout = timeout

    # -- Download ------------------------------------------------------------

    async def download(self) -> str:
        """Download the Title III CSV and return its text content."""
        logger.info("Downloading Title III data from %s", self.url)
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        text = resp.text
        logger.info("Downloaded %d chars of Title III CSV", len(text))
        return text

    # -- Parse ---------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            cleaned = str(value).strip().replace(",", "").replace("$", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip().replace(",", ""))
        except (ValueError, TypeError):
            return None

    def parse_csv(self, csv_text: str) -> list[TitleIIIRecord]:
        """Parse Title III CSV text into records.

        The CSV layout varies; we look for columns that contain key terms
        to be resilient to minor naming changes between years.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        records: list[TitleIIIRecord] = []

        if reader.fieldnames is None:
            raise ValueError("Title III CSV has no header row")

        # Flexible column matching
        headers = {h.strip(): h for h in reader.fieldnames}
        header_upper = {h.strip().upper(): h for h in reader.fieldnames}

        def _find_col(*keywords: str) -> str | None:
            for key, orig in header_upper.items():
                if all(kw in key for kw in keywords):
                    return orig
            return None

        col_nces = _find_col("LEA", "ID") or _find_col("NCES") or _find_col("LEAID")
        col_name = _find_col("LEA", "NAME") or _find_col("DISTRICT")
        col_state = _find_col("STATE")
        col_alloc = _find_col("ALLOCATION") or _find_col("AMOUNT") or _find_col("TITLE III")
        col_year = _find_col("YEAR") or _find_col("FISCAL")

        if not col_nces:
            logger.warning("Could not identify NCES ID column in Title III CSV")
            return records

        for row in reader:
            nces_id = row.get(col_nces, "").strip() if col_nces else ""
            if not nces_id:
                continue

            name = row.get(col_name, "").strip() if col_name else ""
            state = row.get(col_state, "").strip() if col_state else ""
            allocation = self._safe_float(row.get(col_alloc)) if col_alloc else None
            fiscal_year = self._safe_int(row.get(col_year)) if col_year else None

            if allocation is None:
                continue

            records.append(
                TitleIIIRecord(
                    nces_id=nces_id,
                    district_name=name,
                    state=state,
                    allocation=allocation,
                    fiscal_year=fiscal_year,
                )
            )

        logger.info("Parsed %d Title III allocation records", len(records))
        return records

    def parse_file(self, path: Path) -> list[TitleIIIRecord]:
        """Parse a local CSV file."""
        text = path.read_text(encoding="utf-8-sig")
        return self.parse_csv(text)

    # -- DB update -----------------------------------------------------------

    async def update_districts(
        self,
        records: list[TitleIIIRecord],
        db_session: Any,
    ) -> int:
        """Update existing district rows with Title III data.

        Sets ``title_iii_allocation`` and ``esl_program_status = True`` for
        every district whose ``nces_id`` appears in *records*.
        """
        from sqlalchemy import text

        update_sql = text("""
            UPDATE districts
            SET title_iii_allocation = :allocation,
                esl_program_status = TRUE,
                updated_at = NOW()
            WHERE nces_id = :nces_id
        """)

        count = 0
        for rec in records:
            result = await db_session.execute(
                update_sql,
                {"nces_id": rec.nces_id, "allocation": rec.allocation},
            )
            if result.rowcount > 0:
                count += result.rowcount

        await db_session.commit()
        logger.info("Updated %d district rows with Title III data", count)
        return count

    # -- Full run ------------------------------------------------------------

    async def run(
        self,
        *,
        csv_path: Path | None = None,
        db_session: Any | None = None,
    ) -> list[TitleIIIRecord]:
        """Full import: download (or read local) -> parse -> optionally update DB."""
        if csv_path:
            records = self.parse_file(csv_path)
        else:
            csv_text = await self.download()
            records = self.parse_csv(csv_text)

        if db_session is not None:
            await self.update_districts(records, db_session)

        return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import Ed Data Express Title III allocation data",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_TITLE_III_URL,
        help="URL to the Title III CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to a local CSV file instead of downloading",
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

    importer = TitleIIIImporter(url=args.url)
    records = await importer.run(csv_path=args.csv, db_session=None)

    print(f"Parsed {len(records)} Title III records")
    if records:
        sample = records[0]
        print(f"  Sample: {sample.nces_id} | {sample.district_name} | ${sample.allocation:,.2f}")


if __name__ == "__main__":
    asyncio.run(_main())
