"""Contact enrichment via Hunter.io and Apollo.io APIs.

Provides functions to find email addresses and enrich contact data using
third-party intelligence APIs.  Requires environment variables:

- ``HUNTER_API_KEY`` for Hunter.io
- ``APOLLO_API_KEY`` for Apollo.io

Usage::

    email_data = await enrich_from_hunter("springfield.k12.us", "John Smith")
    contact_data = await enrich_from_apollo("John Smith", "Springfield Public Schools")
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from scrapers.base import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

_HUNTER_BASE_URL = "https://api.hunter.io/v2"
_APOLLO_BASE_URL = "https://api.apollo.io/v1"


# ---------------------------------------------------------------------------
# Hunter.io integration
# ---------------------------------------------------------------------------


def _get_hunter_key() -> str:
    key = os.environ.get("HUNTER_API_KEY", "")
    if not key:
        raise EnvironmentError("HUNTER_API_KEY environment variable is required")
    return key


async def enrich_from_hunter(
    domain: str,
    name: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any] | None:
    """Find an email address via Hunter.io email finder API.

    Parameters
    ----------
    domain : str
        The organization's domain (e.g., "springfield.k12.us").
    name : str
        Full name of the person to look up.

    Returns
    -------
    dict | None
        A dictionary with ``email``, ``score``, ``position``, ``sources``
        keys, or ``None`` if no result was found.
    """
    api_key = _get_hunter_key()

    # Split name into first/last for Hunter's API
    parts = name.strip().split()
    first_name = parts[0] if parts else ""
    last_name = parts[-1] if len(parts) > 1 else ""

    params: dict[str, str] = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": api_key,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{_HUNTER_BASE_URL}/email-finder", params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            email = data.get("email")
            if not email:
                logger.debug("Hunter.io: no email found for %s @ %s", name, domain)
                return None

            return {
                "email": email,
                "score": data.get("score", 0),
                "position": data.get("position"),
                "department": data.get("department"),
                "linkedin": data.get("linkedin"),
                "sources": [
                    {"domain": s.get("domain"), "uri": s.get("uri")}
                    for s in data.get("sources", [])
                ],
                "provider": "hunter.io",
            }

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Hunter.io API error for %s @ %s: HTTP %d",
                name,
                domain,
                exc.response.status_code,
            )
            return None
        except Exception as exc:
            logger.warning("Hunter.io error for %s @ %s: %s", name, domain, exc)
            return None


async def hunter_domain_search(
    domain: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Search for all email addresses at a domain via Hunter.io.

    Useful for discovering the email pattern used by a school district.
    """
    api_key = _get_hunter_key()

    params = {"domain": domain, "api_key": api_key, "limit": "20"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{_HUNTER_BASE_URL}/domain-search", params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})

            pattern = data.get("pattern")
            emails = data.get("emails", [])

            results: list[dict[str, Any]] = []
            for entry in emails:
                results.append({
                    "email": entry.get("value"),
                    "first_name": entry.get("first_name"),
                    "last_name": entry.get("last_name"),
                    "position": entry.get("position"),
                    "confidence": entry.get("confidence", 0),
                })

            if pattern:
                logger.info("Hunter.io: domain %s uses pattern '%s'", domain, pattern)

            return results

        except Exception as exc:
            logger.warning("Hunter.io domain search error for %s: %s", domain, exc)
            return []


# ---------------------------------------------------------------------------
# Apollo.io integration
# ---------------------------------------------------------------------------


def _get_apollo_key() -> str:
    key = os.environ.get("APOLLO_API_KEY", "")
    if not key:
        raise EnvironmentError("APOLLO_API_KEY environment variable is required")
    return key


async def enrich_from_apollo(
    name: str,
    organization: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any] | None:
    """Search for a person by name and organization via Apollo.io.

    Parameters
    ----------
    name : str
        Full name of the person.
    organization : str
        Organization/school district name.

    Returns
    -------
    dict | None
        A dictionary with ``email``, ``phone``, ``title``, ``linkedin_url``,
        ``organization`` keys, or ``None`` if not found.
    """
    api_key = _get_apollo_key()

    parts = name.strip().split()
    first_name = parts[0] if parts else ""
    last_name = parts[-1] if len(parts) > 1 else ""

    payload: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": organization,
        "person_titles": ["superintendent"],
    }

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(
                f"{_APOLLO_BASE_URL}/people/match",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            person = data.get("person")
            if not person:
                logger.debug("Apollo.io: no match for %s at %s", name, organization)
                return None

            return {
                "email": person.get("email"),
                "phone": (
                    person.get("phone_numbers", [{}])[0].get("sanitized_number")
                    if person.get("phone_numbers")
                    else None
                ),
                "title": person.get("title"),
                "linkedin_url": person.get("linkedin_url"),
                "organization": person.get("organization", {}).get("name"),
                "city": person.get("city"),
                "state": person.get("state"),
                "provider": "apollo.io",
            }

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Apollo.io API error for %s at %s: HTTP %d",
                name,
                organization,
                exc.response.status_code,
            )
            return None
        except Exception as exc:
            logger.warning("Apollo.io error for %s at %s: %s", name, organization, exc)
            return None
