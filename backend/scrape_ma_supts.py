"""
Scrape Massachusetts superintendent contact info from DESE profiles
and insert into Supabase PostgreSQL contacts table.
"""
import httpx
from bs4 import BeautifulSoup
import re
import psycopg2
import time

DB_CONFIG = {
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': 6543,
    'dbname': 'postgres',
    'user': 'postgres.mymxwesilduzjfniecky',
    'password': 'GdguFo6u90xogV9A',
    'sslmode': 'require',
}

def get_district_org_codes(client):
    """Get all MA district org codes from the DESE profiles dropdown."""
    url = 'https://profiles.doe.mass.edu/general/general.aspx?topNavID=1&leftNavId=100&orgcode=00010000&orgtypecode=5'
    resp = client.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')

    org_dropdown = soup.find('span', {'id': 'ctl00_ContentPlaceHolder1_lblOrgDropDown'})
    districts = []
    if org_dropdown:
        for opt in org_dropdown.find_all('option'):
            val = opt.get('value', '')
            text = opt.text.strip()
            if val and text:
                match = re.search(r'orgCode=(\d+)', val)
                if match:
                    districts.append((match.group(1), text))
    return districts


def scrape_district_contact(client, orgcode):
    """Scrape superintendent info from a district's profile page."""
    url = f'https://profiles.doe.mass.edu/general/general.aspx?topNavID=1&leftNavId=100&orgcode={orgcode}&orgtypecode=5'
    resp = client.get(url)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    wb = soup.find('div', {'id': 'whiteboxRight'})
    if not wb:
        return None

    text = wb.get_text()

    # Extract superintendent name
    supt_match = re.search(r'Superintendent\s*:\s*(.+?)(?:\n|$)', text)
    if not supt_match:
        return None

    full_name = supt_match.group(1).strip()
    if not full_name or full_name == '':
        return None

    # Parse name parts
    # Handle prefixes
    prefixes = ['Dr.', 'Dr', 'Mr.', 'Mr', 'Mrs.', 'Mrs', 'Ms.', 'Ms']
    prefix = None
    name_str = full_name
    for p in prefixes:
        if name_str.startswith(p + ' '):
            prefix = p.rstrip('.')
            name_str = name_str[len(p):].strip()
            break

    # Handle suffixes
    suffixes = ['Jr.', 'Jr', 'Sr.', 'Sr', 'III', 'II', 'IV', 'Ed.D.', 'Ph.D.', 'Ed.D', 'Ph.D']
    suffix = None
    for s in suffixes:
        if name_str.endswith(' ' + s) or name_str.endswith(', ' + s):
            suffix = s
            name_str = name_str[:-(len(s))].rstrip(', ').strip()
            break

    # Split into first/last
    parts = name_str.split()
    if len(parts) == 0:
        return None
    elif len(parts) == 1:
        first_name = parts[0]
        last_name = ''
    else:
        first_name = parts[0]
        last_name = ' '.join(parts[1:])

    # Extract email
    wb_html = str(wb)
    email_match = re.search(r'mailto:([^"]+)"', wb_html)
    email = email_match.group(1) if email_match else None

    # Extract phone (first phone number found, which is the main office phone)
    phone_match = re.search(r'fa-phone.*?</span>.*?<td[^>]*>([^<]+)</td>', wb_html, re.S)
    phone = phone_match.group(1).strip() if phone_match else None

    return {
        'prefix': prefix,
        'first_name': first_name.strip(),
        'last_name': last_name.strip(),
        'suffix': suffix,
        'email': email,
        'phone': phone,
        'full_name_raw': full_name,
    }


def normalize_name(name):
    """Normalize district name for matching."""
    n = name.lower().strip()
    # Remove common suffixes/parentheticals
    n = re.sub(r'\s*\(non-op\)\s*', '', n)
    n = re.sub(r'\s*\(district\)\s*', '', n)
    n = re.sub(r'\s*\(.*?\)\s*', '', n)
    n = n.strip()
    return n


def main():
    print("=" * 60)
    print("Massachusetts Superintendent Scraper")
    print("=" * 60)

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get existing MA districts from DB
    cur.execute("SELECT id, name FROM districts WHERE state='MA'")
    db_districts = cur.fetchall()
    print(f"\nFound {len(db_districts)} MA districts in database")

    # Build lookup by normalized name
    db_lookup = {}
    for did, dname in db_districts:
        norm = normalize_name(dname)
        db_lookup[norm] = (did, dname)

    # Check for existing superintendent contacts to avoid duplicates
    cur.execute("""
        SELECT c.district_id FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state = 'MA' AND c.role = 'superintendent'
    """)
    existing = set(row[0] for row in cur.fetchall())
    print(f"Existing superintendent contacts: {len(existing)}")

    # Get org codes from DESE
    client = httpx.Client(follow_redirects=True, timeout=30)
    print("\nFetching district list from DESE...")
    dese_districts = get_district_org_codes(client)
    print(f"Found {len(dese_districts)} districts on DESE")

    # Scrape each district
    scraped = 0
    matched = 0
    inserted = 0
    skipped_existing = 0
    no_supt = 0
    no_match = 0
    errors = 0
    unmatched_names = []

    total = len(dese_districts)

    for i, (orgcode, dese_name) in enumerate(dese_districts):
        if (i + 1) % 25 == 0 or i == 0:
            print(f"\nProgress: {i+1}/{total} (scraped={scraped}, matched={matched}, inserted={inserted})")

        try:
            contact = scrape_district_contact(client, orgcode)
            scraped += 1

            if not contact:
                no_supt += 1
                continue

            # Try to match to DB district
            norm_dese = normalize_name(dese_name)

            district_id = None
            db_name = None

            # Exact normalized match
            if norm_dese in db_lookup:
                district_id, db_name = db_lookup[norm_dese]
            else:
                # Try partial matching
                for db_norm, (did, dn) in db_lookup.items():
                    # Check if one contains the other
                    if norm_dese in db_norm or db_norm in norm_dese:
                        district_id, db_name = did, dn
                        break
                    # Try without "regional" variations
                    dese_clean = norm_dese.replace(' regional vocational technical', '').replace(' regional', '')
                    db_clean = db_norm.replace(' regional vocational technical', '').replace(' regional', '')
                    if dese_clean == db_clean:
                        district_id, db_name = did, dn
                        break

            if not district_id:
                no_match += 1
                if len(unmatched_names) < 30:
                    unmatched_names.append(dese_name)
                continue

            matched += 1

            # Skip if already exists
            if district_id in existing:
                skipped_existing += 1
                continue

            # Insert contact
            cur.execute("""
                INSERT INTO contacts (district_id, role, first_name, last_name, prefix, suffix, email, email_status, phone, confidence_score, do_not_contact)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                district_id,
                'superintendent',
                contact['first_name'],
                contact['last_name'],
                contact['prefix'],
                contact['suffix'],
                contact['email'],
                'unverified',
                contact['phone'],
                85,
                False,
            ))
            inserted += 1
            existing.add(district_id)

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error on {dese_name} ({orgcode}): {e}")

        # Small delay to be respectful
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    conn.commit()

    # Final stats
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Total DESE districts:      {total}")
    print(f"Successfully scraped:      {scraped}")
    print(f"No superintendent found:   {no_supt}")
    print(f"Matched to DB districts:   {matched}")
    print(f"No DB match:               {no_match}")
    print(f"Skipped (already exists):  {skipped_existing}")
    print(f"Inserted into contacts:    {inserted}")
    print(f"Errors:                    {errors}")

    if unmatched_names:
        print(f"\nSample unmatched DESE names ({len(unmatched_names)}):")
        for n in unmatched_names[:20]:
            print(f"  - {n}")

    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state = 'MA' AND c.role = 'superintendent'
    """)
    print(f"\nTotal MA superintendent contacts in DB: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    client.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
