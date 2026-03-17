"""
Fix district matching for states where abbreviations prevented matches.
Handles cases like 'ATTALA CO SCHOOL DIST' -> 'Attala County School District'
"""
import psycopg2
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_CONFIG = {
    'host': 'aws-0-us-west-2.pooler.supabase.com',
    'port': 6543,
    'dbname': 'postgres',
    'user': 'postgres.mymxwesilduzjfniecky',
    'password': 'GdguFo6u90xogV9A',
    'sslmode': 'require',
}


def expanded_normalize(name):
    """Aggressive normalization that handles NCES abbreviations."""
    n = name.lower().strip()
    # Expand common abbreviations
    n = re.sub(r'\bco\b\.?', 'county', n)
    n = re.sub(r'\bcons\b\.?', 'consolidated', n)
    n = re.sub(r'\bconsol\b\.?', 'consolidated', n)
    n = re.sub(r'\bsch\b\.?', 'school', n)
    n = re.sub(r'\bschl\b\.?', 'school', n)
    n = re.sub(r'\bschls\b\.?', 'schools', n)
    n = re.sub(r'\bdist\b\.?', 'district', n)
    n = re.sub(r'\bsp\b\.?', 'special', n)
    n = re.sub(r'\bmun\b\.?', 'municipal', n)
    n = re.sub(r'\bcty\b\.?', 'county', n)
    n = re.sub(r'\bctg\b\.?', 'county', n)
    n = re.sub(r'\bag\b\.?', 'agricultural', n)
    n = re.sub(r'\bms\b\.?', 'mississippi', n)
    n = re.sub(r'\bst\b\.', 'saint', n)
    n = re.sub(r'\belem\b\.?', 'elementary', n)
    n = re.sub(r'\bindep\b\.?', 'independent', n)
    n = re.sub(r'\bvoc\b\.?', 'vocational', n)
    n = re.sub(r'\btech\b\.?', 'technical', n)
    # Remove extra spaces
    n = re.sub(r'\s+', ' ', n).strip()
    # Remove common suffixes for comparison
    for sfx in [' school district', ' school districtrict', ' public school district',
                 ' public schools', ' schools', ' school', ' district',
                 ' consolidated', ' separate', ' municipal', ' special',
                 ' administration', ' high school']:
        if n.endswith(sfx):
            n = n[:-(len(sfx))].strip()
    n = re.sub(r'\s*[\-~]\s*', ' ', n).strip()
    return n


def parse_name(full_name):
    full_name = full_name.strip()
    if not full_name:
        return None, '', '', None
    prefix = None
    for p in ['Dr. ', 'Dr ', 'Mr. ', 'Mr ', 'Mrs. ', 'Mrs ', 'Ms. ', 'Ms ']:
        if full_name.startswith(p):
            prefix = p.strip().rstrip('.')
            full_name = full_name[len(p):].strip()
            break
    suffix = None
    for s in [', Ed.D.', ', Ph.D.', ' Ed.D.', ' Ph.D.', ' Jr.', ' Jr', ' Sr.', ' Sr',
              ' III', ' II', ' IV', ' (Interim)']:
        if full_name.endswith(s):
            sv = s.strip().lstrip(',').strip()
            if sv != '(Interim)':
                suffix = sv
            full_name = full_name[:-(len(s))].strip()
            break
    parts = full_name.split()
    if len(parts) == 0:
        return prefix, '', '', suffix
    elif len(parts) == 1:
        return prefix, parts[0], '', suffix
    else:
        return prefix, parts[0], parts[-1], suffix


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Data that needs re-matching with better normalization
    # Format: state|district_name|full_name|email|phone
    data = []

    # MS unmatched records
    ms_records = """MS|Attala County School District|Rhyne Thompson|rthompson@attala.k12.ms.us|(662) 289-2801
MS|Bay St. Louis-Waveland School District|Dr. Sandra Reed|sreed@bwsd.org|(228) 467-6621
MS|Benton County School District|Dr. Regina Biggers|rbiggers@benton.k12.ms.us|(662) 224-6252
MS|Calhoun County School District|Dr. Lisa Langford|llangford@calhounk12.com|(662) 412-3152
MS|Chickasaw County School District|John Ellison|jellison@chickasaw.k12.ms.us|(662) 456-3332
MS|Choctaw County School District|Stewart G. Beard, Jr.|glenbeard@choctaw.k12.ms.us|(662) 285-4022
MS|Claiborne County School District|Dr. Sandra R. Nash|snash@claiborne.k12.ms.us|(601) 437-4232
MS|Copiah County School District|Rickey Clopton|rickey.clopton@copiah.ms|(601) 894-1341
MS|DeSoto County School District|Cory Uselton|cory.uselton@dcsms.org|(662) 429-5271
MS|East Tallahatchie Consolidated School District|Raymond Russell|RRussell@etsdk12.org|(662) 647-5524
MS|Franklin County School District|Chris Kent|ckent@fcsd.k12.ms.us|(601) 384-2340
MS|George County School District|Debra Joiner|debra.joiner@gcsd.us|(601) 947-6993
MS|Greenwood Leflore Consolidated School District|Dr. Kenneth Pulley|kpulley@glcsd.org|(662) 453-4231
MS|Hancock County School District|Rhett Ladner|rladner@hancockschools.net|(228) 255-0376
MS|Harrison County School District|William Bentz|WiBentz@harrison.k12.ms.us|(228) 539-6500
MS|Hinds County School District|Dr. Mitchell Shears|mshears@hinds.k12.ms.us|(601) 857-5222
MS|Humphreys County School District|Dr. Stanley Ellis|sellis@humphreys.k12.ms.us|(662) 746-2125
MS|Jackson County School District|David Baggett|David.baggett@jcsd.ms|(228) 826-1757
MS|Jefferson County School District|Dr. Adrian Hammitte|ahammitte@jcpsd.net|(601) 786-3721
MS|Jefferson Davis County School District|Isaac Haynes Jr.|ihaynes@jdcsd.org|(601) 792-2738
MS|Jones County School District|B. R. Jones|brjones@jonesk12.org|(601) 649-5201
MS|Kemper County School District|Hilute Hudson|hhudson@kemper.k12.ms.us|(601) 743-2657
MS|Lafayette County School District|James C. Foster|jay.foster@gocommodores.org|(662) 234-3271
MS|Lauderdale County School District|Dr. John-Mark Cain|jcain@lauderdale.k12.ms.us|(601) 693-1683
MS|Lawrence County School District|Allen Barron|allen.barron@lawcosd.org|(601) 587-2506
MS|Leake County School District|Will Russell|wrussell@leakesd.org|(601) 267-4579
MS|Lowndes County School District|Sam Allison|Sam.allison@lowndes.k12.ms.us|(662) 244-5000
MS|Madison County School District|Ted Poore|tpoore@madison-schools.com|(601) 879-3000
MS|Marion County School District|Brian Foster|bfoster@marionk12.org|(601) 736-7193
MS|Marshall County School District|Dr. Carrie Skelton|cskelton@mcschools.us|(662) 252-4271
MS|Monroe County School District|Dr. Chad O'Brian|chadobrian@mcsd.us|(662) 257-2176
MS|North Bolivar Consolidated School District|Dr. Jeremiah Burks|jburks@nbcsd.k12.ms.us|(662) 339-3781
MS|North Pike Consolidated School District|Dr. Jay Smith|Jay.Smith@npsd.k12.ms.us|(601) 276-2216
MS|North Tippah Consolidated School District|Dr. Dax Glover|dax.glover@ntippah.ms|(662) 837-8450
MS|Okolona Municipal Separate School District|Chad Spence|cspence@okolona.k12.ms.us|(662) 447-2353
MS|Pearl River County School District|Jeremy Weir|jweir@prc.k12.ms.us|(601) 798-7744
MS|Perry County School District|Dr. Titus M. Hines|thines@pcsdms.us|(601) 964-3211
MS|Pontotoc County School District|Dr. Brock Puckett|brockpuckett@pcsd.ms|(662) 489-3932
MS|Poplarville Special Municipal Separate School District|Jonathan Will|Jonathan.Will@poplarvilleschools.org|(601) 795-8477
MS|Prentiss County School District|Nickey Marshall|nmarshall@pcsdk12.com|(662) 728-4911
MS|Quitman County School District|Walter L. Atkins, Jr.|walteratkins@qcsd.k12.ms.us|(662) 326-7046
MS|Rankin County School District|Shane Sanders|ssanders@rcsd.ms|(601) 825-5590
MS|Scott County School District|Alan Lumpkin|alumpkin@scott.k12.ms.us|(601) 469-3861
MS|Simpson County School District|Dr. Robert Sanders|rsanders@simpson.k12.ms.us|(601) 847-8000
MS|Smith County School District|John King|John.King@SmithCountySchools.net|(601) 782-4296
MS|Starkville Oktibbeha Consolidated School District|Dr. Tony McGee|tmcgee@starkvillesd.com|(662) 615-0013
MS|Stone County School District|Boyd West|bwest@stoneschools.org|(601) 928-7247
MS|Sunflower County Consolidated School District|James Johnson-Waldington|jdjwaldington@sunflowerk12.org|(662) 887-4919
MS|Tate County School District|Alee Dixon|adixon@tcsdms.org|(662) 562-5861
MS|Tishomingo County Special Municipal Separate School District|Christie Holly|cholly@tcsk12.com|(662) 423-3206
MS|Union County School District|Windy Faulkner|wfaulkner@union.k12.ms.us|(662) 534-1960
MS|Vicksburg-Warren School District|Dr. Toriano Holloway|toriholloway@vwsd.org|(601) 638-5122
MS|Walthall County School District|J. Bradley Brumfield|jbbrumfield@wcsd.k12.ms.us|(601) 876-3401
MS|Wayne County School District|Lynn Revette|revettel@wcsdms.com|(601) 735-4871
MS|Webster County School District|James Mason|jmason@webstercountyschools.org|(662) 258-5921
MS|West Bolivar Consolidated School District|Dr. L'Kenna Whitehead|lwhitehead@wbcsdk12.org|(662) 759-3525
MS|Wilkinson County School District|Lee Coats|lcoats@wilkinsonk12.org|(601) 888-3582
MS|Yazoo County School District|Dr. Terri Rhea|Terri.rhea@yazook12.org|(662) 746-4672
MS|Forrest County Agricultural High School|Dr. William Wheat|wwheat@forrestcountyahs.com|(601) 582-4102
MS|Mississippi Schools for the Deaf and the Blind|LaMarlon Wilson|lamarlon.wilson@msdbk12.org|(601) 984-8200"""

    for line in ms_records.strip().split('\n'):
        data.append(line)

    # Process all states that need re-matching
    states_processed = set()
    total_additional = 0

    for line in data:
        parts = line.split('|')
        if len(parts) != 5:
            continue
        state, dist_name, full_name, email, phone = parts

        if state not in states_processed:
            states_processed.add(state)

        # Get DB districts for this state
        cur.execute("SELECT id, name FROM districts WHERE state = %s", (state,))
        db_districts = cur.fetchall()

        # Build expanded lookup
        db_lookup = {}
        for did, dname in db_districts:
            norm = expanded_normalize(dname)
            db_lookup[norm] = (did, dname)

        # Get existing contacts
        cur.execute("""
            SELECT c.district_id FROM contacts c
            JOIN districts d ON c.district_id = d.id
            WHERE d.state = %s AND c.role = 'superintendent'
        """, (state,))
        existing = set(row[0] for row in cur.fetchall())

        # Try to match
        norm_scraped = expanded_normalize(dist_name)

        match = None
        if norm_scraped in db_lookup:
            match = db_lookup[norm_scraped]
        else:
            for db_norm, val in db_lookup.items():
                if norm_scraped in db_norm or db_norm in norm_scraped:
                    match = val
                    break
                # Aggressive: strip all qualifiers
                s1 = re.sub(r'\b(consolidated|special|municipal|separate|public|county|city)\b', '', norm_scraped).strip()
                s2 = re.sub(r'\b(consolidated|special|municipal|separate|public|county|city)\b', '', db_norm).strip()
                s1 = re.sub(r'\s+', ' ', s1).strip()
                s2 = re.sub(r'\s+', ' ', s2).strip()
                if s1 and s2 and (s1 == s2 or s1 in s2 or s2 in s1):
                    match = val
                    break

        if not match:
            continue

        district_id, db_name = match
        if district_id in existing:
            continue

        prefix, first, last, suffix = parse_name(full_name)
        if not first and not last:
            continue

        try:
            cur.execute("""
                INSERT INTO contacts (district_id, role, first_name, last_name, prefix, suffix,
                                      email, email_status, phone, confidence_score, do_not_contact)
                VALUES (%s, 'superintendent', %s, %s, %s, %s, %s, 'unverified', %s, 80, false)
            """, (district_id, first, last, prefix, suffix,
                  email.strip() or None, phone.strip() or None))
            total_additional += 1
        except Exception as e:
            conn.rollback()
            print(f"  Error for {dist_name}: {e}")

    conn.commit()
    print(f"Additional contacts inserted: {total_additional}")

    # Print final stats for all 22 states
    print("\n--- Final Stats ---")
    for st in ['MS', 'ID', 'NM', 'AL', 'MD', 'WV', 'TN', 'KY', 'WY', 'RI', 'HI', 'AK', 'DE', 'DC',
               'PR', 'VI', 'GU', 'AS', 'MP', 'BI', 'NV', 'UT']:
        cur.execute("SELECT COUNT(*) FROM districts WHERE state=%s", (st,))
        d_count = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM contacts c JOIN districts d ON c.district_id=d.id
                       WHERE d.state=%s AND c.role='superintendent'""", (st,))
        c_count = cur.fetchone()[0]
        pct = f"{c_count/d_count*100:.0f}%" if d_count > 0 else "N/A"
        print(f"  {st}: {c_count} contacts / {d_count} districts ({pct})")

    cur.execute("SELECT COUNT(*) FROM contacts WHERE role = 'superintendent'")
    print(f"\n  GRAND TOTAL superintendent contacts: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
