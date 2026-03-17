"""Scraping pipeline orchestration.

Ties together state scrapers, NCES matching, deduplication, email verification,
and database storage into a single ``run_pipeline`` entry point.

Usage::

    # Run all states
    await run_pipeline()

    # Run specific states only
    await run_pipeline(state_codes=["FL", "CA"])
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from scrapers.base import NormalizedContact
from scrapers.states import SCRAPERS
from scrapers.utils import fuzzy_match_district, normalize_district_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NCES matching
# ---------------------------------------------------------------------------


def match_to_nces(
    contact: NormalizedContact,
    districts: list[dict[str, Any]],
    *,
    threshold: float = 85.0,
) -> str | None:
    """Fuzzy-match a contact's district name to an NCES district.

    Parameters
    ----------
    contact : NormalizedContact
        The contact whose ``district_name`` we want to match.
    districts : list[dict]
        List of dicts with at least ``nces_id`` and ``name`` keys,
        typically loaded from the ``districts`` table.

    Returns
    -------
    str | None
        The matched NCES ID, or None if no match meets the threshold.
    """
    if not districts:
        return None

    # Build lookup: normalized_name -> nces_id
    name_to_id: dict[str, str] = {}
    candidate_names: list[str] = []
    for d in districts:
        name = d.get("name", "")
        nces_id = d.get("nces_id", "")
        if name and nces_id:
            norm = normalize_district_name(name)
            name_to_id[norm] = nces_id
            candidate_names.append(norm)

    query = normalize_district_name(contact.district_name)
    result = fuzzy_match_district(query, candidate_names, threshold=threshold)

    if result is None:
        return None

    matched_name, score = result
    nces_id = name_to_id.get(matched_name)
    if nces_id:
        logger.debug(
            "Matched '%s' -> '%s' (score=%.1f, nces_id=%s)",
            contact.district_name,
            matched_name,
            score,
            nces_id,
        )
    return nces_id


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate(
    contacts: list[NormalizedContact],
) -> list[NormalizedContact]:
    """Deduplicate contacts, keeping the highest-confidence record per district.

    Groups contacts by ``nces_id`` (when available) or by
    ``(state, normalized_district_name)`` as a fallback.  Within each group
    the record with the highest ``confidence_score`` wins.
    """
    groups: dict[str, list[NormalizedContact]] = defaultdict(list)

    for c in contacts:
        if c.nces_id:
            key = f"nces:{c.nces_id}"
        else:
            key = f"name:{c.state}:{normalize_district_name(c.district_name)}"
        groups[key].append(c)

    deduped: list[NormalizedContact] = []
    for key, group in groups.items():
        best = max(group, key=lambda c: c.confidence_score)

        # Merge in any extra data from lower-confidence duplicates
        for other in group:
            if other is best:
                continue
            if not best.email and other.email:
                best.email = other.email
            if not best.phone and other.phone:
                best.phone = other.phone

        deduped.append(best)

    logger.info(
        "Deduplication: %d contacts -> %d unique",
        len(contacts),
        len(deduped),
    )
    return deduped


# ---------------------------------------------------------------------------
# Database storage
# ---------------------------------------------------------------------------


async def store_contacts(
    contacts: list[NormalizedContact],
    db_session: Any,
) -> int:
    """Upsert normalized contacts and their sources into the database.

    Uses ``(nces_id, last_name, first_name)`` or ``(state, district_name,
    last_name)`` as the dedup key depending on whether nces_id is set.

    Returns the number of rows written.
    """
    from sqlalchemy import text

    upsert_contact_sql = text("""
        INSERT INTO contacts (
            nces_id, district_name, state, first_name, last_name,
            prefix, suffix, email, phone, role, confidence_score
        ) VALUES (
            :nces_id, :district_name, :state, :first_name, :last_name,
            :prefix, :suffix, :email, :phone, :role, :confidence_score
        )
        ON CONFLICT (nces_id, last_name, first_name)
        WHERE nces_id IS NOT NULL
        DO UPDATE SET
            email = COALESCE(EXCLUDED.email, contacts.email),
            phone = COALESCE(EXCLUDED.phone, contacts.phone),
            confidence_score = GREATEST(EXCLUDED.confidence_score, contacts.confidence_score),
            updated_at = NOW()
        RETURNING id
    """)

    upsert_source_sql = text("""
        INSERT INTO contact_sources (contact_id, source, scraped_at)
        VALUES (:contact_id, :source, :scraped_at)
        ON CONFLICT (contact_id, source) DO UPDATE SET
            scraped_at = EXCLUDED.scraped_at
    """)

    count = 0
    for contact in contacts:
        try:
            result = await db_session.execute(
                upsert_contact_sql,
                {
                    "nces_id": contact.nces_id,
                    "district_name": contact.district_name,
                    "state": contact.state,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "prefix": contact.prefix,
                    "suffix": contact.suffix,
                    "email": contact.email,
                    "phone": contact.phone,
                    "role": contact.role,
                    "confidence_score": contact.confidence_score,
                },
            )
            row = result.fetchone()
            contact_id = row[0] if row else None

            if contact_id:
                await db_session.execute(
                    upsert_source_sql,
                    {
                        "contact_id": contact_id,
                        "source": contact.source,
                        "scraped_at": contact.scraped_at,
                    },
                )
            count += 1
        except Exception:
            logger.exception(
                "Failed to store contact: %s %s (%s)",
                contact.first_name,
                contact.last_name,
                contact.district_name,
            )

    await db_session.commit()
    logger.info("Stored %d contacts", count)
    return count


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(
    state_codes: list[str] | None = None,
    *,
    db_session: Any | None = None,
    districts: list[dict[str, Any]] | None = None,
    verify_emails: bool = False,
) -> list[NormalizedContact]:
    """Execute the full scraping pipeline.

    Steps:
        1. Run state scrapers (all or filtered by *state_codes*)
        2. Normalize raw contacts
        3. Match each contact to an NCES district
        4. Deduplicate across sources
        5. Optionally verify email addresses
        6. Optionally store to database

    Parameters
    ----------
    state_codes : list[str] | None
        Two-letter state codes to scrape.  ``None`` means all registered scrapers.
    db_session : AsyncSession | None
        SQLAlchemy async session for storage.  If None, results are returned
        but not persisted.
    districts : list[dict] | None
        Pre-loaded NCES districts for matching.  If None and *db_session* is
        provided, districts are loaded from the database.
    verify_emails : bool
        If True, run Mailgun email verification on all contacts with emails.

    Returns
    -------
    list[NormalizedContact]
        The final deduplicated contacts.
    """
    start = datetime.now(timezone.utc)
    logger.info("Pipeline starting at %s", start.isoformat())

    # 1. Determine which scrapers to run
    codes = [c.upper() for c in state_codes] if state_codes else list(SCRAPERS.keys())
    scrapers_to_run = {code: SCRAPERS[code] for code in codes if code in SCRAPERS}

    if not scrapers_to_run:
        logger.warning("No scrapers matched state_codes=%s", state_codes)
        return []

    logger.info("Running scrapers for: %s", ", ".join(scrapers_to_run.keys()))

    # 2. Scrape all states concurrently
    all_contacts: list[NormalizedContact] = []

    async def _run_scraper(code: str, scraper_cls: type) -> list[NormalizedContact]:
        try:
            scraper = scraper_cls()
            return await scraper.run()
        except Exception:
            logger.exception("Scraper for %s failed", code)
            return []

    tasks = [_run_scraper(code, cls) for code, cls in scrapers_to_run.items()]
    results = await asyncio.gather(*tasks)

    for result_list in results:
        all_contacts.extend(result_list)

    logger.info("Collected %d total contacts across %d states", len(all_contacts), len(codes))

    # 3. Match to NCES districts
    if districts is None and db_session is not None:
        from sqlalchemy import text

        result = await db_session.execute(
            text("SELECT nces_id, name, state FROM districts")
        )
        districts = [dict(row._mapping) for row in result.fetchall()]

    if districts:
        for contact in all_contacts:
            # Filter candidates to same state for efficiency
            state_districts = [d for d in districts if d.get("state") == contact.state]
            nces_id = match_to_nces(contact, state_districts)
            if nces_id:
                contact.nces_id = nces_id
        matched = sum(1 for c in all_contacts if c.nces_id)
        logger.info("NCES matching: %d/%d contacts matched", matched, len(all_contacts))

    # 4. Deduplicate
    deduped = deduplicate(all_contacts)

    # 5. Email verification (optional)
    if verify_emails:
        from scrapers.enrichment.email_verifier import bulk_verify

        emails_to_check = [c.email for c in deduped if c.email]
        if emails_to_check:
            logger.info("Verifying %d email addresses", len(emails_to_check))
            results = await bulk_verify(emails_to_check)

            # Build lookup of verification results
            verification_map = {r.email: r for r in results}

            for contact in deduped:
                if contact.email and contact.email in verification_map:
                    vr = verification_map[contact.email]
                    if not vr.is_valid:
                        logger.info(
                            "Marking invalid email for %s %s: %s (%s)",
                            contact.first_name,
                            contact.last_name,
                            contact.email,
                            vr.reason,
                        )
                        # Downgrade confidence but keep the email for reference
                        contact.confidence_score = max(contact.confidence_score - 20, 0)
                    if vr.did_you_mean:
                        logger.info(
                            "Email suggestion for %s: %s -> %s",
                            contact.email,
                            contact.email,
                            vr.did_you_mean,
                        )

    # 6. Store to database
    if db_session is not None:
        await store_contacts(deduped, db_session)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        "Pipeline complete: %d contacts in %.1fs",
        len(deduped),
        elapsed,
    )
    return deduped
