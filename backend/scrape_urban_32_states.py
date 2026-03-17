"""
Scrape superintendent contacts for 32 U.S. states using Urban Institute Education Data API.

API: https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2022/?fips=XX

States: OH, MI, PA, AZ, MN, WI, NC, IA, AR, ME, CO, GA, ND, VA, CT, NH, LA, VT,
        ID, KY, SD, UT, AL, MS, TN, NM, SC, RI, WY, AK, DE, NV
"""

import httpx
import psycopg2
import re
import time
import traceback

DB_CONFIG = {
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': 6543,
    'dbname': 'postgres',
    'user': 'postgres.mymxwesilduzjfniecky',
    'password': 'GdguFo6u90xogV9A',
    'sslmode': 'require',
}

# State abbreviation -> FIPS code
STATES = {
    'OH': 39, 'MI': 26, 'PA': 42, 'AZ': 4, 'MN': 27, 'WI': 55, 'NC': 37,
    'IA': 19, 'AR': 5, 'ME': 23, 'CO': 8, 'GA': 13, 'ND': 38, 'VA': 51,
    'CT': 9, 'NH': 33, 'LA': 22, 'VT': 50, 'ID': 16, 'KY': 21, 'SD': 46,
    'UT': 49, 'AL': 1, 'MS': 28, 'TN': 47, 'NM': 35, 'SC': 45, 'RI': 44,
    'WY': 56, 'AK': 2, 'DE': 10, 'NV': 32,
}


def parse_superintendent_name(full_name):
    """Parse superintendent_name into prefix, first_name, last_name, suffix.

    Handles formats:
    - "John Smith"
    - "Smith, John"
    - "Dr. John Smith"
    - "John A. Smith Jr."
    """
    if not full_name or not full_name.strip():
        return None, '', '', None

    full_name = full_name.strip()

    # Check for "Last, First" format
    if ',' in full_name:
        parts = full_name.split(',', 1)
        last_part = parts[0].strip()
        first_part = parts[1].strip()
        # Reconstruct as "First Last" for uniform processing
        full_name = f"{first_part} {last_part}"

    # Extract prefix
    prefix = None
    for p in ['Dr. ', 'Dr ', 'Mr. ', 'Mr ', 'Mrs. ', 'Mrs ', 'Ms. ', 'Ms ',
              'Rev. ', 'Rev ', 'Maj. ', 'Col. ', 'Capt. ']:
        if full_name.startswith(p):
            prefix = p.strip().rstrip('.')
            # Re-add period for standard prefixes
            if prefix in ('Dr', 'Mr', 'Mrs', 'Ms', 'Rev'):
                pass  # store without period
            full_name = full_name[len(p):].strip()
            break

    # Extract suffix
    suffix = None
    for s in [', Ed.D.', ', Ph.D.', ', Ed.D', ', Ph.D', ', Ed. D.', ', Ph. D.',
              ' Ed.D.', ' Ph.D.', ' Jr.', ' Jr', ' Sr.', ' Sr', ' III', ' II', ' IV',
              ', Jr.', ', Jr', ', Sr.', ', Sr', ', III', ', II', ', IV']:
        if full_name.endswith(s):
            suffix = s.strip().lstrip(',').strip()
            full_name = full_name[:-(len(s))].strip()
            break

    parts = full_name.split()
    if len(parts) == 0:
        return prefix, '', '', suffix
    elif len(parts) == 1:
        return prefix, parts[0], '', suffix
    else:
        first_name = parts[0]
        last_name = parts[-1]
        return prefix, first_name, last_name, suffix


def format_phone(phone_val):
    """Format phone number from API (may be integer or string)."""
    if phone_val is None:
        return None
    phone_str = str(phone_val).strip()
    if not phone_str or phone_str in ('0', '-1', '-2', 'None', ''):
        return None
    # Remove non-digit chars
    digits = re.sub(r'\D', '', phone_str)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    elif len(digits) >= 7:
        return phone_str
    return None


def fetch_state_data(client, fips):
    """Fetch all district data for a state from Urban Institute API, handling pagination."""
    url = f'https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2022/?fips={fips:02d}'
    all_results = []

    while url:
        try:
            resp = client.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results', [])
            all_results.extend(results)
            url = data.get('next')  # pagination
        except Exception as e:
            print(f"    API error fetching {url}: {e}")
            break

    return all_results


def main():
    print("=" * 70)
    print("Urban Institute API - Superintendent Contacts for 32 States")
    print("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    client = httpx.Client(timeout=60, follow_redirects=True)

    # Build NCES ID -> district UUID lookup for all target states
    state_list = list(STATES.keys())
    placeholders = ','.join(['%s'] * len(state_list))
    cur.execute(f"SELECT id, nces_id, state FROM districts WHERE state IN ({placeholders})", state_list)
    nces_lookup = {}
    state_district_counts = {}
    for row in cur.fetchall():
        dist_id, nces_id, state = row
        nces_lookup[nces_id] = dist_id
        state_district_counts[state] = state_district_counts.get(state, 0) + 1

    print(f"Loaded {len(nces_lookup)} districts from DB across {len(state_district_counts)} states\n")

    # Get all existing superintendent contacts for these states
    cur.execute(f"""
        SELECT c.district_id FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state IN ({placeholders}) AND c.role = 'superintendent'
    """, state_list)
    existing_contacts = set(row[0] for row in cur.fetchall())
    print(f"Found {len(existing_contacts)} existing superintendent contacts (will skip)\n")

    # Process each state
    summary = []
    grand_total_inserted = 0
    grand_total_api = 0
    grand_total_matched = 0
    grand_total_with_name = 0

    for state_abbr, fips in STATES.items():
        start = time.time()
        db_count = state_district_counts.get(state_abbr, 0)
        print(f"[{state_abbr}] FIPS={fips:02d}, {db_count} districts in DB...")

        if db_count == 0:
            print(f"  No districts in DB, skipping")
            summary.append((state_abbr, 0, 0, 0, 0, 0))
            continue

        # Fetch from API
        results = fetch_state_data(client, fips)
        elapsed = time.time() - start
        print(f"  API returned {len(results)} districts in {elapsed:.1f}s")

        # Process results
        inserted = 0
        matched = 0
        with_name = 0
        skipped_existing = 0
        skipped_no_match = 0

        for r in results:
            leaid = r.get('leaid')
            supt_name = r.get('superintendent_name')
            phone = r.get('phone')
            lea_name = r.get('lea_name', '')

            if not leaid:
                continue

            # Zero-pad leaid to 7 digits
            nces_id = str(leaid).zfill(7)

            # Try to match to DB
            district_id = nces_lookup.get(nces_id)
            if not district_id:
                skipped_no_match += 1
                continue
            matched += 1

            # Skip if no superintendent name
            if not supt_name or not supt_name.strip():
                continue
            with_name += 1

            # Skip if contact already exists
            if district_id in existing_contacts:
                skipped_existing += 1
                continue

            # Parse name
            prefix, first_name, last_name, suffix = parse_superintendent_name(supt_name)

            # Skip if we couldn't parse a meaningful name
            if not first_name and not last_name:
                continue

            # Format phone
            formatted_phone = format_phone(phone)

            # Insert
            try:
                cur.execute("""
                    INSERT INTO contacts (district_id, role, first_name, last_name, prefix, suffix,
                                          email, email_status, phone, confidence_score, do_not_contact)
                    VALUES (%s, 'superintendent', %s, %s, %s, %s, NULL, 'unverified', %s, 80, false)
                """, (district_id, first_name, last_name, prefix, suffix, formatted_phone))
                existing_contacts.add(district_id)
                inserted += 1
            except Exception as e:
                print(f"  Insert error for {lea_name} ({nces_id}): {e}")
                conn.rollback()

        conn.commit()
        pct = f"{inserted}/{db_count} ({inserted*100//db_count}%)" if db_count > 0 else "0"
        print(f"  Matched={matched}, WithName={with_name}, Existing={skipped_existing}, "
              f"NoMatch={skipped_no_match}, INSERTED={inserted} [{pct}]")

        grand_total_inserted += inserted
        grand_total_api += len(results)
        grand_total_matched += matched
        grand_total_with_name += with_name
        summary.append((state_abbr, len(results), matched, with_name, inserted, db_count))

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'State':<6} {'API':>6} {'Match':>7} {'w/Name':>7} {'Insert':>7} {'DB Dist':>8} {'Cover%':>7}")
    print("-" * 50)
    for state_abbr, api_count, matched, with_name, inserted, db_count in summary:
        pct = f"{inserted*100//db_count}%" if db_count > 0 else "N/A"
        print(f"{state_abbr:<6} {api_count:>6} {matched:>7} {with_name:>7} {inserted:>7} {db_count:>8} {pct:>7}")
    print("-" * 50)
    print(f"{'TOTAL':<6} {grand_total_api:>6} {grand_total_matched:>7} {grand_total_with_name:>7} "
          f"{grand_total_inserted:>7}")

    # Final DB verification
    print("\n--- Final DB Count per State ---")
    for state_abbr in STATES:
        cur.execute("""
            SELECT COUNT(*) FROM contacts c
            JOIN districts d ON c.district_id = d.id
            WHERE d.state = %s AND c.role = 'superintendent'
        """, (state_abbr,))
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  {state_abbr}: {count} superintendent contacts")

    cur.close()
    conn.close()
    client.close()
    print(f"\nDone! Inserted {grand_total_inserted} new superintendent contacts.")


if __name__ == '__main__':
    main()
