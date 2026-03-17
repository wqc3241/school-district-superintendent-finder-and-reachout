"""
Scrape superintendent contacts for 22 remaining U.S. states/territories
and insert into Supabase PostgreSQL contacts table.

States: MS, ID, NM, AL, MD, WV, TN, KY, WY, RI, HI, AK, DE, DC, PR, VI, GU, AS, MP, BI, NV, UT
"""

import httpx
from bs4 import BeautifulSoup
import psycopg2
import re
import time
import traceback
import io
import csv
import json

DB_CONFIG = {
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': 6543,
    'dbname': 'postgres',
    'user': 'postgres.mymxwesilduzjfniecky',
    'password': 'GdguFo6u90xogV9A',
    'sslmode': 'require',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

TIMEOUT = 30


def parse_name(full_name):
    """Parse a full name into prefix, first_name, last_name, suffix."""
    full_name = full_name.strip()
    if not full_name:
        return None, '', '', None

    # Remove prefixes
    prefix = None
    for p in ['Dr. ', 'Dr ', 'Mr. ', 'Mr ', 'Mrs. ', 'Mrs ', 'Ms. ', 'Ms ', 'Rev. ', 'Rev ']:
        if full_name.startswith(p):
            prefix = p.strip().rstrip('.')
            full_name = full_name[len(p):].strip()
            break

    # Remove suffixes
    suffix = None
    for s in [', Ed.D.', ', Ph.D.', ', Ed.D', ', Ph.D', ' Ed.D.', ' Ph.D.',
              ' Jr.', ' Jr', ' Sr.', ' Sr', ' III', ' II', ' IV']:
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
        return prefix, parts[0], parts[-1], suffix


def normalize_district_name(name):
    """Create normalized version for matching."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [' public schools', ' public school district', ' school district',
                   ' school dept', ' school department', ' schools', ' sd',
                   ' county schools', ' city schools', ' independent school district',
                   ' consolidated school district', ' municipal school district',
                   ' unified school district', ' union free school district',
                   ' central school district', ' community school district',
                   ' area school district', ' local school district',
                   ' school division', ' school system',
                   ' board of education', ' county board of education',
                   ' city board of education']:
        if name.endswith(suffix):
            name = name[:-(len(suffix))]
            break
    # Remove parenthetical qualifiers
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    # Remove 'county' at end if it's a county school system
    return name


def match_district(scraped_name, db_lookup):
    """Try to match a scraped district name to the database."""
    norm = normalize_district_name(scraped_name)

    # Exact match
    if norm in db_lookup:
        return db_lookup[norm]

    # Try with 'county' appended/removed
    if not norm.endswith(' county'):
        test = norm + ' county'
        if test in db_lookup:
            return db_lookup[test]
    else:
        test = norm.replace(' county', '').strip()
        if test in db_lookup:
            return db_lookup[test]

    # Substring matching
    for db_norm, val in db_lookup.items():
        if norm in db_norm or db_norm in norm:
            return val
        # Handle 'city' vs 'county' variants
        if norm.replace(' city', '') == db_norm.replace(' city', '').replace(' county', ''):
            return val

    return None


def get_db_districts(cur, state):
    """Get districts for a state from database, build lookup."""
    cur.execute("SELECT id, name FROM districts WHERE state = %s", (state,))
    rows = cur.fetchall()
    lookup = {}
    for did, dname in rows:
        norm = normalize_district_name(dname)
        lookup[norm] = (did, dname)
    return lookup, len(rows)


def get_existing_contacts(cur, state):
    """Get existing superintendent contacts for a state."""
    cur.execute("""
        SELECT c.district_id FROM contacts c
        JOIN districts d ON c.district_id = d.id
        WHERE d.state = %s AND c.role = 'superintendent'
    """, (state,))
    return set(row[0] for row in cur.fetchall())


def insert_contact(cur, district_id, first_name, last_name, prefix=None, suffix=None,
                   email=None, phone=None, confidence=80):
    """Insert a superintendent contact."""
    cur.execute("""
        INSERT INTO contacts (district_id, role, first_name, last_name, prefix, suffix,
                              email, email_status, phone, confidence_score, do_not_contact)
        VALUES (%s, 'superintendent', %s, %s, %s, %s, %s, 'unverified', %s, %s, false)
    """, (district_id, first_name, last_name, prefix, suffix, email, phone, confidence))


# ============================================================================
# STATE-SPECIFIC SCRAPERS
# ============================================================================

def scrape_ms(client, cur):
    """Mississippi - try MDE website."""
    records = []

    # Try the Mississippi school district superintendent page
    urls_to_try = [
        'https://mdek12.org/accred/school-district-contacts',
        'https://www.mdek12.org/OAE/School-District-Contacts',
        'https://mdek12.org/accred/superintendent-contacts',
    ]

    for url in urls_to_try:
        try:
            resp = client.get(url, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Look for tables or structured data
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # skip header
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            district = cells[0].get_text(strip=True)
                            name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            email = ''
                            phone = ''
                            # Look for email links
                            for a in row.find_all('a', href=True):
                                if 'mailto:' in a['href']:
                                    email = a['href'].replace('mailto:', '').strip()
                            if len(cells) > 2:
                                for c in cells[2:]:
                                    txt = c.get_text(strip=True)
                                    if '@' in txt and not email:
                                        email = txt
                                    elif re.match(r'[\d\(\)\-\.\s]{7,}', txt):
                                        phone = txt
                            if district and name:
                                prefix, first, last, suffix = parse_name(name)
                                records.append({
                                    'district': district, 'first_name': first, 'last_name': last,
                                    'prefix': prefix, 'suffix': suffix, 'email': email, 'phone': phone
                                })
                if records:
                    break
        except Exception:
            continue

    return records


def scrape_id(client, cur):
    """Idaho - try SDE website."""
    records = []

    urls_to_try = [
        'https://www.sde.idaho.gov/topics/superintendent-list/',
        'https://sde.idaho.gov/superintendent-directory/',
        'https://sde.idaho.gov/communications/superintendent-directory.html',
    ]

    for url in urls_to_try:
        try:
            resp = client.get(url, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:]:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            district = cells[0].get_text(strip=True)
                            name = cells[1].get_text(strip=True)
                            email = ''
                            phone = ''
                            for a in row.find_all('a', href=True):
                                if 'mailto:' in a['href']:
                                    email = a['href'].replace('mailto:', '').strip()
                            for c in cells[2:]:
                                txt = c.get_text(strip=True)
                                if '@' in txt and not email:
                                    email = txt
                                elif re.match(r'[\d\(\)\-\.\s]{7,}', txt):
                                    phone = txt
                            if district and name:
                                prefix, first, last, suffix = parse_name(name)
                                records.append({
                                    'district': district, 'first_name': first, 'last_name': last,
                                    'prefix': prefix, 'suffix': suffix, 'email': email, 'phone': phone
                                })
                if records:
                    break
        except Exception:
            continue

    return records


def scrape_md(client, cur):
    """Maryland - hardcoded from successful WebFetch scrape."""
    return [
        {'district': 'Allegany County Public Schools', 'first_name': 'Michael', 'last_name': 'Martirano', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 759-2038'},
        {'district': 'Anne Arundel County Public Schools', 'first_name': 'Mark', 'last_name': 'Bedell', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 222-5303'},
        {'district': 'Baltimore City Public Schools', 'first_name': 'Sonja', 'last_name': 'Santelises', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 396-8803'},
        {'district': 'Baltimore County Public Schools', 'first_name': 'Myriam', 'last_name': 'Rogers', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(443) 809-4281'},
        {'district': 'Calvert County Public Schools', 'first_name': 'Marcus', 'last_name': 'Newsome', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(443) 550-8009'},
        {'district': 'Caroline County Public Schools', 'first_name': 'Derek', 'last_name': 'Simmons', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 479-1460'},
        {'district': 'Carroll County Public Schools', 'first_name': 'Cynthia', 'last_name': 'McCabe', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 751-3128'},
        {'district': 'Cecil County Public Schools', 'first_name': 'Jeffrey', 'last_name': 'Lawson', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 996-5499'},
        {'district': 'Charles County Public Schools', 'first_name': 'Maria', 'last_name': 'Navarro', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 934-7223'},
        {'district': 'Dorchester County Public Schools', 'first_name': 'Jymil', 'last_name': 'Thompson', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 221-1111'},
        {'district': 'Frederick County Public Schools', 'first_name': 'Cheryl', 'last_name': 'Dyson', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 696-6910'},
        {'district': 'Garrett County Public Schools', 'first_name': 'Brenda', 'last_name': 'McCartney', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 334-8901'},
        {'district': 'Harford County Public Schools', 'first_name': 'Dyann', 'last_name': 'Mack', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 588-5204'},
        {'district': 'Howard County Public Schools', 'first_name': 'William', 'last_name': 'Barnes', 'prefix': 'Mr', 'suffix': None, 'email': '', 'phone': '(410) 313-6677'},
        {'district': 'Kent County Public Schools', 'first_name': 'Mary', 'last_name': 'Boswell-McComas', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 778-7113'},
        {'district': 'Montgomery County Public Schools', 'first_name': 'Thomas', 'last_name': 'Taylor', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(240) 740-3020'},
        {'district': "Prince George's County Public Schools", 'first_name': 'Shawn', 'last_name': 'Joseph', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 952-6008'},
        {'district': "Queen Anne's County Public Schools", 'first_name': 'Matthew', 'last_name': 'Kibler', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 758-2403'},
        {'district': "St. Mary's County Public Schools", 'first_name': 'James', 'last_name': 'Smith', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 475-5511'},
        {'district': 'Somerset County Public Schools', 'first_name': 'David', 'last_name': 'Bromwell', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 651-1616'},
        {'district': 'Talbot County Public Schools', 'first_name': 'Sharon', 'last_name': 'Pepukayi', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 822-0330'},
        {'district': 'Washington County Public Schools', 'first_name': 'David', 'last_name': 'Sovine', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(301) 766-2815'},
        {'district': 'Wicomico County Public Schools', 'first_name': 'Micah', 'last_name': 'Stauffer', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 677-4495'},
        {'district': 'Worcester County Public Schools', 'first_name': 'Annette', 'last_name': 'Wallace', 'prefix': 'Dr', 'suffix': None, 'email': '', 'phone': '(410) 632-5020'},
    ]


def scrape_wv(client, cur):
    """West Virginia - hardcoded from successful Excel download."""
    raw = """Barbour|Mr.|Eddie Vincent|edvincen@k12.wv.us|(304)457-3030
Berkeley|Dr.|Ryan Saxe|rsaxe@k12.wv.us|(304)267-3500
Boone|Mr.|Allen Sexton|asexton@k12.wv.us|(304)369-3131
Braxton|Dr.|Donna Burge-Tetrick|dtetrick@k12.wv.us|(304)765-7101
Brooke|Dr.|Jeffrey Crook|jcrook@k12.wv.us|(304)737-3481
Cabell|Mr.|Tim Hardesty|thardest@k12.wv.us|(304)528-5000
Calhoun|Mr.|Michael Fitzwater|mfitzwater@k12.wv.us|(304)354-7011
Clay|Mr.|Phil Dobbins|philip.dobbins@k12.wv.us|(304)587-4266
Doddridge|Dr.|Adam Cheeseman|acheeseman@k12.wv.us|(304)873-2300
Fayette|Mr.|David Warvel|dwarvel@k12.wv.us|(304)574-1176
Gilmer|Dr.|Tony Minney|tdminney@k12.wv.us|(304)462-7386
Grant|Mr.|Mitch Webster|mwebster@k12.wv.us|(304)257-1011
Greenbrier|Mr.|Jeffrey A. Bryant|jbryant@k12.wv.us|(304)647-6470
Hampshire|Mr.|George R. Collett|gcollett@k12.wv.us|(304)822-3528
Hancock|Mr.|Walter Saunders|wsaunder@k12.wv.us|(304)564-3411
Hardy|Dr.|Sheena VanMeter|srvanmet@k12.wv.us|(304)530-2348
Harrison|Ms.|Dora Stutler|dstutler@k12.wv.us|(304)326-7300
Jackson|Mr.|William P. Hosaflook|whosaflo@k12.wv.us|(304)372-7300
Jefferson|Dr.|William Bishop|chuck.bishop@k12.wv.us|(304)725-9741
Kanawha|Dr.|Paula Potter|ppotter@mail.kana.k12.wv.us|(304)348-7770
Lewis|Ms.|Carolyn Long|carolyn.long@k12.wv.us|(304)269-8300
Lincoln|Mr.|Frank Barnett|flbarnet@k12.wv.us|(304)824-3033
Logan|Dr.|Sonya White|snjwhite@k12.wv.us|(304)792-2060
Marion|Dr.|Donna Heston|donna.heston@k12.wv.us|(304)367-2100
Marshall|Dr.|Shelby Haines|shaines@k12.wv.us|(304)843-4400
Mason|Ms.|Melissa Farmer|mfarmer@k12.wv.us|(304)675-4540
McDowell|Dr.|Ingrida Barker|ibarker@k12.wv.us|(304)436-8441
Mercer|Mr.|Ed Toman|etoman@k12.wv.us|(304)487-1551
Mineral|Mr.|Troy Ravenscroft|tlravenscroft@k12.wv.us|(304)788-4200
Mingo|Dr.|Joetta Basile|jsbasile@k12.wv.us|(304)235-3333
Monongalia|Dr.|Eddie Campbell|ecampbell@k12.wv.us|(304)291-9210
Monroe|Dr.|Jason Conaway|jconaway@k12.wv.us|(304)772-3094
Morgan|Mr.|David Banks|dbanks@k12.wv.us|(304)258-2430
Nicholas|Mr.|Scott Cochran|scochran@k12.wv.us|(304)872-3611
Ohio|Dr.|Kimberly Miller|ksmiller@k12.wv.us|(304)243-0300
Pendleton|Mrs.|Nicole Hevener|nhevener@k12.wv.us|(304)358-2207
Pleasants|Mr.|Michael Wells|gwells@k12.wv.us|(304)684-2215
Pocahontas|Dr.|Leatha Williams|lgwillia@k12.wv.us|(304)799-4505
Preston|Mr.|Brad Martin|brrmarti@k12.wv.us|(304)329-0580
Putnam|Mr.|John G. Hudson|jghudson@k12.wv.us|(304)586-0500
Raleigh|Dr.|Serena Starcher|slstarch@k12.wv.us|(304)256-4500
Randolph|Dr.|Shawn Dilly|sdilly@k12.wv.us|(304)636-9150
Ritchie|Ms.|April Haught|ahaught@k12.wv.us|(304)643-2991
Roane|Ms.|Michelle Stellato|michelle.stellato@k12.wv.us|(304)927-6400
Summers|Dr.|Linda Knott|lknott@k12.wv.us|(304)466-6000
Taylor|Dr.|John Stallings|john.stallings@k12.wv.us|(304)265-2497
Tucker|Ms.|Alicia Lambert|arlambert@k12.wv.us|(304)478-2771
Tyler|Mr.|Shane Highley|ahighley@k12.wv.us|(304)758-2145
Upshur|Mrs.|Christine Miller|cemiller@k12.wv.us|(304)472-5480
Wayne|Mr.|Todd Alexander|talexand@k12.wv.us|(304)272-5113
Webster|Mr.|Joseph Arbogast|jarbogast@k12.wv.us|(304)847-5638
Wetzel|Ms.|Cassandra Porter|crporter@k12.wv.us|(304)455-2441
Wirt|Mr.|John McKown|jmckown@k12.wv.us|(304)275-4279
Wood|Ms.|Christie Willis|cwillis@k12.wv.us|(304)420-9663
Wyoming|Mr.|Johnathan Henry|jjhenry@k12.wv.us|(304)732-6262"""

    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 5:
            county, title, full_name, email, phone = parts
            name_parts = full_name.strip().split()
            prefix = title.strip().rstrip('.')
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[-1] if len(name_parts) > 1 else ''
            records.append({
                'district': county.strip() + ' County Schools',
                'first_name': first_name, 'last_name': last_name,
                'prefix': prefix, 'suffix': None,
                'email': email.strip(), 'phone': phone.strip()
            })
    return records


def scrape_generic_table(client, urls, state_name):
    """Generic scraper that tries to find superintendent tables on given URLs."""
    records = []
    for url in urls:
        try:
            resp = client.get(url, timeout=TIMEOUT, follow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Look for tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 3:
                    continue
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        texts = [c.get_text(strip=True) for c in cells]
                        district = texts[0]
                        name = texts[1] if len(texts) > 1 else ''
                        email = ''
                        phone = ''
                        for a in row.find_all('a', href=True):
                            if 'mailto:' in a['href']:
                                email = a['href'].replace('mailto:', '').strip()
                        for t in texts[2:]:
                            if '@' in t and not email:
                                email = t
                            elif re.match(r'[\d\(\)\-\.\s]{7,}', t):
                                phone = t
                        if district and name and len(name) > 3:
                            prefix, first, last, suffix = parse_name(name)
                            records.append({
                                'district': district, 'first_name': first, 'last_name': last,
                                'prefix': prefix, 'suffix': suffix, 'email': email, 'phone': phone
                            })
            if records:
                break

            # Look for dl/dt/dd pattern
            dls = soup.find_all('dl')
            for dl in dls:
                dts = dl.find_all('dt')
                dds = dl.find_all('dd')
                for dt, dd in zip(dts, dds):
                    district = dt.get_text(strip=True)
                    name = dd.get_text(strip=True)
                    if district and name:
                        prefix, first, last, suffix = parse_name(name)
                        records.append({
                            'district': district, 'first_name': first, 'last_name': last,
                            'prefix': prefix, 'suffix': suffix, 'email': '', 'phone': ''
                        })
            if records:
                break

        except Exception as e:
            continue

    return records


def scrape_al(client, cur):
    """Alabama"""
    return scrape_generic_table(client, [
        'https://alabamaachieves.org/school-systems/',
        'https://www.alsde.edu/Contacts/Superintendents',
        'https://www.alabamaachieves.org/superintendent-directory/',
    ], 'Alabama')


def scrape_nm(client, cur):
    """New Mexico"""
    return scrape_generic_table(client, [
        'https://webnew.ped.state.nm.us/bureaus/superintendent-directory/',
        'https://newmexico.schoolmint.net/schoolfinder',
    ], 'New Mexico')


def scrape_tn(client, cur):
    """Tennessee"""
    return scrape_generic_table(client, [
        'https://schooldirectory.tn.gov/',
        'https://www.tn.gov/education/districts/lea-superintendent-directory.html',
        'https://www.tn.gov/education/districts.html',
    ], 'Tennessee')


def scrape_ky(client, cur):
    """Kentucky"""
    records = []
    # Try KDE superintendent directory
    urls = [
        'https://education.ky.gov/districts/Pages/Superintendents.aspx',
        'https://education.ky.gov/districts/endir/Pages/District-Superintendents.aspx',
        'https://applications.education.ky.gov/SRC/',
    ]
    return scrape_generic_table(client, urls, 'Kentucky')


def scrape_wy(client, cur):
    """Wyoming"""
    return scrape_generic_table(client, [
        'https://edu.wyoming.gov/school-districts/',
        'https://portals.edu.wyoming.gov/wyedpro/Pages/OnlineDirectory/OnlineDirectoryBreadCrumb.aspx',
    ], 'Wyoming')


def scrape_ri(client, cur):
    """Rhode Island"""
    return scrape_generic_table(client, [
        'https://www.ride.ri.gov/InsideRIDE/RISchoolDistricts.aspx',
        'https://www.ride.ri.gov/InformationAccountability/RIEducationData/SchoolDistrictInformation.aspx',
    ], 'Rhode Island')


def scrape_hi(client, cur):
    """Hawaii - single district state."""
    return [{
        'district': 'Hawaii Department of Education',
        'first_name': 'Keith', 'last_name': 'Hayashi',
        'prefix': None, 'suffix': None,
        'email': '', 'phone': '(808) 586-3230'
    }]


def scrape_ak(client, cur):
    """Alaska"""
    return scrape_generic_table(client, [
        'https://education.alaska.gov/SchoolDistricts',
        'https://education.alaska.gov/directory',
    ], 'Alaska')


def scrape_de(client, cur):
    """Delaware"""
    return scrape_generic_table(client, [
        'https://education.delaware.gov/community/district-school-information/',
        'https://www.doe.k12.de.us/domain/175',
    ], 'Delaware')


def scrape_dc(client, cur):
    """DC - single main district."""
    return [{
        'district': 'District of Columbia Public Schools',
        'first_name': 'Lewis', 'last_name': 'Ferebee',
        'prefix': 'Dr', 'suffix': None,
        'email': 'lewis.ferebee@k12.dc.gov', 'phone': '(202) 442-5885'
    }]


def scrape_nv(client, cur):
    """Nevada"""
    return scrape_generic_table(client, [
        'https://doe.nv.gov/SchoolDistricts/',
        'https://www.doe.nv.gov/SchoolDistricts/About/',
    ], 'Nevada')


def scrape_ut(client, cur):
    """Utah"""
    return scrape_generic_table(client, [
        'https://www.schools.utah.gov/superintendents',
        'https://www.schools.utah.gov/data/reports?menu=schooldirectory',
    ], 'Utah')


def scrape_territory(client, cur, state):
    """Generic territory scraper - these are expected to mostly fail."""
    return []


# ============================================================================
# URBAN INSTITUTE API FALLBACK
# ============================================================================

def try_urban_institute(client, fips, state):
    """Try Urban Institute API to get district list (no superintendent names though)."""
    # The Urban Institute API doesn't have superintendent names,
    # but we can use it to verify districts exist
    try:
        url = f'https://educationdata.urban.org/api/v1/school-districts/ccd/directory/2022/?fips={fips:02d}'
        resp = client.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('results', [])
            return [(r.get('lea_name', ''), r.get('leaid', ''), r.get('phone', ''))
                    for r in results if r.get('lea_name')]
    except Exception:
        pass
    return []


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_state(client, cur, conn, state, scraper_func, fips=None):
    """Process a single state: scrape, match, insert."""
    start_time = time.time()

    # Get existing DB data
    db_lookup, total_districts = get_db_districts(cur, state)
    existing = get_existing_contacts(cur, state)

    if total_districts == 0:
        print(f"  {state}: No districts in database, skipping")
        return 0, total_districts

    # Try state-specific scraper
    print(f"  {state}: Scraping... ({total_districts} districts in DB, {len(existing)} existing contacts)")
    records = []
    try:
        records = scraper_func(client, cur)
    except Exception as e:
        print(f"  {state}: Scraper error: {e}")

    elapsed = time.time() - start_time
    if elapsed > 180:  # 3 minute limit
        print(f"  {state}: Time limit reached ({elapsed:.0f}s)")

    if not records:
        print(f"  {state}: No records scraped from state DOE")

    # Match and insert
    inserted = 0
    for rec in records:
        district_match = match_district(rec['district'], db_lookup)
        if not district_match:
            continue

        district_id, db_name = district_match

        # Skip if already exists
        if district_id in existing:
            continue

        # Skip empty names
        if not rec['first_name'] and not rec['last_name']:
            continue

        try:
            insert_contact(
                cur, district_id,
                rec['first_name'], rec['last_name'],
                rec.get('prefix'), rec.get('suffix'),
                rec.get('email') or None, rec.get('phone') or None,
                80
            )
            existing.add(district_id)
            inserted += 1
        except Exception as e:
            print(f"  {state}: Insert error for {rec['district']}: {e}")
            conn.rollback()
            continue

    conn.commit()
    pct = (inserted / total_districts * 100) if total_districts > 0 else 0
    print(f"  {state}: {inserted} contacts inserted / {total_districts} districts ({pct:.0f}%)")
    return inserted, total_districts


def main():
    print("=" * 70)
    print("Superintendent Contact Scraper - 22 States/Territories")
    print("=" * 70)

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    client = httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT,
        headers=HEADERS,
        verify=False  # Some state sites have cert issues
    )

    # State configurations: (state_code, scraper_function, FIPS code)
    states = [
        ('MS', scrape_ms, 28),
        ('ID', scrape_id, 16),
        ('NM', scrape_nm, 35),
        ('AL', scrape_al, 1),
        ('MD', scrape_md, 24),
        ('WV', scrape_wv, 54),
        ('TN', scrape_tn, 47),
        ('KY', scrape_ky, 21),
        ('WY', scrape_wy, 56),
        ('RI', scrape_ri, 44),
        ('HI', scrape_hi, 15),
        ('AK', scrape_ak, 2),
        ('DE', scrape_de, 10),
        ('DC', scrape_dc, 11),
        ('PR', lambda c, cu: scrape_territory(c, cu, 'PR'), 72),
        ('VI', lambda c, cu: scrape_territory(c, cu, 'VI'), None),
        ('GU', lambda c, cu: scrape_territory(c, cu, 'GU'), None),
        ('AS', lambda c, cu: scrape_territory(c, cu, 'AS'), None),
        ('MP', lambda c, cu: scrape_territory(c, cu, 'MP'), None),
        ('BI', lambda c, cu: scrape_territory(c, cu, 'BI'), None),
        ('NV', scrape_nv, 32),
        ('UT', scrape_ut, 49),
    ]

    results = []
    total_inserted = 0
    total_districts = 0

    for state_code, scraper, fips in states:
        try:
            inserted, districts = process_state(client, cur, conn, state_code, scraper, fips)
            results.append((state_code, inserted, districts))
            total_inserted += inserted
            total_districts += districts
        except Exception as e:
            print(f"  {state_code}: FAILED - {e}")
            traceback.print_exc()
            results.append((state_code, 0, 0))
            conn.rollback()

    # Summary table
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'State':<6} {'Inserted':>10} {'Districts':>10} {'Coverage':>10}")
    print("-" * 40)
    for state_code, inserted, districts in results:
        pct = f"{inserted/districts*100:.0f}%" if districts > 0 else "N/A"
        print(f"{state_code:<6} {inserted:>10} {districts:>10} {pct:>10}")
    print("-" * 40)
    print(f"{'TOTAL':<6} {total_inserted:>10} {total_districts:>10}")

    # Final verification
    print("\n--- Final DB Verification ---")
    for state_code, _, _ in results:
        cur.execute("""
            SELECT COUNT(*) FROM contacts c
            JOIN districts d ON c.district_id = d.id
            WHERE d.state = %s AND c.role = 'superintendent'
        """, (state_code,))
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  {state_code}: {count} superintendent contacts in DB")

    cur.close()
    conn.close()
    client.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
