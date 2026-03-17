"""
NJ Superintendent Scraper
=========================
Scrapes superintendent contact information from the NJ DOE User-Friendly Budget
employee data (CSV) and inserts into the contacts table.

Data source: https://www.nj.gov/education/budget/ufb/2526/download/employees26.csv
This is official NJ Department of Education data for 2025-2026 contracts.

Also enriches with phone numbers from the NCES Urban Institute Education Data API.
"""

import csv
import io
import re
import uuid
from difflib import SequenceMatcher

import httpx
import psycopg2
import psycopg2.extras


# ── Configuration ──────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "aws-0-us-west-2.pooler.supabase.com",
    "port": 6543,
    "dbname": "postgres",
    "user": "postgres.mymxwesilduzjfniecky",
    "password": "GdguFo6u90xogV9A",
    "sslmode": "require",
}

NJ_DOE_EMPLOYEE_CSV_URL = (
    "https://www.nj.gov/education/budget/ufb/2526/download/employees26.csv"
)
URBAN_INST_API_URL = (
    "https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2022/"
    "?fips=34&per_page=1000"
)

CONFIDENCE_SCORE = 85

# Manual overrides for district names that don't fuzzy-match well
MANUAL_CSV_TO_DB = {
    "Ho Ho Kus Boro": "Ho-Ho-Kus School District",
}


# ── Name normalization helpers ─────────────────────────────────────────────

# Common abbreviation expansions used in NJ DOE data
ABBREV_MAP = {
    "twp": "township",
    "boro": "borough",
    "reg": "regional",
    "co": "county",
    "elem": "elementary",
    "voc": "vocational",
    "spec": "special",
    "serv": "services",
    "tech": "technical",
    "jt": "jointure",
}


def normalize_district_name(name: str) -> str:
    """Normalize a district name for fuzzy matching."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [
        "school district",
        "school dist",
        "public school district",
        "public schools district",
        "board of education",
        "public school",
        "public schools",
        "regional school district",
        "elementary school district",
        "sd",
    ]:
        name = name.replace(suffix, "")
    # Expand abbreviations
    words = name.split()
    expanded = []
    for w in words:
        expanded.append(ABBREV_MAP.get(w, w))
    name = " ".join(expanded)
    # Remove punctuation and extra whitespace
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def match_score(csv_name: str, db_name: str) -> float:
    """Return a similarity score between 0 and 1."""
    n1 = normalize_district_name(csv_name)
    n2 = normalize_district_name(db_name)

    # Exact match after normalization
    if n1 == n2:
        return 1.0

    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return 0.95

    # Check if the first significant word matches
    w1 = n1.split()
    w2 = n2.split()
    if w1 and w2 and w1[0] == w2[0]:
        # First word matches - use sequence matcher for the rest
        return 0.5 + 0.5 * SequenceMatcher(None, n1, n2).ratio()

    return SequenceMatcher(None, n1, n2).ratio()


def parse_superintendent_name(raw_name: str):
    """
    Parse a superintendent name into (prefix, first_name, last_name, suffix).
    Handles formats like:
      - "Dr. Daniel J. Dooley"
      - "Small La'quetta"  (last, first)
      - "Guenther, Philip"  (last, first)
      - "David Cappuccio Jr."
    """
    name = raw_name.strip()

    # Skip non-person entries
    if not name or name.lower() in [
        "shared service agreement",
        "n/a",
        "tbd",
        "vacant",
        "none",
        "",
    ]:
        return None, None, None, None

    # Extract prefix
    prefix = None
    prefix_patterns = [
        (r"^Dr\.\s*", "Dr."),
        (r"^Mr\.\s*", "Mr."),
        (r"^Mrs\.\s*", "Mrs."),
        (r"^Ms\.\s*", "Ms."),
    ]
    for pat, pval in prefix_patterns:
        if re.match(pat, name, re.IGNORECASE):
            prefix = pval
            name = re.sub(pat, "", name, flags=re.IGNORECASE).strip()
            break

    # Extract suffix
    suffix = None
    suffix_patterns = [
        (r",?\s+Jr\.?\s*$", "Jr."),
        (r",?\s+Sr\.?\s*$", "Sr."),
        (r",?\s+III\s*$", "III"),
        (r",?\s+II\s*$", "II"),
        (r",?\s+IV\s*$", "IV"),
        (r",?\s+Ed\.?D\.?\s*$", "Ed.D."),
        (r",?\s+Ph\.?D\.?\s*$", "Ph.D."),
        (r",?\s+Esq\.?\s*$", "Esq."),
    ]
    for pat, sval in suffix_patterns:
        if re.search(pat, name, re.IGNORECASE):
            suffix = sval
            name = re.sub(pat, "", name, flags=re.IGNORECASE).strip()
            break

    # Check if name is in "Last, First" format
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        last_name = parts[0]
        first_parts = parts[1].split() if len(parts) > 1 else []
        first_name = first_parts[0] if first_parts else ""
    else:
        parts = name.split()
        if len(parts) == 1:
            # Single name - treat as last name
            first_name = ""
            last_name = parts[0]
        elif len(parts) == 2:
            first_name = parts[0]
            last_name = parts[1]
        else:
            # Multiple parts: first name is first, last name is last,
            # middle parts ignored
            first_name = parts[0]
            last_name = parts[-1]

    # Clean up - use empty string for first_name if missing (DB has NOT NULL)
    first_name = first_name.strip().title() if first_name else ""
    last_name = last_name.strip().title() if last_name else None

    return prefix, first_name, last_name, suffix


def fetch_superintendent_data():
    """Download and parse the NJ DOE employee CSV for superintendents."""
    print("Downloading NJ DOE employee data (2025-2026)...")
    r = httpx.get(
        NJ_DOE_EMPLOYEE_CSV_URL,
        follow_redirects=True,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    print(f"  Downloaded {len(r.content):,} bytes")

    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    print(f"  Total employee rows: {len(rows)}")

    # Filter to superintendent only (not assistant, deputy, etc.)
    supts = [
        row
        for row in rows
        if row.get("emp_job_title", "").strip().lower() == "superintendent"
    ]
    print(f"  Superintendent records: {len(supts)}")

    # Filter out shared service agreements and placeholder names
    valid_supts = []
    skipped = 0
    for s in supts:
        name = s.get("emp_name", "").strip()
        if name.lower() in [
            "shared service agreement",
            "n/a",
            "tbd",
            "vacant",
            "",
        ]:
            skipped += 1
            continue
        valid_supts.append(s)
    print(f"  Valid superintendent records: {len(valid_supts)} (skipped {skipped})")

    return valid_supts


def fetch_phone_numbers():
    """Fetch district phone numbers from the Urban Institute Education Data API."""
    print("Fetching phone numbers from Urban Institute API...")
    try:
        r = httpx.get(
            URBAN_INST_API_URL,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        print(f"  Got {len(results)} district records with phone numbers")

        # Build a lookup by normalized name
        phone_lookup = {}
        for rec in results:
            name = rec.get("lea_name", "")
            phone = rec.get("phone", "")
            if name and phone:
                phone_lookup[normalize_district_name(name)] = phone
        return phone_lookup
    except Exception as e:
        print(f"  Warning: Could not fetch phone numbers: {e}")
        return {}


def load_db_districts():
    """Load all NJ districts from the database."""
    print("Loading NJ districts from database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, name, nces_id FROM districts WHERE state='NJ'")
    districts = cur.fetchall()
    cur.close()
    conn.close()
    print(f"  Loaded {len(districts)} NJ districts")
    return districts  # list of (id, name, nces_id)


def build_district_match_map(csv_districts, db_districts):
    """
    Match CSV district names to DB district names.
    Returns dict: csv_distname -> (db_id, db_name, score)
    """
    print("Matching CSV district names to database districts...")

    # Build normalized index for DB districts
    db_index = {}
    for db_id, db_name, nces_id in db_districts:
        norm = normalize_district_name(db_name)
        db_index[norm] = (db_id, db_name, nces_id)

    matches = {}
    unmatched = []

    for csv_name in csv_districts:
        # Check manual overrides first
        if csv_name in MANUAL_CSV_TO_DB:
            override_name = MANUAL_CSV_TO_DB[csv_name]
            override_norm = normalize_district_name(override_name)
            if override_norm in db_index:
                db_id, db_name, _ = db_index[override_norm]
                matches[csv_name] = (db_id, db_name, 1.0)
                continue

        csv_norm = normalize_district_name(csv_name)

        # Try exact normalized match first
        if csv_norm in db_index:
            db_id, db_name, _ = db_index[csv_norm]
            matches[csv_name] = (db_id, db_name, 1.0)
            continue

        # Try fuzzy matching
        best_score = 0
        best_match = None
        for db_norm, (db_id, db_name, _) in db_index.items():
            score = match_score(csv_name, db_name)
            if score > best_score:
                best_score = score
                best_match = (db_id, db_name)

        if best_score >= 0.70:
            matches[csv_name] = (best_match[0], best_match[1], best_score)
        else:
            unmatched.append((csv_name, best_match[1] if best_match else "?", best_score))

    print(f"  Matched: {len(matches)}")
    print(f"  Unmatched: {len(unmatched)}")
    if unmatched:
        print("  Unmatched districts (top 20):")
        for csv_name, best_db, score in sorted(unmatched, key=lambda x: -x[2])[:20]:
            print(f"    CSV: '{csv_name}' -> best DB: '{best_db}' (score: {score:.2f})")

    return matches


def insert_contacts(supt_records, match_map, phone_lookup):
    """Insert superintendent contacts into the database."""
    print("\nInserting contacts into database...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Check for existing superintendent contacts to avoid duplicates
    cur.execute(
        """
        SELECT district_id FROM contacts
        WHERE role = 'superintendent'
        AND district_id IN (SELECT id FROM districts WHERE state = 'NJ')
        """
    )
    existing = set(row[0] for row in cur.fetchall())
    print(f"  Existing superintendent contacts for NJ: {len(existing)}")

    inserted = 0
    skipped_no_match = 0
    skipped_existing = 0
    skipped_bad_name = 0

    for rec in supt_records:
        csv_dist = rec["distname"].strip()
        raw_name = rec["emp_name"].strip()

        # Check if we have a match
        if csv_dist not in match_map:
            skipped_no_match += 1
            continue

        db_id, db_name, score = match_map[csv_dist]

        # Skip if contact already exists for this district
        if db_id in existing:
            skipped_existing += 1
            continue

        # Parse the name
        prefix, first_name, last_name, suffix = parse_superintendent_name(raw_name)
        if not last_name:
            skipped_bad_name += 1
            continue

        # Look up phone number
        phone = phone_lookup.get(normalize_district_name(db_name), None)

        # Insert
        cur.execute(
            """
            INSERT INTO contacts (
                district_id, role, first_name, last_name, prefix, suffix,
                phone, confidence_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                db_id,
                "superintendent",
                first_name,
                last_name,
                prefix,
                suffix,
                phone,
                CONFIDENCE_SCORE,
            ),
        )
        existing.add(db_id)  # Prevent duplicate inserts within same run
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"RESULTS:")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (no district match): {skipped_no_match}")
    print(f"  Skipped (already exists): {skipped_existing}")
    print(f"  Skipped (bad name): {skipped_bad_name}")
    print(f"{'='*60}")

    return inserted


def main():
    print("=" * 60)
    print("NJ Superintendent Scraper")
    print("=" * 60)

    # Step 1: Fetch superintendent data from NJ DOE
    supt_records = fetch_superintendent_data()

    # Step 2: Fetch phone numbers from Urban Institute API
    phone_lookup = fetch_phone_numbers()

    # Step 3: Load DB districts
    db_districts = load_db_districts()

    # Step 4: Build match map
    csv_dist_names = sorted(set(r["distname"].strip() for r in supt_records))
    match_map = build_district_match_map(csv_dist_names, db_districts)

    # Step 5: Insert contacts
    inserted = insert_contacts(supt_records, match_map, phone_lookup)

    # Step 6: Verify
    print("\nVerification:")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state = 'NJ' AND c.role = 'superintendent'
        """
    )
    total = cur.fetchone()[0]
    print(f"  Total NJ superintendent contacts in DB: {total}")

    cur.execute(
        """
        SELECT d.name, c.prefix, c.first_name, c.last_name, c.suffix, c.phone
        FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state = 'NJ' AND c.role = 'superintendent'
        ORDER BY d.name
        LIMIT 15
        """
    )
    print("\n  Sample contacts:")
    for row in cur.fetchall():
        name_parts = [p for p in [row[1], row[2], row[3], row[4]] if p]
        print(f"    {row[0]}: {' '.join(name_parts)} | phone: {row[5] or 'N/A'}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
