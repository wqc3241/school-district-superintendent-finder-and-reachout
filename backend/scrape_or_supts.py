import pdfplumber
import re
import psycopg2

pdf_path = r'C:\Users\wqc32\.claude\projects\C--githubrepo\d8ee8be5-3507-4a2a-a601-85ba786dfd36\tool-results\webfetch-1773768449923-5toqpw.pdf'
pdf = pdfplumber.open(pdf_path)

# Get all DB districts
conn = psycopg2.connect(host='aws-0-us-west-2.pooler.supabase.com', port=6543, dbname='postgres',
                        user='postgres.mymxwesilduzjfniecky', password='GdguFo6u90xogV9A', sslmode='require')
cur = conn.cursor()
cur.execute("SELECT id, name FROM districts WHERE state='OR'")
db_districts = {row[1]: row[0] for row in cur.fetchall()}
conn.close()

# Extract full text
all_text = ""
for i in range(11, 90):
    text = pdf.pages[i].extract_text()
    if text:
        all_text += text + "\n"

lines = all_text.split('\n')

# Find EVERY "Superintendent Name" line, then search backwards for district
pdf_entries = []

for i, line in enumerate(lines):
    stripped = line.strip()

    m = re.match(r'^Superintendent\s+(.+)', stripped)
    if not m:
        continue

    # Skip if previous non-empty line contains "Assistant" or "Deputy"
    skip = False
    for j in range(i-1, max(i-3, 0), -1):
        prev = lines[j].strip()
        if prev:
            if 'Assistant' in prev or 'Deputy' in prev:
                skip = True
            break
    if skip:
        continue

    name_part = m.group(1).strip()

    # Extract phone
    pm = re.search(r'(\d{3}[-\s]\d{3}[-\s]\d{4})', name_part)
    supt_phone = pm.group(1).replace(' ', '-') if pm else None
    name = name_part[:pm.start()].strip() if pm else name_part

    # Clean name
    name = re.sub(r'\s+(Fax|Institution|Grades|Business|Deputy|Admin|Career|Special|Assessment|Technology|Media|Activities|Child|Transportation|Facilities|Curriculum|Instruction|Safety|Human|Communications|PO Box|Principal|\d{3,}).*$', '', name, flags=re.IGNORECASE)
    name = name.strip()

    if not name or len(name) < 3 or len(name) > 40:
        continue

    # Search backwards for district
    dist_name = None
    dist_phone = None
    dist_email = None

    for j in range(i-1, max(i-15, 0), -1):
        dl = lines[j].strip()
        dm = re.search(r'(\S+(?:\s+\S+)*?\s+(?:SD|ESD)\s+\S+)\s+(\d{3}-\d{3}-\d{4})', dl)
        if dm:
            dist_name = dm.group(1).strip()
            dist_phone = dm.group(2)
            for k in range(j+1, i):
                em = re.search(r'([\w.+-]+@[\w.-]+\.\w+)', lines[k])
                if em:
                    dist_email = em.group(1)
                    break
            break

    if dist_name:
        pdf_entries.append({
            'raw_district': dist_name,
            'superintendent': name,
            'phone': supt_phone or dist_phone,
            'email': dist_email,
            'line': i
        })

print(f"Found {len(pdf_entries)} superintendent entries from PDF")

# Build lookup indices
def normalize(s):
    return re.sub(r'\s+', ' ', s.lower().strip())

db_by_norm = {}
db_by_suffix = {}
for name, uid in db_districts.items():
    n = normalize(name)
    db_by_norm[n] = (name, uid)
    sm = re.search(r'((?:SD|ESD)\s+\S+)', name, re.IGNORECASE)
    if sm:
        suffix = normalize(sm.group(1))
        if suffix not in db_by_suffix:
            db_by_suffix[suffix] = []
        db_by_suffix[suffix].append((name, uid))

# Manual fixes for truncated names from PDF multi-column layout
manual_map = {
    'Eagle SD 61': 'Pine Eagle SD 61',
    'River SD 35': 'Molalla River SD 35',
    'Harbor SD 17C': 'Brookings-Harbor SD 17C',
    'Curry SD 1': 'Central Curry SD 1',
    'Pine Admin SD 1': 'Bend-LaPine Administrative SD 1',
    'Valley SD 21J': 'Camas Valley SD 21J',
    'County SD 15': 'Days Creek SD 15',
    'Umpqua SD 19': 'South Umpqua SD 19',
    'Day SD 3': 'John Day SD 3',
    'City SD 4': 'Prairie City SD 4',
    'County SD 3': 'Harney County SD 3',
    'Creek SD 5': 'Pine Creek SD 5',
    'Point SD 6': 'Central Point SD 6',
    'Talent SD 4': 'Phoenix-Talent SD 4',
    'Butte SD 41': 'Black Butte SD 41',
    'County SD 509J': 'Jefferson County SD 509J',
    'County SD 7': 'Lake County SD 7',
    'Ridge SD 28J': 'Fern Ridge SD 28J',
    'City SD 69': 'Junction City SD 69',
    'Adams Springfield SD 19': 'Springfield SD 19',
    'Linn SD 552': 'Central Linn SD 552',
    'Community SD 9': 'Lebanon Community SD 9',
    'Home SD 55': 'Sweet Home SD 55',
    'Valley SD 3': 'Jordan Valley SD 3',
    'Angel SD 91': 'Mt Angel SD 91',
    'Paul SD 45': 'St Paul SD 45',
    'Barlow SD 10J': 'Gresham-Barlow SD 10J',
    'Weston SD 29RJ': 'Athena-Weston SD 29RJ',
    'Tualatin SD 23J': 'Tigard-Tualatin SD 23J',
    'Jay Mathisen Grants Pass SD 7': 'Grants Pass SD 7',
    'Clackamas SD 12': 'North Clackamas SD 12',
    'Douglas SD 22': 'North Douglas SD 22',
    'Douglas SD 40': 'David Douglas SD 40',
    'Lake SD 14': 'North Lake SD 14',
    'Lane SD 45J3': 'South Lane SD 45J3',
    'Kenzie SD 68': 'McKenzie SD 68',
    'Minnville SD 40': 'McMinnville SD 40',
    'Wasco County SD 21': 'North Wasco County SD 21',
    'Mayfield Elem North Powder SD 8J': 'North Powder SD 8J',
    'Young Elem Yamhill Carlton SD 1': 'Yamhill Carlton SD 1',
    'Assistant Barb Carr Coos Bay SD 9': 'Coos Bay SD 9',
    'Assistant Gina Blanchette 541-923-5437 Sisters SD 6': 'Sisters SD 6',
    'County SD 4': 'Douglas County SD 4',
}

# Process and deduplicate
final_entries = {}

for entry in pdf_entries:
    raw = entry['raw_district']
    n = normalize(raw)
    matched_name = None
    matched_id = None

    # Direct match
    if n in db_by_norm:
        matched_name, matched_id = db_by_norm[n]

    # Manual map
    if not matched_name and raw in manual_map:
        target = manual_map[raw]
        tn = normalize(target)
        if tn in db_by_norm:
            matched_name, matched_id = db_by_norm[tn]

    # Suffix match (unique)
    if not matched_name:
        sm = re.search(r'((?:SD|ESD)\s+\S+)', raw, re.IGNORECASE)
        if sm:
            suffix = normalize(sm.group(1))
            if suffix in db_by_suffix and len(db_by_suffix[suffix]) == 1:
                matched_name, matched_id = db_by_suffix[suffix][0]

    if matched_name and matched_name not in final_entries:
        # Clean superintendent name
        name = entry['superintendent']
        for pattern in [
            r'\s+\d+\s+\w+\s+St.*$',
            r'\s+\w+,\s+OR.*$',
            r'\s+PO\s+Box.*$',
            r'\s+Institution.*$',
            r'\s+Assessment.*$',
            r'\s+Oak\s+Heights.*$',
            r'\s+Facilities.*$',
            r'\s+Lane\s+Education.*$',
            r'\s+Grants\s+Pass.*$',
            r'\s+WASHINGTON.*$',
            r'\s+Roseburg.*$',
            r'\s+Tigard.*$',
            r'\s+Aurora.*$',
            r'\s+Nyssa.*$',
            r'\s+Project\s+Di.*$',
        ]:
            name = re.sub(pattern, '', name)
        name = name.strip()

        final_entries[matched_name] = {
            'db_name': matched_name,
            'db_id': matched_id,
            'superintendent': name,
            'phone': entry['phone'],
            'email': entry['email'],
            'raw': raw
        }

print(f"\nFinal matched entries: {len(final_entries)}")

# Show unmatched raw districts
matched_raws = {e['raw'] for e in final_entries.values()}
unmatched = [e for e in pdf_entries if e['raw_district'] not in matched_raws]
# Deduplicate unmatched
seen_raw = set()
unmatched_dedup = []
for e in unmatched:
    if e['raw_district'] not in seen_raw:
        seen_raw.add(e['raw_district'])
        # Check if this district name (after manual map) is already in final_entries
        raw = e['raw_district']
        if raw in manual_map:
            target = manual_map[raw]
            if target in final_entries:
                continue
        unmatched_dedup.append(e)

print(f"Still unmatched: {len(unmatched_dedup)}")
for u in unmatched_dedup:
    print(f"  RAW: {u['raw_district']:50s} | {u['superintendent']}")

# Split names into first/last
print("\n--- Final data to insert ---")
records = []
for e in sorted(final_entries.values(), key=lambda x: x['db_name']):
    name = e['superintendent']
    parts = name.split()
    if len(parts) >= 2:
        first = parts[0]
        last = ' '.join(parts[1:])
        # Handle prefixes
        prefix = None
        if first in ('Dr.', 'Dr'):
            prefix = 'Dr.'
            first = parts[1] if len(parts) > 2 else ''
            last = ' '.join(parts[2:]) if len(parts) > 2 else parts[1]
    elif len(parts) == 1:
        first = parts[0]
        last = ''
    else:
        continue

    # Handle middle initials - keep in first name or move to last
    # e.g., "Carter L Wells" -> first="Carter", last="L Wells" - actually let's keep middle initial with last
    # Actually standard: first=Carter, last=Wells, middle initial is middle
    # Keep simple: first word = first, rest = last

    records.append({
        'district_id': e['db_id'],
        'db_name': e['db_name'],
        'first_name': first,
        'last_name': last,
        'email': e['email'],
        'phone': e['phone'],
    })
    print(f"  {e['db_name']:45s} | {first:15s} {last:20s} | {str(e['email']):45s} | {e['phone']}")

print(f"\nTotal records to insert: {len(records)}")

# Insert into contacts table
conn = psycopg2.connect(host='aws-0-us-west-2.pooler.supabase.com', port=6543, dbname='postgres',
                        user='postgres.mymxwesilduzjfniecky', password='GdguFo6u90xogV9A', sslmode='require')
cur = conn.cursor()

inserted = 0
skipped = 0
errors = 0

for rec in records:
    # Check if superintendent contact already exists for this district
    cur.execute("""
        SELECT id FROM contacts
        WHERE district_id = %s AND role = 'superintendent'
    """, (rec['district_id'],))

    if cur.fetchone():
        skipped += 1
        continue

    try:
        cur.execute("""
            INSERT INTO contacts (district_id, role, first_name, last_name, email, email_status, phone, confidence_score, do_not_contact)
            VALUES (%s, 'superintendent', %s, %s, %s, 'unverified', %s, 85, false)
        """, (rec['district_id'], rec['first_name'], rec['last_name'], rec['email'], rec['phone']))
        inserted += 1
    except Exception as ex:
        print(f"  ERROR inserting {rec['db_name']}: {ex}")
        conn.rollback()
        errors += 1

conn.commit()
conn.close()

print(f"\n=== RESULTS ===")
print(f"Districts matched from PDF: {len(final_entries)}")
print(f"Contacts inserted: {inserted}")
print(f"Contacts skipped (already exist): {skipped}")
print(f"Errors: {errors}")
print(f"Total OR districts in DB: {len(db_districts)}")
print(f"Coverage: {len(final_entries)}/{len(db_districts)} = {len(final_entries)/len(db_districts)*100:.1f}%")
