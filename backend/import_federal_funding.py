"""
Import Title I, Title III, and ELL student count data into the districts table.

Data sources:
1. Title I: FY2024 ESEA Title I LEA Allocations from ed.gov (per-state Excel files)
2. Title III: CCD Finance data from Urban Institute API (rev_fed_state_bilingual_ed)
3. ELL counts: CCD Directory data from Urban Institute API (english_language_learners, enrollment)
"""

import sys
import io
import time
import csv
import zipfile
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import httpx
import psycopg2
import openpyxl


# Database connection
DB_CONFIG = {
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': 6543,
    'dbname': 'postgres',
    'user': 'postgres.mymxwesilduzjfniecky',
    'password': 'GdguFo6u90xogV9A',
    'sslmode': 'require',
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def pad_nces_id(raw_id):
    """Zero-pad NCES ID to 7 characters."""
    s = str(int(raw_id)).zfill(7)
    return s


# ============================================================
# TASK 1: Import Title I Data
# ============================================================

TITLE_I_STATE_FILES = {
    'alabama': 109623, 'alaska': 109624, 'arizona': 109625, 'arkansas': 109626,
    'california': 109627, 'colorado': 109628, 'connecticut': 109629, 'dc': 109630,
    'delaware': 109631, 'florida': 109632, 'georgia': 109633, 'hawaii': 109634,
    'idaho': 109635, 'illinois': 109636, 'indiana': 109637, 'iowa': 109638,
    'kansas': 109639, 'kentucky': 109640, 'louisiana': 109641, 'maine': 109642,
    'maryland': 109643, 'massachusetts': 109644, 'michigan': 109645,
    'minnesota': 109646, 'mississippi': 109647, 'missouri': 109648,
    'montana': 109649, 'nebraska': 109650, 'nevada': 109651, 'nh': 109652,
    'new-jersey': 109653, 'new-mexico': 109654, 'new-york': 109655,
    'north-carolina': 109656, 'north-dakota': 109657, 'ohio': 109658,
    'oklahoma': 109659, 'oregon': 109660, 'pennsylvania': 109661,
    'puerto-rico': 109662, 'rhode-island': 109663, 'south-carolina': 109664,
    'south-dakota': 109665, 'tennessee': 109666, 'texas': 109667,
    'utah': 109668, 'vermont': 109669, 'virginia': 109674,
    'washington': 109670, 'west-virginia': 109671, 'wisconsin': 109672,
    'wyoming': 109673,
}


def download_title_i_data():
    """Download all state Title I Excel files and extract LEA allocations."""
    title_i_data = {}  # nces_id -> allocation amount
    client = httpx.Client(follow_redirects=True, timeout=60)

    for state_name, file_id in TITLE_I_STATE_FILES.items():
        url = f'https://www.ed.gov/media/document/fy2024-esea-title-1-tables-{state_name}-{file_id}.xlsx'
        try:
            r = client.get(url)
            if r.status_code != 200:
                print(f'  WARNING: Failed to download {state_name}: HTTP {r.status_code}')
                continue

            wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
            ws = wb.active

            count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0] is None:
                    continue
                try:
                    lea_id_raw = row[0]
                    allocation = row[2]

                    # Skip non-numeric IDs (footnotes)
                    if not isinstance(lea_id_raw, (int, float)):
                        continue
                    if allocation is None or not isinstance(allocation, (int, float)):
                        continue
                    if allocation <= 0:
                        continue

                    nces_id = pad_nces_id(lea_id_raw)
                    title_i_data[nces_id] = round(float(allocation), 2)
                    count += 1
                except (ValueError, TypeError, IndexError):
                    continue

            wb.close()
            print(f'  {state_name}: {count} districts')
        except Exception as e:
            print(f'  ERROR downloading {state_name}: {e}')

    client.close()
    return title_i_data


def import_title_i(title_i_data):
    """Update districts table with Title I data."""
    conn = get_db_connection()
    cur = conn.cursor()

    updated = 0
    batch = []
    for nces_id, allocation in title_i_data.items():
        batch.append((allocation, nces_id))
        if len(batch) >= 500:
            cur.executemany(
                "UPDATE districts SET title_i_allocation = %s, title_i_status = TRUE WHERE nces_id = %s",
                batch
            )
            updated += cur.rowcount
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE districts SET title_i_allocation = %s, title_i_status = TRUE WHERE nces_id = %s",
            batch
        )
        updated += cur.rowcount
        conn.commit()

    cur.close()
    conn.close()
    return updated


# ============================================================
# TASK 2: Import Title III Data (from CCD Finance)
# ============================================================

FIPS_CODES = list(range(1, 57))  # All state FIPS codes (1-56)


def download_title_iii_data():
    """Download Title III (bilingual ed) allocation data from Urban Institute API."""
    title_iii_data = {}  # nces_id -> allocation
    client = httpx.Client(follow_redirects=True, timeout=60)

    # Use most recent year with finance data (2020)
    year = 2020

    for fips in FIPS_CODES:
        url = f'https://educationdata.urban.org/api/v1/school-districts/ccd/finance/{year}/?fips={fips}'
        try:
            r = client.get(url)
            if r.status_code != 200:
                continue
            data = r.json()
            results = data.get('results', [])
            count = 0
            for rec in results:
                leaid = rec.get('leaid')
                bilingual = rec.get('rev_fed_state_bilingual_ed')
                if leaid and bilingual and isinstance(bilingual, (int, float)) and bilingual > 0:
                    title_iii_data[leaid] = round(float(bilingual), 2)
                    count += 1

            # Handle pagination
            next_url = data.get('next')
            while next_url:
                r = client.get(next_url)
                if r.status_code != 200:
                    break
                data = r.json()
                for rec in data.get('results', []):
                    leaid = rec.get('leaid')
                    bilingual = rec.get('rev_fed_state_bilingual_ed')
                    if leaid and bilingual and isinstance(bilingual, (int, float)) and bilingual > 0:
                        title_iii_data[leaid] = round(float(bilingual), 2)
                        count += 1
                next_url = data.get('next')

            if count > 0:
                print(f'  FIPS {fips:02d}: {count} districts with Title III data')
        except Exception as e:
            print(f'  ERROR FIPS {fips}: {e}')
            time.sleep(1)

    client.close()
    return title_iii_data


def import_title_iii(title_iii_data):
    """Update districts table with Title III data."""
    conn = get_db_connection()
    cur = conn.cursor()

    updated = 0
    batch = []
    for nces_id, allocation in title_iii_data.items():
        batch.append((allocation, nces_id))
        if len(batch) >= 500:
            cur.executemany(
                "UPDATE districts SET title_iii_allocation = %s, esl_program_status = TRUE WHERE nces_id = %s",
                batch
            )
            updated += cur.rowcount
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE districts SET title_iii_allocation = %s, esl_program_status = TRUE WHERE nces_id = %s",
            batch
        )
        updated += cur.rowcount
        conn.commit()

    cur.close()
    conn.close()
    return updated


# ============================================================
# TASK 3: Import ELL Student Counts
# ============================================================

def download_ell_data():
    """Download ELL student count data from Urban Institute API."""
    ell_data = {}  # nces_id -> (ell_count, total_enrollment)
    client = httpx.Client(follow_redirects=True, timeout=60)

    # Use 2021 for ELL data (most recent with english_language_learners populated)
    # Use 2022 for enrollment if 2021 enrollment missing
    year = 2021

    for fips in FIPS_CODES:
        url = f'https://educationdata.urban.org/api/v1/school-districts/ccd/directory/{year}/?fips={fips}'
        try:
            r = client.get(url)
            if r.status_code != 200:
                continue
            data = r.json()
            count = 0

            def process_results(results):
                nonlocal count
                for rec in results:
                    leaid = rec.get('leaid')
                    ell = rec.get('english_language_learners')
                    enrollment = rec.get('enrollment')
                    if leaid and ell is not None and isinstance(ell, (int, float)) and ell >= 0:
                        ell_data[leaid] = (int(ell), int(enrollment) if enrollment else None)
                        count += 1

            process_results(data.get('results', []))

            next_url = data.get('next')
            while next_url:
                r = client.get(next_url)
                if r.status_code != 200:
                    break
                data = r.json()
                process_results(data.get('results', []))
                next_url = data.get('next')

            if count > 0:
                print(f'  FIPS {fips:02d}: {count} districts with ELL data')
        except Exception as e:
            print(f'  ERROR FIPS {fips}: {e}')
            time.sleep(1)

    client.close()
    return ell_data


def import_ell(ell_data):
    """Update districts table with ELL data."""
    conn = get_db_connection()
    cur = conn.cursor()

    updated = 0
    batch = []
    for nces_id, (ell_count, enrollment) in ell_data.items():
        ell_pct = None
        if enrollment and enrollment > 0:
            ell_pct = round(ell_count / enrollment * 100, 2)
        batch.append((ell_count, ell_pct, nces_id))
        if len(batch) >= 500:
            cur.executemany(
                "UPDATE districts SET ell_student_count = %s, ell_percentage = %s WHERE nces_id = %s",
                batch
            )
            updated += cur.rowcount
            conn.commit()
            batch = []

    if batch:
        cur.executemany(
            "UPDATE districts SET ell_student_count = %s, ell_percentage = %s WHERE nces_id = %s",
            batch
        )
        updated += cur.rowcount
        conn.commit()

    cur.close()
    conn.close()
    return updated


# ============================================================
# Verification
# ============================================================

def verify():
    """Run verification queries."""
    conn = get_db_connection()
    cur = conn.cursor()

    queries = [
        ("Districts with Title I status = TRUE", "SELECT COUNT(*) FROM districts WHERE title_i_status = TRUE"),
        ("Districts with ESL program status = TRUE", "SELECT COUNT(*) FROM districts WHERE esl_program_status = TRUE"),
        ("Districts with ELL student count", "SELECT COUNT(*) FROM districts WHERE ell_student_count IS NOT NULL"),
        ("Average Title I allocation", "SELECT AVG(title_i_allocation) FROM districts WHERE title_i_allocation IS NOT NULL"),
        ("Average Title III allocation", "SELECT AVG(title_iii_allocation) FROM districts WHERE title_iii_allocation IS NOT NULL"),
    ]

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    for label, query in queries:
        cur.execute(query)
        result = cur.fetchone()[0]
        if isinstance(result, float):
            print(f"  {label}: {result:,.2f}")
        else:
            print(f"  {label}: {result:,}")

    cur.close()
    conn.close()


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("TASK 1: Importing Title I Data")
    print("=" * 60)
    print("Downloading Title I allocation data from ed.gov...")
    title_i_data = download_title_i_data()
    print(f"\nTotal Title I records: {len(title_i_data)}")
    print("Updating database...")
    updated = import_title_i(title_i_data)
    print(f"Title I: {updated} districts updated in database")

    print("\n" + "=" * 60)
    print("TASK 2: Importing Title III Data")
    print("=" * 60)
    print("Downloading Title III (bilingual ed) finance data from Urban Institute API...")
    title_iii_data = download_title_iii_data()
    print(f"\nTotal Title III records: {len(title_iii_data)}")
    print("Updating database...")
    updated = import_title_iii(title_iii_data)
    print(f"Title III: {updated} districts updated in database")

    print("\n" + "=" * 60)
    print("TASK 3: Importing ELL Student Counts")
    print("=" * 60)
    print("Downloading ELL data from Urban Institute API...")
    ell_data = download_ell_data()
    print(f"\nTotal ELL records: {len(ell_data)}")
    print("Updating database...")
    updated = import_ell(ell_data)
    print(f"ELL: {updated} districts updated in database")

    verify()


if __name__ == '__main__':
    main()
