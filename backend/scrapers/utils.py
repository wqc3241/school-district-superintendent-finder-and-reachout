"""Utility functions: name parsing, address standardization, fuzzy matching."""

from __future__ import annotations

import re

from nameparser import HumanName
from rapidfuzz import fuzz, process


# ---------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------

def parse_name(full_name: str) -> dict[str, str | None]:
    """Parse a full name string into components.

    Handles titles (Dr., Mr., Mrs., Ms., Hon.) and suffixes
    (Jr., Sr., III, Ed.D., Ph.D.).

    >>> parse_name("Dr. John A. Smith, Ed.D.")
    {'prefix': 'Dr.', 'first': 'John', 'middle': 'A.', 'last': 'Smith', 'suffix': 'Ed.D.'}
    """
    name = HumanName(full_name)
    return {
        "prefix": name.title or None,
        "first": name.first or None,
        "middle": name.middle or None,
        "last": name.last or None,
        "suffix": name.suffix or None,
    }


# ---------------------------------------------------------------------------
# Phone standardization
# ---------------------------------------------------------------------------

_PHONE_DIGITS_RE = re.compile(r"\d")


def standardize_phone(phone: str | None) -> str | None:
    """Normalize a US phone number to E.164 format (+1XXXXXXXXXX).

    Returns None for unparseable inputs.

    >>> standardize_phone("(850) 245-0505")
    '+18502450505'
    >>> standardize_phone("850.245.0505 ext 123")
    '+18502450505'
    """
    if not phone:
        return None

    digits = "".join(_PHONE_DIGITS_RE.findall(phone))

    # Strip leading 1 for 11-digit US numbers
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return None

    return f"+1{digits}"


# ---------------------------------------------------------------------------
# Address standardization
# ---------------------------------------------------------------------------

_ABBREVIATIONS: dict[str, str] = {
    "street": "St",
    "st": "St",
    "st.": "St",
    "avenue": "Ave",
    "ave": "Ave",
    "ave.": "Ave",
    "boulevard": "Blvd",
    "blvd": "Blvd",
    "blvd.": "Blvd",
    "drive": "Dr",
    "dr": "Dr",
    "dr.": "Dr",
    "road": "Rd",
    "rd": "Rd",
    "rd.": "Rd",
    "lane": "Ln",
    "ln": "Ln",
    "court": "Ct",
    "ct": "Ct",
    "suite": "Ste",
    "ste": "Ste",
    "ste.": "Ste",
    "north": "N",
    "south": "S",
    "east": "E",
    "west": "W",
    "northeast": "NE",
    "northwest": "NW",
    "southeast": "SE",
    "southwest": "SW",
}


def standardize_address(address: str | None) -> str | None:
    """Basic address standardization — collapse whitespace, apply common abbreviations.

    >>> standardize_address("325 West Gaines Street, Suite 1502")
    '325 W Gaines St, Ste 1502'
    """
    if not address:
        return None

    # Collapse whitespace
    text = " ".join(address.split())

    tokens = text.split()
    result: list[str] = []
    for token in tokens:
        # Strip trailing comma for lookup, re-add after
        trailing = ""
        if token.endswith(","):
            trailing = ","
            token = token[:-1]

        key = token.lower()
        replacement = _ABBREVIATIONS.get(key, token)
        result.append(replacement + trailing)

    return " ".join(result)


# ---------------------------------------------------------------------------
# Fuzzy district matching
# ---------------------------------------------------------------------------

def fuzzy_match_district(
    name: str,
    candidates: list[str],
    *,
    threshold: float = 85.0,
) -> tuple[str, float] | None:
    """Find the best fuzzy match for *name* among *candidates*.

    Uses token_sort_ratio which handles word-order differences well for
    district names like "Springfield Public Schools" vs "Public Schools of Springfield".

    Returns (best_match, score) or None if nothing meets the threshold.

    >>> fuzzy_match_district("Springfield Pub Schools", ["Springfield Public Schools", "Shelby County"])
    ('Springfield Public Schools', ...)
    """
    if not candidates:
        return None

    result = process.extractOne(
        name,
        candidates,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )

    if result is None:
        return None

    match_str, score, _ = result
    return (match_str, score)


def normalize_district_name(name: str) -> str:
    """Lowercase and strip common suffixes for better matching.

    >>> normalize_district_name("Springfield Public Schools District")
    'springfield public schools district'
    """
    return " ".join(name.lower().split())
