"""Bulk import superintendent contacts for remaining states using state DOE websites."""
import httpx
from bs4 import BeautifulSoup
import psycopg2
import re
import csv
import io
import time

DB = dict(
    host='aws-0-us-west-2.pooler.supabase.com', port=6543, dbname='postgres',
    user='postgres.mymxwesilduzjfniecky', password='GdguFo6u90xogV9A', sslmode='require'
)
HEADERS = {"User-Agent": "Mozilla/5.0 (Education Research Tool)"}

def get_conn():
    return psycopg2.connect(**DB)

def parse_name(full_name):
    name = full_name.strip()
    prefix = None
    for p in ['Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Dr', 'Mr', 'Mrs', 'Ms']:
        if name.startswith(p + ' '):
            prefix = p if p.endswith('.') else p + '.'
            name = name[len(p):].strip()
            break

    if ',' in name:
        parts = name.split(',', 1)
        last_name = parts[0].strip()
        first_name = parts[1].strip()
    else:
        parts = name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
        elif len(parts) == 1:
            first_name = parts[0]
            last_name = ''
        else:
            return None

    if not first_name or not last_name:
        return None
    return {'first': first_name, 'last': last_name, 'prefix': prefix}

def insert_contact(cur, state, district_pattern, first, last, prefix=None, email=None, phone=None):
    try:
        cur.execute("""
            INSERT INTO contacts (district_id, role, first_name, last_name, prefix, email, phone, email_status, confidence_score)
            SELECT id, 'superintendent', %s, %s, %s, %s, %s, 'unverified', 80
            FROM districts WHERE UPPER(name) LIKE UPPER(%s) AND state = %s
            AND NOT EXISTS (SELECT 1 FROM contacts ct WHERE ct.district_id = districts.id AND ct.role = 'superintendent')
            LIMIT 1
        """, (first, last, prefix, email, phone, f"%{district_pattern}%", state))
        return cur.rowcount
    except:
        return 0

def insert_by_nces(cur, nces_id, first, last, prefix=None, email=None, phone=None):
    try:
        cur.execute("""
            INSERT INTO contacts (district_id, role, first_name, last_name, prefix, email, phone, email_status, confidence_score)
            SELECT id, 'superintendent', %s, %s, %s, %s, %s, 'unverified', 80
            FROM districts WHERE nces_id = %s
            AND NOT EXISTS (SELECT 1 FROM contacts ct WHERE ct.district_id = districts.id AND ct.role = 'superintendent')
        """, (first, last, prefix, email, phone, nces_id))
        return cur.rowcount
    except:
        return 0

def scrape_colorado():
    """Colorado CDE superintendent download."""
    print("CO: Trying CDE download...")
    try:
        resp = httpx.get("https://www.cde.state.co.us/cdereval/superintendentcontactinfo", headers=HEADERS, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return 0
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Look for download links
        links = soup.find_all('a', href=re.compile(r'\.(csv|xlsx|xls)', re.I))
        print(f"  CO: Found {len(links)} download links")
        for link in links:
            href = link.get('href', '')
            if not href.startswith('http'):
                href = 'https://www.cde.state.co.us' + href
            print(f"  CO: Trying {href}")
            try:
                dl = httpx.get(href, headers=HEADERS, timeout=30, follow_redirects=True)
                if dl.status_code == 200 and len(dl.content) > 100:
                    print(f"  CO: Downloaded {len(dl.content)} bytes")
                    return -1  # Signal we got data but need to parse
            except:
                continue
        return 0
    except Exception as e:
        print(f"  CO: Error - {e}")
        return 0

def scrape_generic_directory(state, url):
    """Try to scrape a generic state DOE superintendent directory page."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            print(f"  {state}: Status {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n")

        # Look for superintendent name patterns in text
        contacts = []
        lines = text.split('\n')

        email_pattern = re.compile(r'[\w\.\-]+@[\w\.\-]+\.\w+')
        phone_pattern = re.compile(r'\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}')

        current_district = None
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue

            emails = email_pattern.findall(line)
            phones = phone_pattern.findall(line)

            if emails or phones:
                # This line has contact info
                pass

        return contacts
    except Exception as e:
        print(f"  {state}: Error - {e}")
        return []

# State DOE directory URLs to try
STATE_URLS = {
    'OH': 'https://education.ohio.gov/Topics/Data/Ohio-Educational-Directory',
    'MI': 'https://www.michigan.gov/mde/services/school-performance-reports/ed-directory',
    'PA': 'https://www.education.pa.gov/DataAndReporting/Pages/EdNA.aspx',
    'AZ': 'https://www.azed.gov/finance/school-district-and-charter-school-directory',
    'MN': 'https://public.education.mn.gov/MdeOrgView/organization/show/superintendent',
    'WI': 'https://dpi.wi.gov/school-directory',
    'NC': 'https://www.dpi.nc.gov/districts-schools',
    'IA': 'https://educateiowa.gov/data-reporting/district-data',
    'AR': 'https://adedata.arkansas.gov/statewide/Districts/DistrictList.aspx',
    'CO': 'https://www.cde.state.co.us/cdereval/superintendentcontactinfo',
    'GA': 'https://www.gadoe.org/External-Affairs-and-Policy/communications/Pages/superintendent-list.aspx',
    'VA': 'https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/school-division-directory',
    'CT': 'https://portal.ct.gov/sde/directory/superintendent-directory',
}

def main():
    conn = get_conn()

    # Check which states still need contacts
    cur = conn.cursor()
    cur.execute("""
        SELECT d.state, COUNT(DISTINCT d.id) as districts, COUNT(DISTINCT c.id) as contacts
        FROM districts d LEFT JOIN contacts c ON c.district_id = d.id
        GROUP BY d.state HAVING COUNT(c.id) = 0
        ORDER BY COUNT(DISTINCT d.id) DESC
    """)
    remaining = cur.fetchall()
    print(f"States still needing contacts: {len(remaining)}")
    for r in remaining:
        print(f"  {r[0]}: {r[1]} districts")

    # Try each state DOE URL
    for state, url in STATE_URLS.items():
        print(f"\n--- {state} ---")
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
            print(f"  Status: {resp.status_code}, Size: {len(resp.text)}")

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Look for CSV/Excel download links
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    text = a.get_text(strip=True).lower()
                    if any(x in text for x in ['superintendent', 'directory', 'download', 'csv', 'excel']) or \
                       any(x in href.lower() for x in ['.csv', '.xlsx', '.xls']):
                        print(f"  Found link: {text[:60]} -> {href[:80]}")
        except Exception as e:
            print(f"  Error: {e}")

    conn.close()
    print("\nDone probing state DOE websites.")

if __name__ == '__main__':
    main()
