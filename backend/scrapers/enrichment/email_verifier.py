"""Mailgun email validation integration.

Provides single-email and bulk verification against the Mailgun validation
API (v4).  Requires the ``MAILGUN_API_KEY`` environment variable.

Usage::

    result = await verify_email("superintendent@example.edu")
    print(result.is_valid, result.risk)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx

from scrapers.base import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

_MAILGUN_VALIDATION_URL = "https://api.mailgun.net/v4/address/validate"


@dataclass
class EmailVerificationResult:
    """Result of a single email verification."""

    email: str
    is_valid: bool
    risk: str  # "low", "medium", "high", "unknown"
    did_you_mean: str | None
    reason: str  # "deliverable", "undeliverable", "risky", "unknown", "api_error"
    mailbox_verification: bool | None = None


def _get_api_key() -> str:
    """Retrieve the Mailgun API key from the environment."""
    key = os.environ.get("MAILGUN_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "MAILGUN_API_KEY environment variable is required for email verification"
        )
    return key


async def verify_email(
    email: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> EmailVerificationResult:
    """Verify a single email address via Mailgun's validation API.

    Returns an ``EmailVerificationResult`` with validity, risk, and
    suggested corrections.
    """
    api_key = _get_api_key()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(
                _MAILGUN_VALIDATION_URL,
                params={"address": email},
                auth=("api", api_key),
            )
            resp.raise_for_status()
            data = resp.json()

            result_str = data.get("result", "unknown")
            risk_str = data.get("risk", "unknown")
            is_valid = result_str == "deliverable"

            return EmailVerificationResult(
                email=email,
                is_valid=is_valid,
                risk=risk_str,
                did_you_mean=data.get("did_you_mean") or None,
                reason=result_str,
                mailbox_verification=data.get("mailbox_verification"),
            )

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Mailgun validation failed for %s: HTTP %d",
                email,
                exc.response.status_code,
            )
            return EmailVerificationResult(
                email=email,
                is_valid=False,
                risk="unknown",
                did_you_mean=None,
                reason="api_error",
            )
        except Exception as exc:
            logger.warning("Mailgun validation error for %s: %s", email, exc)
            return EmailVerificationResult(
                email=email,
                is_valid=False,
                risk="unknown",
                did_you_mean=None,
                reason="api_error",
            )


async def bulk_verify(
    emails: list[str],
    *,
    max_concurrent: int = 5,
    delay_seconds: float = 0.2,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[EmailVerificationResult]:
    """Verify a batch of emails with rate limiting.

    Processes up to *max_concurrent* verifications at once, with
    *delay_seconds* between batches to respect API rate limits.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[EmailVerificationResult] = []

    async def _verify_one(email: str) -> EmailVerificationResult:
        async with semaphore:
            result = await verify_email(email, timeout=timeout)
            await asyncio.sleep(delay_seconds)
            return result

    tasks = [_verify_one(e) for e in emails]
    results = await asyncio.gather(*tasks)

    valid_count = sum(1 for r in results if r.is_valid)
    logger.info(
        "Bulk verification complete: %d/%d valid",
        valid_count,
        len(results),
    )
    return list(results)
