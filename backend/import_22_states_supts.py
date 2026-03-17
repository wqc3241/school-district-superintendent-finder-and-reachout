"""
Import superintendent contacts for 22 remaining U.S. states/territories into Supabase.
Uses a combination of pre-scraped data and live scraping.

States: MS, ID, NM, AL, MD, WV, TN, KY, WY, RI, HI, AK, DE, DC, PR, VI, GU, AS, MP, BI, NV, UT
"""
import psycopg2
import httpx
from bs4 import BeautifulSoup
import re
import time
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

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
}


def parse_name(full_name):
    """Parse a full name into prefix, first_name, last_name, suffix."""
    full_name = full_name.strip()
    if not full_name:
        return None, '', '', None

    prefix = None
    for p in ['Dr. ', 'Dr ', 'Mr. ', 'Mr ', 'Mrs. ', 'Mrs ', 'Ms. ', 'Ms ', 'Rev. ', 'Rev ']:
        if full_name.startswith(p):
            prefix = p.strip().rstrip('.')
            full_name = full_name[len(p):].strip()
            break

    suffix = None
    for s in [', Ed.D.', ', Ph.D.', ', Ed.D', ', Ph.D', ' Ed.D.', ' Ph.D.',
              ' Jr.', ' Jr', ' Sr.', ' Sr', ' III', ' II', ' IV', ' (Interim)']:
        if full_name.endswith(s):
            suffix_val = s.strip().lstrip(',').strip()
            if suffix_val == '(Interim)':
                suffix_val = None  # Don't store interim as suffix
            else:
                suffix = suffix_val
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
    # Fix special chars
    name = name.replace('\u02db', '').replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    for sfx in [' public schools', ' public school district', ' school district',
                 ' school dept', ' school department', ' schools', ' sd',
                 ' county school system', ' county schools',
                 ' city school system', ' city schools', ' city school district',
                 ' independent school district', ' independent schools',
                 ' consolidated school district', ' consolidated schools',
                 ' municipal school district', ' municipal separate school district',
                 ' special municipal separate school district',
                 ' municipal schools', ' school system',
                 ' school division', ' board of education',
                 ' county board of education', ' city board of education',
                 ' separate school district', ' community school district',
                 ' unified school district', ' area school district',
                 ' local school district', ' union free school district',
                 ' central school district', ' regional school district',
                 ' vocational technical school district']:
        if name.endswith(sfx):
            name = name[:-(len(sfx))]
            break
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    return name


def match_district(scraped_name, db_lookup):
    """Try to match a scraped district name to the database."""
    norm = normalize_district_name(scraped_name)
    if norm in db_lookup:
        return db_lookup[norm]

    # Try with/without 'county'
    if not norm.endswith(' county'):
        test = norm + ' county'
        if test in db_lookup:
            return db_lookup[test]
    else:
        test = norm.replace(' county', '').strip()
        if test in db_lookup:
            return db_lookup[test]

    # Try with/without 'city'
    if not norm.endswith(' city'):
        test = norm + ' city'
        if test in db_lookup:
            return db_lookup[test]

    # Substring matching
    for db_norm, val in db_lookup.items():
        if norm in db_norm or db_norm in norm:
            return val
        # Handle county vs city
        n1 = norm.replace(' city', '').replace(' county', '').strip()
        n2 = db_norm.replace(' city', '').replace(' county', '').strip()
        if n1 and n2 and (n1 == n2):
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


def insert_contacts(cur, conn, records, db_lookup, existing, state):
    """Match records to districts and insert contacts."""
    inserted = 0
    for rec in records:
        district_match = match_district(rec['district'], db_lookup)
        if not district_match:
            continue

        district_id, db_name = district_match
        if district_id in existing:
            continue

        first = rec.get('first_name', '').strip()
        last = rec.get('last_name', '').strip()
        if not first and not last:
            continue

        try:
            cur.execute("""
                INSERT INTO contacts (district_id, role, first_name, last_name, prefix, suffix,
                                      email, email_status, phone, confidence_score, do_not_contact)
                VALUES (%s, 'superintendent', %s, %s, %s, %s, %s, 'unverified', %s, %s, false)
            """, (district_id, first, last, rec.get('prefix'), rec.get('suffix'),
                  rec.get('email') or None, rec.get('phone') or None, 80))
            existing.add(district_id)
            inserted += 1
        except Exception as e:
            conn.rollback()
            print(f"    Insert error for {rec['district']}: {e}")

    conn.commit()
    return inserted


def make_record(district, name, email='', phone=''):
    """Create a contact record from raw data."""
    prefix, first, last, suffix = parse_name(name)
    return {
        'district': district,
        'first_name': first, 'last_name': last,
        'prefix': prefix, 'suffix': suffix,
        'email': email.strip() if email else None,
        'phone': phone.strip() if phone else None,
    }


# ==========================================================================
# STATE DATA FUNCTIONS
# ==========================================================================

def get_ms_data(client):
    """Mississippi - scrape from MDE district directory."""
    records = []
    try:
        resp = client.get('https://mdek12.org/dd/', timeout=30)
        if resp.status_code != 200:
            return records
        soup = BeautifulSoup(resp.text, 'html.parser')
        # The MDE directory has structured data - look for district entries
        # Each district has name, superintendent, email, phone
        text = resp.text

        # Parse using regex on the full HTML
        # Look for patterns like district name + superintendent info
        entries = re.findall(
            r'<strong>([^<]+)</strong>.*?Superintendent.*?<[^>]+>([^<]+)<.*?mailto:([^"]+)".*?(\(\d{3}\)\s*\d{3}[\-\.]\d{4})',
            text, re.DOTALL
        )
        for district, name, email, phone in entries:
            records.append(make_record(district.strip(), name.strip(), email, phone))

        if not records:
            # Try table-based extraction
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        district = cells[0].get_text(strip=True)
                        name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
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
                        if district and name and len(name) > 3:
                            records.append(make_record(district, name, email, phone))
    except Exception as e:
        print(f"    MS scrape error: {e}")
    return records


MS_HARDCODED = """Aberdeen School District|Dr. Andrea Pastchal-Smith|apsmith@asdms.us|(662) 369-4682
Alcorn School District|Brandon Quinn|bquinn@alcornschools.org|(662) 286-5591
Amite County School District|Don Cuevas|dcuevas@amite.k12.ms.us|(601) 657-4361
Amory School District|Brian Tyler Jones|brjones@amoryschools.com|(662) 256-5991
Attala County School District|Rhyne Thompson|rthompson@attala.k12.ms.us|(662) 289-2801
Baldwyn School District|Raymond Craven|cravenr@baldwynschools.com|(662) 365-1000
Bay St. Louis-Waveland School District|Dr. Sandra Reed|sreed@bwsd.org|(228) 467-6621
Benton County School District|Dr. Regina Biggers|rbiggers@benton.k12.ms.us|(662) 224-6252
Biloxi Public School District|Marcus Boudreaux|marcus.boudreaux@biloxischools.net|(228) 374-1810
Booneville School District|Dr. Todd English|tenglish@boonevilleschools.org|(662) 728-2171
Brookhaven School District|Rod Henderson|rod.henderson@brookhavenschools.org|(601) 833-6661
Calhoun County School District|Dr. Lisa Langford|llangford@calhounk12.com|(662) 412-3152
Canton Public School District|Dwight J. Luckett, Sr.|dwightjluckett@cantonschools.net|(601) 859-4110
Carroll County School District|Joey Carpenter|jcarpenter@ccsd.ms|(662) 237-9276
Chickasaw County School District|John Ellison|jellison@chickasaw.k12.ms.us|(662) 456-3332
Choctaw County School District|Stewart G. Beard, Jr.|glenbeard@choctaw.k12.ms.us|(662) 285-4022
Claiborne County School District|Dr. Sandra R. Nash|snash@claiborne.k12.ms.us|(601) 437-4232
Clarksdale Municipal School District|Dr. Toya Harrell-Matthews|tmatthews@cmsd.k12.ms.us|(662) 627-8500
Cleveland School District|Dr. Lisa Bramuchi|lbramuchi@cleveland.k12.ms.us|(662) 843-3529
Clinton Public School District|Dr. Andy Schoggin|aschoggin@clintonpublicschools.com|(601) 924-7533
Coahoma County School District|Dr. Virginia Young|vyoung@coahoma.k12.ms.us|(662) 624-5448
Coffeeville School District|Dexter Green|dgreen@coffeevilleschools.org|(662) 675-8941
Columbia School District|Jason Harris|jharris@columbiaschools.org|(601) 736-2366
Columbus Municipal School District|Craig Chapman|chapmanc@columbuscityschools.org|(662) 241-7405
Copiah County School District|Rickey Clopton|rickey.clopton@copiah.ms|(601) 894-1341
Corinth School District|Dr. John Barnett|jbarnett@corinth.k12.ms.us|(662) 287-2425
Covington County School District|Jon Chancelor|jchancelor@covingtoncountyschools.org|(601) 765-8247
DeSoto County School District|Cory Uselton|cory.uselton@dcsms.org|(662) 429-5271
East Jasper School District|Nadene Arrington|narrington@eastjasper.k12.ms.us|(601) 787-3281
East Tallahatchie Consolidated School District|Raymond Russell|RRussell@etsdk12.org|(662) 647-5524
Enterprise School District|Marlon C. Brannan|marlon.brannan@esd.k12.ms.us|(601) 659-7604
Forest Municipal School District|Dr. Melanie Nelson|mnelson@forest.k12.ms.us|(601) 469-3250
Forrest County School District|Brian Freeman|brfreeman@forrest.k12.ms.us|(601) 545-6055
Franklin County School District|Chris Kent|ckent@fcsd.k12.ms.us|(601) 384-2340
George County School District|Debra Joiner|debra.joiner@gcsd.us|(601) 947-6993
Greene County School District|Charles L. Breland|cbreland@greene.k12.ms.us|(601) 394-2364
Greenville Public Schools|Dr. Ilean Richards|irichards@gpsdk12.com|(662) 334-7000
Greenwood Leflore Consolidated School District|Dr. Kenneth Pulley|kpulley@glcsd.org|(662) 453-4231
Grenada School District|Dr. David Daigneault|ddaigneault@grenadak12.com|(662) 226-1606
Gulfport School District|Glen East|glen.east@gulfportschools.org|(228) 865-4600
Hancock County School District|Rhett Ladner|rladner@hancockschools.net|(228) 255-0376
Harrison County School District|William Bentz|WiBentz@harrison.k12.ms.us|(228) 539-6500
Hattiesburg Public School District|Dr. Robert Williams|superintendent@hattiesburgpsd.com|(601) 582-5078
Hazlehurst City School District|Cloyd Garth|cgarth@hazlehurst.k12.ms.us|(601) 894-1152
Hinds County School District|Dr. Mitchell Shears|mshears@hinds.k12.ms.us|(601) 857-5222
Hollandale School District|Sarah J. Bailey|sjbailey@hollandalesd.org|(662) 827-2276
Holly Springs School District|Dr. Irene Walton Turnage|iwalton@hssdk12.org|(662) 252-2183
Holmes County Consolidated School District|Pat Ross|pross@holmesccsd.org|(662) 834-2175
Humphreys County School District|Dr. Stanley Ellis|sellis@humphreys.k12.ms.us|(662) 746-2125
Itawamba County School District|Austin Alexander|aalexander@itawambacountyschools.com|(662) 862-2159
Jackson County School District|David Baggett|David.baggett@jcsd.ms|(228) 826-1757
Jackson Public School District|Dr. Errick L. Greene|ergreene@jackson.k12.ms.us|(601) 960-8725
Jefferson County School District|Dr. Adrian Hammitte|ahammitte@jcpsd.net|(601) 786-3721
Jefferson Davis County School District|Isaac Haynes Jr.|ihaynes@jdcsd.org|(601) 792-2738
Jones County School District|B. R. Jones|brjones@jonesk12.org|(601) 649-5201
Kemper County School District|Hilute Hudson|hhudson@kemper.k12.ms.us|(601) 743-2657
Kosciusko School District|Dr. Donna Boone|donna.boone@kosciuskoschools.com|(662) 289-4771
Lafayette County School District|James C. Foster|jay.foster@gocommodores.org|(662) 234-3271
Lamar County School District|Dr. Wesley Quick|wesley.quick@lamarcountyschools.org|(601) 794-1030
Lauderdale County School District|Dr. John-Mark Cain|jcain@lauderdale.k12.ms.us|(601) 693-1683
Laurel School District|Dr. Michael Eubanks|meubanks@laurelschools.org|(601) 649-6391
Lawrence County School District|Allen Barron|allen.barron@lawcosd.org|(601) 587-2506
Leake County School District|Will Russell|wrussell@leakesd.org|(601) 267-4579
Lee County School District|Coke Magee|coke.magee@leecountyschools.us|(662) 841-9144
Leland School District|Jesse King|jesseking@lelandk12.org|(662) 686-5000
Lincoln County School District|David Martin|david.martin@lincoln.k12.ms.us|(601) 835-0011
Long Beach School District|Dr. Talia Lock|talia.lock@lbsdk12.com|(228) 864-1146
Louisville Municipal School District|David Luke|dluke@louisville.k12.ms.us|(662) 773-3411
Lowndes County School District|Sam Allison|Sam.allison@lowndes.k12.ms.us|(662) 244-5000
Madison County School District|Ted Poore|tpoore@madison-schools.com|(601) 879-3000
Marion County School District|Brian Foster|bfoster@marionk12.org|(601) 736-7193
Marshall County School District|Dr. Carrie Skelton|cskelton@mcschools.us|(662) 252-4271
McComb Separate School District|Johnnie Vick|vickj@mccomb.k12.ms.us|(601) 684-4661
Meridian Public Schools|Dr. Amy Carter|amcarter@mpsdk12.net|(601) 484-4915
Monroe County School District|Dr. Chad O'Brian|chadobrian@mcsd.us|(662) 257-2176
Moss Point School District|Dr. Christopher Williams|cjwilliams@mpsdnow.org|(228) 475-4558
Natchez-Adams School District|Zandra McDonald|zanmcdonald@natchez.k12.ms.us|(601) 445-4329
Neshoba County School District|Josh Perkins|jperkins@neshobacentral.com|(601) 656-3752
Nettleton School District|Megan Garner|mgarner@nettleton.k12.ms.us|(662) 963-2151
New Albany Public School District|Tony Cook|tcook@nasd.ms|(662) 534-1800
Newton County School District|Brooke Sibley|bsibley@newton.k12.ms.us|(601) 635-2317
Newton Municipal School District|Cola Shelby|ccshelby@nmsd.us|(601) 683-2451
North Bolivar Consolidated School District|Dr. Jeremiah Burks|jburks@nbcsd.k12.ms.us|(662) 339-3781
North Panola School District|Dr. Wilner Bolden|wbolden@northpanolaschools.org|(662) 487-3029
North Pike Consolidated School District|Dr. Jay Smith|Jay.Smith@npsd.k12.ms.us|(601) 276-2216
North Tippah Consolidated School District|Dr. Dax Glover|dax.glover@ntippah.ms|(662) 837-8450
Noxubee County School District|Dr. Washington Cole, IV|wcole@ourncsd.org|(662) 726-4527
Ocean Springs School District|Michael Lindsey|superintendent@ossdms.org|(228) 875-7706
Okolona Municipal Separate School District|Chad Spence|cspence@okolona.k12.ms.us|(662) 447-2353
Oxford School District|Bradley Roberson|wbroberson@oxfordsd.org|(662) 234-3541
Pascagoula-Gautier School District|Dr. Caterria Payton|cpayton@pgsd.ms|(228) 938-6491
Pass Christian Public School District|Dr. Carla J. Evers|cevers@pc.k12.ms.us|(228) 255-6200
Pearl Public School District|Chris Chism|cchism@pearlk12.com|(601) 932-7921
Pearl River County School District|Jeremy Weir|jweir@prc.k12.ms.us|(601) 798-7744
Perry County School District|Dr. Titus M. Hines|thines@pcsdms.us|(601) 964-3211
Petal School District|Dr. Matt Dillon|matt.dillon@petalschools.com|(601) 545-3002
Philadelphia Public School District|Dr. Shannon Whitehead|shannon.whitehead@phillytornadoes.com|(601) 656-2955
Picayune School District|Dean Shaw|dshaw@pcu.k12.ms.us|(601) 798-3230
Pontotoc City Schools|Phil Webb|Pwebb@pontotoc.k12.ms.us|(662) 489-3336
Pontotoc County School District|Dr. Brock Puckett|brockpuckett@pcsd.ms|(662) 489-3932
Poplarville Special Municipal Separate School District|Jonathan Will|Jonathan.Will@poplarvilleschools.org|(601) 795-8477
Prentiss County School District|Nickey Marshall|nmarshall@pcsdk12.com|(662) 728-4911
Quitman School District|Dr. Minnie Dace|mdace@qsdk12.org|(601) 776-2186
Quitman County School District|Walter L. Atkins, Jr.|walteratkins@qcsd.k12.ms.us|(662) 326-7046
Rankin County School District|Shane Sanders|ssanders@rcsd.ms|(601) 825-5590
Richton School District|Clay Anglin|canglin@richton.k12.ms.us|(601) 788-6581
Scott County School District|Alan Lumpkin|alumpkin@scott.k12.ms.us|(601) 469-3861
Senatobia Municipal School District|Chris Fleming|cfleming@senatobia.k12.ms.us|(662) 562-4897
Simpson County School District|Dr. Robert Sanders|rsanders@simpson.k12.ms.us|(601) 847-8000
Smith County School District|John King|John.King@SmithCountySchools.net|(601) 782-4296
South Delta School District|Sammie Ivy|sammieivy@sdelta.org|(662) 873-4302
South Panola School District|Dr. Del Phillips|dphillips@spanola.net|(662) 563-9361
South Pike School District|Dr. Geneva Holmes|gholmes@southpike.org|(601) 783-0430
South Tippah School District|Tony Elliott|telliott@stsd.ms|(662) 837-7156
Starkville Oktibbeha Consolidated School District|Dr. Tony McGee|tmcgee@starkvillesd.com|(662) 615-0013
Stone County School District|Boyd West|bwest@stoneschools.org|(601) 928-7247
Sunflower County Consolidated School District|James Johnson-Waldington|jdjwaldington@sunflowerk12.org|(662) 887-4919
Tate County School District|Alee Dixon|adixon@tcsdms.org|(662) 562-5861
Tishomingo County Special Municipal Separate School District|Christie Holly|cholly@tcsk12.com|(662) 423-3206
Tunica County School District|Dr. Frederick Robinson|robinsonfre@tunicak12.org|(662) 363-2811
Tupelo Public School District|Dr. Robert Joseph Picou|rjpicou@tupeloschools.com|(662) 841-8850
Union County School District|Windy Faulkner|wfaulkner@union.k12.ms.us|(662) 534-1960
Union Public School District|Dr. Tyler Hansford|hansfordt@unionyellowjackets.org|(601) 774-9579
Vicksburg-Warren School District|Dr. Toriano Holloway|toriholloway@vwsd.org|(601) 638-5122
Walthall County School District|J. Bradley Brumfield|jbbrumfield@wcsd.k12.ms.us|(601) 876-3401
Water Valley School District|Drew Pitcock|dpitcock@wvsdschools.com|(662) 473-1203
Wayne County School District|Lynn Revette|revettel@wcsdms.com|(601) 735-4871
Webster County School District|James Mason|jmason@webstercountyschools.org|(662) 258-5921
West Bolivar Consolidated School District|Dr. L'Kenna Whitehead|lwhitehead@wbcsdk12.org|(662) 759-3525
West Jasper Consolidated School District|Dr. Jill Miller|jmiller@westjasper.org|(601) 425-8500
West Point School District|Dr. Jermaine Taylor|jtaylor@westpoint.k12.ms.us|(662) 494-4242
West Tallahatchie Consolidated School District|Tony Young|tyoung@wtsd.k12.ms.us|(662) 375-9291
Western Line School District|Lawerence Hudson|lhudson@westernline.org|(662) 335-7186
Wilkinson County School District|Lee Coats|lcoats@wilkinsonk12.org|(601) 888-3582
Winona-Montgomery Consolidated School District|Dr. Howard Savage, Jr.|howardsavage@winonaschools.net|(662) 283-3731
Yazoo City School District|Dr. Earl Watkins|ewatkins@yazoocity.k12.ms.us|(662) 746-2125
Yazoo County School District|Dr. Terri Rhea|Terri.rhea@yazook12.org|(662) 746-4672"""


def get_ms_records():
    records = []
    for line in MS_HARDCODED.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_ky_data(client):
    """Kentucky - scrape from KDE OpenHouse."""
    records = []
    try:
        resp = client.get('https://openhouse.education.ky.gov/Superintendents', timeout=30)
        if resp.status_code != 200:
            return records
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table')
        if not table:
            return records
        rows = table.find_all('tr')
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) >= 7:
                district = cells[1].get_text(strip=True)
                name = cells[2].get_text(strip=True)
                phone = cells[6].get_text(strip=True)
                if district and name:
                    records.append(make_record(district, name, '', phone))
    except Exception as e:
        print(f"    KY scrape error: {e}")
    return records


def get_tn_data():
    """Tennessee - hardcoded from TOSS directory."""
    raw = """Achievement School District|Robin Copp
Alamo City Schools|Brooks Rawson
Alcoa City Schools|Jake Jones
Anderson County Schools|Dr. Tim Parrott
Arlington Community Schools|Dr. Allison Clark
Athens City Schools|Joe Barnett
Bartlett City Schools|Dr. David Stephens
Bedford County Schools|Dr. Tammy Garrett
Bells City Schools|Boone Parlow
Benton County Schools|Mark Florence
Bledsoe County Schools|Dr. Kristy Walker
Blount County Schools|Justin Ridge
Bradford Special School System|Dan Black
Bradley County Schools|Dr. Linda Cash
Bristol TN City Schools|Dr. Annette Tudor
Campbell County Schools|Jennifer Fields
Cannon County Schools|Julie Vincent
Carroll County Schools|Johnny McAdams
Carter County Schools|Dr. Brandon Carpenter
Cheatham County Schools|Stacy Brown
Chester County Schools|Troy Kilzer
Claiborne County Schools|Meredith Arnold
Clarksville-Montgomery County|Dr. Jean Luna-Vedder
Clay County Schools|Diana Monroe
Cleveland City Schools|Jeff Elliott
Clinton City Schools|Kelly Johnson
Cocke County Schools|Manney Moore
Coffee County Schools|Scott Hargrove
Collierville Schools|Dr. Russell Dyer
Crockett County Schools|Phillip Pratt
Cumberland County Schools|Dr. Rebecca Farley
Dayton City Schools|Trish Newsom
Decatur County Schools|Melinda Thompson
DeKalb County Schools|Patrick Cripps
Dickson County Schools|Dr. Christie Southerland
Dyer County Schools|Cheryl Mathis
Dyersburg City Schools|Kim Worley
Elizabethton City Schools|Richard VanHuss
Etowah City Schools|Dr. Mike Frazier
Fayette County Schools|Dr. Don McPherson
Fayetteville City Schools|Eric Jones
Fentress County Schools|Kristi Hall
Franklin County Schools|Dr. Cary Holman
Franklin Special School District|Dr. David Snowden
Germantown Municipal Schools|Jason Manuel
Gibson County SSD|Eddie Pruett
Giles County Schools|Dr. Vickie Beard
Grainger County Schools|Mark Briscoe
Greene County Schools|Chris Malone
Greeneville City Schools|Steve Starnes
Grundy County Schools|Dr. Clint Durley
Hamblen County Schools|Arnold Bunch
Hamilton County Schools|Dr. Justin Robertson
Hancock County Schools|Charlotte Mullins
Hardeman County Schools|Dr. Christy Smith
Hardin County Schools|Michael Davis
Hawkins County Schools|Matt Hixson
Haywood County Schools|Amie Marsh
Henderson County Schools|Danny Beecham
Henry County Schools|Dr. Leah Rice Watkins
Hickman County Schools|Belinda Anderson
Hollow Rock-Bruceton SSD|David Duncan
Houston County Schools|Scott Moore
Humboldt City Schools|Dr. Janice Epperson
Humphreys County Schools|Dr. Robert Lanham
Huntingdon Special School District|Dr. Jonathan Kee
Jackson County Schools|Jason Hardy
Jackson-Madison County Schools|Dr. Marlon King
Jefferson County Schools|Dr. Tommy Arnold
Johnson City Schools|Dr. Erin Slater
Johnson County Schools|Dr. Mischelle Simcox
Kingsport City Schools|Dr. Chris Hampton
Knox County Schools|Dr. Jon Rysewyk
Lake County Schools|Dr. Woody Burton
Lakeland Schools|Dr. Ted Horrell
Lauderdale County Schools|Selina Sparkman
Lawrence County Schools|Michael Adkins
Lebanon Special School District|Brian Hutto
Lenoir City Schools|Dr. Millicent Smith
Lewis County Schools|Dr. Tracy McAbee
Lexington City Schools|Cindy Olive
Lincoln County Schools|Jacob Sorrells
Loudon County Schools|Mike Garren
Macon County Schools|Shawn Carter
Manchester City Schools|Dr. Joey Vaughn
Marion County Schools|Dr. Mark Griffith
Marshall County Schools|Dr. Justin Perry
Maryville City Schools|Dr. Mike Winstead
Maury County Schools|Dr. Lisa Ventura
McKenzie Special School District|Dr. Justin Barden
McMinn County Schools|Melasawn Knight
McNairy County Schools|Greg Martin
Meigs County Schools|Clint Baker
Memphis-Shelby County Schools|Dr. Roderick Richmond
Metro Nashville Public Schools|Dr. Adrienne Battle
Milan Special School District|Dr. Versie Hamlett
Millington Municipal Schools|Bo Griffin
Monroe County Schools|Dr. Kristi Windsor
Moore County Schools|Chad Moorehead
Morgan County Schools|Jamie Pemberton
Murfreesboro City Schools|Dr. Trey Duke
Newport City Schools|Dr. Justin Norton
Oak Ridge City Schools|Dr. Bruce Borchers
Obion County Schools|Tim Watkins
Oneida Special School District|Dr. Jeanny Phillips
Overton County Schools|Kim Dillon
Paris Special School District|Shane Paschall
Perry County Schools|Eric Lomax
Pickett County Schools|Melissa Robbins
Polk County Schools|Dr. James Jones
Putnam County Schools|Corby King
Rhea County Schools|Amie Lonas
Richard City Schools|Sharon Newcom
Roane County Schools|Russell Jenkins
Robertson County Schools|Dr. Danny Weeks
Rogersville City Schools|Edwin Jarnagin
Rutherford County Schools|Dr. Jimmy Sullivan
Scott County Schools|Bill Hall
Sequatchie County Schools|Sarai Pierce
Sevier County Schools|Stephanie Huskey
Smith County Schools|Barry Smith
South Carroll SSD|Dr. Lisa Norris
Stewart County Schools|Mike Craig
Sullivan County Schools|Chuck Carter
Sumner County Schools|Dr. Scott Langford
Sweetwater City Schools|Rodney Boruff
Tipton County Schools|Dr. John Combs
Trenton Special School District|Tim Haney
Trousdale County Schools|Jennifer Cothron
Tullahoma City Schools|Dr. Catherine Stephens
Unicoi County Schools|John English
Union City Schools|Wes Kennedy
Union County Schools|Greg Clay
Van Buren County Schools|Katina Simmons
Warren County Schools|Dr. Grant Swallows
Washington County Schools|Jerry Boyd
Wayne County Schools|Dr. Ricky Inman
Weakley County Schools|Jeff Cupples
West Carroll Special School District|Preston Caldwell
White County Schools|Kurt Dronebarger
Williamson County Schools|Jason Golden
Wilson County Schools|Jeff Luttrell"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 2:
            records.append(make_record(parts[0], parts[1]))
    return records


# I'll include hardcoded data inline for the remaining states to keep it manageable.
# The data was scraped from official state DOE websites.

def get_md_records():
    """Maryland - from MSDE website."""
    raw = """Allegany County Public Schools|Dr. Michael J. Martirano||(301) 759-2038
Anne Arundel County Public Schools|Dr. Mark T. Bedell||(410) 222-5303
Baltimore City Public Schools|Dr. Sonja B. Santelises||(410) 396-8803
Baltimore County Public Schools|Dr. Myriam A. Rogers||(443) 809-4281
Calvert County Public Schools|Dr. Marcus Newsome||(443) 550-8009
Caroline County Public Schools|Dr. Derek L. Simmons||(410) 479-1460
Carroll County Public Schools|Dr. Cynthia McCabe||(410) 751-3128
Cecil County Public Schools|Dr. Jeffrey A. Lawson||(410) 996-5499
Charles County Public Schools|Dr. Maria V. Navarro||(301) 934-7223
Dorchester County Public Schools|Dr. Jymil Thompson||(410) 221-1111
Frederick County Public Schools|Dr. Cheryl L. Dyson||(301) 696-6910
Garrett County Public Schools|Dr. Brenda McCartney||(301) 334-8901
Harford County Public Schools|Dr. Dyann Mack||(410) 588-5204
Howard County Public Schools|Mr. William Barnes||(410) 313-6677
Kent County Public Schools|Dr. Mary Boswell-McComas||(410) 778-7113
Montgomery County Public Schools|Dr. Thomas W. Taylor||(240) 740-3020
Prince George's County Public Schools|Dr. Shawn Joseph||(301) 952-6008
Queen Anne's County Public Schools|Dr. Matthew Kibler||(410) 758-2403
St. Mary's County Public Schools|Dr. James Scott Smith||(301) 475-5511
Somerset County Public Schools|Dr. W. David Bromwell||(410) 651-1616
Talbot County Public Schools|Dr. Sharon M. Pepukayi||(410) 822-0330
Washington County Public Schools|Dr. David T. Sovine||(301) 766-2815
Wicomico County Public Schools|Dr. Micah C. Stauffer||(410) 677-4495
Worcester County Public Schools|Dr. Annette Wallace||(410) 632-5020"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_wv_records():
    """West Virginia - from WVDE Excel."""
    raw = """Barbour County Schools|Mr. Eddie Vincent|edvincen@k12.wv.us|(304)457-3030
Berkeley County Schools|Dr. Ryan Saxe|rsaxe@k12.wv.us|(304)267-3500
Boone County Schools|Mr. Allen Sexton|asexton@k12.wv.us|(304)369-3131
Braxton County Schools|Dr. Donna Burge-Tetrick|dtetrick@k12.wv.us|(304)765-7101
Brooke County Schools|Dr. Jeffrey Crook|jcrook@k12.wv.us|(304)737-3481
Cabell County Schools|Mr. Tim Hardesty|thardest@k12.wv.us|(304)528-5000
Calhoun County Schools|Mr. Michael Fitzwater|mfitzwater@k12.wv.us|(304)354-7011
Clay County Schools|Mr. Phil Dobbins|philip.dobbins@k12.wv.us|(304)587-4266
Doddridge County Schools|Dr. Adam Cheeseman|acheeseman@k12.wv.us|(304)873-2300
Fayette County Schools|Mr. David Warvel|dwarvel@k12.wv.us|(304)574-1176
Gilmer County Schools|Dr. Tony Minney|tdminney@k12.wv.us|(304)462-7386
Grant County Schools|Mr. Mitch Webster|mwebster@k12.wv.us|(304)257-1011
Greenbrier County Schools|Mr. Jeffrey A. Bryant|jbryant@k12.wv.us|(304)647-6470
Hampshire County Schools|Mr. George R. Collett|gcollett@k12.wv.us|(304)822-3528
Hancock County Schools|Mr. Walter Saunders|wsaunder@k12.wv.us|(304)564-3411
Hardy County Schools|Dr. Sheena VanMeter|srvanmet@k12.wv.us|(304)530-2348
Harrison County Schools|Ms. Dora Stutler|dstutler@k12.wv.us|(304)326-7300
Jackson County Schools|Mr. William P. Hosaflook|whosaflo@k12.wv.us|(304)372-7300
Jefferson County Schools|Dr. William Bishop|chuck.bishop@k12.wv.us|(304)725-9741
Kanawha County Schools|Dr. Paula Potter|ppotter@mail.kana.k12.wv.us|(304)348-7770
Lewis County Schools|Ms. Carolyn Long|carolyn.long@k12.wv.us|(304)269-8300
Lincoln County Schools|Mr. Frank Barnett|flbarnet@k12.wv.us|(304)824-3033
Logan County Schools|Dr. Sonya White|snjwhite@k12.wv.us|(304)792-2060
Marion County Schools|Dr. Donna Heston|donna.heston@k12.wv.us|(304)367-2100
Marshall County Schools|Dr. Shelby Haines|shaines@k12.wv.us|(304)843-4400
Mason County Schools|Ms. Melissa Farmer|mfarmer@k12.wv.us|(304)675-4540
McDowell County Schools|Dr. Ingrida Barker|ibarker@k12.wv.us|(304)436-8441
Mercer County Schools|Mr. Ed Toman|etoman@k12.wv.us|(304)487-1551
Mineral County Schools|Mr. Troy Ravenscroft|tlravenscroft@k12.wv.us|(304)788-4200
Mingo County Schools|Dr. Joetta Basile|jsbasile@k12.wv.us|(304)235-3333
Monongalia County Schools|Dr. Eddie Campbell|ecampbell@k12.wv.us|(304)291-9210
Monroe County Schools|Dr. Jason Conaway|jconaway@k12.wv.us|(304)772-3094
Morgan County Schools|Mr. David Banks|dbanks@k12.wv.us|(304)258-2430
Nicholas County Schools|Mr. Scott Cochran|scochran@k12.wv.us|(304)872-3611
Ohio County Schools|Dr. Kimberly Miller|ksmiller@k12.wv.us|(304)243-0300
Pendleton County Schools|Mrs. Nicole Hevener|nhevener@k12.wv.us|(304)358-2207
Pleasants County Schools|Mr. Michael Wells|gwells@k12.wv.us|(304)684-2215
Pocahontas County Schools|Dr. Leatha Williams|lgwillia@k12.wv.us|(304)799-4505
Preston County Schools|Mr. Brad Martin|brrmarti@k12.wv.us|(304)329-0580
Putnam County Schools|Mr. John G. Hudson|jghudson@k12.wv.us|(304)586-0500
Raleigh County Schools|Dr. Serena Starcher|slstarch@k12.wv.us|(304)256-4500
Randolph County Schools|Dr. Shawn Dilly|sdilly@k12.wv.us|(304)636-9150
Ritchie County Schools|Ms. April Haught|ahaught@k12.wv.us|(304)643-2991
Roane County Schools|Ms. Michelle Stellato|michelle.stellato@k12.wv.us|(304)927-6400
Summers County Schools|Dr. Linda Knott|lknott@k12.wv.us|(304)466-6000
Taylor County Schools|Dr. John Stallings|john.stallings@k12.wv.us|(304)265-2497
Tucker County Schools|Ms. Alicia Lambert|arlambert@k12.wv.us|(304)478-2771
Tyler County Schools|Mr. Shane Highley|ahighley@k12.wv.us|(304)758-2145
Upshur County Schools|Mrs. Christine Miller|cemiller@k12.wv.us|(304)472-5480
Wayne County Schools|Mr. Todd Alexander|talexand@k12.wv.us|(304)272-5113
Webster County Schools|Mr. Joseph Arbogast|jarbogast@k12.wv.us|(304)847-5638
Wetzel County Schools|Ms. Cassandra Porter|crporter@k12.wv.us|(304)455-2441
Wirt County Schools|Mr. John McKown|jmckown@k12.wv.us|(304)275-4279
Wood County Schools|Ms. Christie Willis|cwillis@k12.wv.us|(304)420-9663
Wyoming County Schools|Mr. Johnathan Henry|jjhenry@k12.wv.us|(304)732-6262"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_ri_records():
    """Rhode Island - from RISSA directory."""
    raw = """Barrington|Robert Mitchell|rmitchell@barringtonschools.org|401-245-5000
Bristol-Warren Regional|Ana Riley|ariley@bw.k12.ri.us|401-253-4000
Burrillville|Dr. Michael Sollitto|msollitto@bsd-ri.net|401-568-1301
Central Falls|Stephanie Downey Toledo|stoledodowney@cfschools.net|401-727-7700
Chariho|Gina Picard|gpicard@chariho.k12.ri.us|401-364-7575
Coventry|Don Cowart|dcowart@coventryschools.net|401-822-9400
Cranston|Jeannine Nota Masse|jnotamasse@cpsed.net|401-270-8170
Cumberland|Phil Thornton|pthornton@cumberlandschools.org|401-658-1600
East Greenwich|Tom Kenworthy|tkenworthy@egsd.net|401-398-1201
East Providence|Sandra Forand|sforand@epsd.org|401-433-6222
Foster|Kathy Crowley|kcrowley@fosterps.org|401-647-5100
Exeter-West Greenwich|James Erinakes|jerinakes@ewg.k12.ri.us|401-397-5125
Glocester|Patricia Dubois|pdubois@glocesterschools.org|401-568-4175
Foster-Glocester|Renee Palazzo|rpalazzo@fgschools.com|401-710-7500
Johnston|Scott Sutherland|ssutherland@johnstonschools.org|401-233-1900
Jamestown|David Raleigh|raleigh.david@jamestownschools.org|401-423-7010
Little Compton|Dr. Laurie Dias-Mitchell|ldiasmitchell@lcsd.k12.ri.us|401-635-2351
Lincoln|Dr. Kevin McNamara|kmcnamara@lincolnps.org|401-721-3300
Narragansett|Peter Cummings|pcummings@narragansett.k12.ri.us|401-792-9450
Middletown|William Niemeyer|niemeyer@mpsri.net|401-849-2122
Newport|Colleen Jermain|cjermain@npsri.net|401-847-2100
New Shoreham|John Martin|jmartin@bischool.org|401-466-7732
North Providence|Joseph Goho|jgoho@npsd.k12.ri.us|401-233-1100
North Kingstown|Dr. Ken Duva|kduva@nksd.net|401-268-6403
Pawtucket|Randy Buck|rbuck@psdri.net|401-729-6315
North Smithfield|Michael St. Jean|mstjean@nssk12.org|401-769-5492
Portsmouth|Elizabeth L. Viveiros|eviveiros@portsmouthschoolsri.org|
Scituate|Michael Haskell|mhaskell@scituateschoolsri.net|401-647-4100
Providence|Javier Montanez|jmontanez@ppsd.org|401-456-9211
South Kingstown|Michael Podraza|mpodraza@skschools.net|401-360-1300
Smithfield|Lisa Odom-Villela|lodom-villela@smithfield-ps.org|401-231-6606
Warwick|William McCaffrey|wmccaffrey@warwickschools.org|401-734-3100
Tiverton|Chris Haskins|chaskins@tivertonschools.org|401-624-8475
Westerly|Mark Garceau|mgarceau@westerly.k12.ri.us|401-348-2700
West Warwick|Karen Tarasevich|ktarasevich@westwarwickpublicschools.com|401-821-1180
Woonsocket|Patrick McGee|pmcgee@woonsocketschools.com|401-767-4600"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_de_records():
    """Delaware - from UDel directory."""
    raw = """Appoquinimink School District|Matt Burrows|Matthew.Burrows@appo.k12.de.us|302-376-4128
Brandywine School District|Lincoln Hohler|lincoln.hohler@bsd.k12.de.us|302-793-5058
Caesar Rodney School District|Kevin Fitzgerald|kevin.fitzgerald@cr.k.12.de.us|302-698-4800
Cape Henlopen School District|Robert S. Fulton|robert.fulton@cape.k12.de.us|302-645-6686
Capital School District|Dr. Sylvia M. Henderson|Sylvia.Henderson@capital.k12.de.us|302-857-4223
Christina School District|Dan Shelton|dan.shelton@christina.k12.de.us|302-552-2600
Colonial School District|Jeffrey D. Menzer|jeffrey.menzer@colonial.k12.de.us|302-323-2716
Delmar School District|Charity Phillips|charity.phillips@delmar.k12.de.us|302-846-9544
Indian River School District|Dr. Jay Owens|jack.owens@irsd.k12.de.us|302-436-1000
Lake Forest School District|Dr. Brenda Wynder|bgwynder@lf.k12.de.us|302-284-3020
Laurel School District|Shawn Larrimore|shawn.larrimore@laurel.k12.de.us|302-875-6100
Milford School District|Phyllis Kohel|phyllis.kohel@milford.k12.de.us|302-422-1600
New Castle County Vocational Technical School District|Dr. Victoria C. Gehrt|vicki.gehrt@ncct.k12.de.us|302-995-8051
Polytech School District|Deborah Zych|deborah.zych@polytech.k12.de.us|302-697-2170
Red Clay Consolidated School District|Jill Floore|jill.floore@redclay.k12.de.us|302-552-3702
Seaford School District|David Perrington|dperrington@seaford.k12.de.us|302-629-4587
Smyrna School District|Deborah Wicks|deborah.wicks@smyrna.k12.de.us|302-653-8585
Sussex Technical School District|Allen Lathbury|allen.lathbury@sussexvt.k12.de.us|302-856-0961
Woodbridge School District|Heath Chasanov|heath.chasanov@woodbridge.k12.de.us|302-337-7990"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_ut_records():
    """Utah - from schools.utah.gov."""
    raw = """Alpine School District|Rob Smith|rwsmith@alpinedistrict.org|801-610-8400
Beaver School District|David Long|david.long@beaver.k12.ut.us|435-438-2291
Box Elder School District|Steve Carlsen|steve.carlsen@besd.net|435-734-4800
Cache School District|Todd McKee|todd.mckee@ccsdut.org|435-752-3925
Canyons School District|Rick Robins|rick.robins@canyonsdistrict.org|801-826-5000
Carbon School District|Mika Salas|salasm@carbonschools.org|435-637-1732
Daggett School District|E. Bruce Northcott|bnorthcott@dsdf.org|435-784-3174
Davis School District|Dan Linford|dlinford@dsdmail.net|801-402-5258
Duchesne School District|Jason Young|jyoung@dcsd.org|435-823-1281
Emery School District|Jim Shank|james@emeryschools.org|435-687-9846
Garfield School District|John Dodds|jdodds@garfk12.org|435-676-8821
Grand School District|Tayrn Kay|kayt@grandschools.org|435-259-5317
Granite School District|Ben Horsley|bhorsley@graniteschools.org|385-646-5000
Iron School District|Lance Hatch|lance.hatch@ironmail.org|435-586-2804
Jordan School District|Anthony Godfrey|superintendent@jordandistrict.org|801-567-8100
Juab School District|Kodey Hughes|kodey.hughes@juabsd.org|435-623-1940
Kane School District|Ben Dalton|daltonb@kane.k12.ut.us|435-644-2555
Logan School District|Frank Schofield|frank.schofield@loganschools.org|435-755-2300
Millard School District|Randy Hunter|randy@millardk12.org|435-864-1000
Morgan School District|Andy Jensen|ajensen@morgansd.org|801-829-3411
Murray School District|Jennifer Covington|jcovington@murrayschools.org|801-264-7400
Nebo School District|Rick Nielsen|rick.nielsen@nebo.edu|801-354-7400
North Sanpete School District|Odee Hansen|odee.hansen@nsanpete.org|435-462-2485
North Summit School District|Wade Murdock|wmurdock@nsummit.org|435-336-5654
Ogden School District|Luke Rasmussen|rasmussenl@ogdensd.org|801-737-7300
Park City School District|Lyndsay Huntsman|lhuntsman@pcschools.org|435-645-5600
Piute School District|Koby Willis|koby.willis@piutek12.org|435-577-2912
Provo School District|Wendy Dau|wendyd@provo.edu|801-374-4800
Rich School District|Dale Lamborn|dlamborn@richschool.org|435-793-2135
Salt Lake City School District|Elizabeth Grant|elizabeth.grant@slcschools.org|801-578-8599
San Juan School District|Christine Fitzgerald|cfitzgerald@sjsd.org|435-678-1200
Sevier School District|Cade J. Douglas|cade.douglas@seviersd.org|435-896-8214
South Sanpete School District|Ralph Squire|ralph.squire@ssanpete.org|435-835-2261
South Summit School District|Greg Maughan|greg.maughan@ssummit.org|435-783-4301
Tintic School District|Gregory Thornock|gthornock@tintic.org|435-433-6363
Tooele School District|Mark Ernst|mernst@tooeleschools.org|435-833-1900
Uintah School District|Rick Woodford|rick.woodford@uintah.net|435-781-3100
Wasatch School District|Garrick Peterson|garrick.peterson@wasatch.edu|435-654-0280
Washington School District|Richard Holmes|richard.holmes@washk12.org|435-673-3553
Wayne School District|Randy Shelley|randy.shelley@waynesd.org|435-425-3813
Weber School District|Gina Butters|gbutters@wsd.net|801-476-7800"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_ak_records():
    """Alaska - from ACSA superintendent contact sheet PDF."""
    raw = """Alaska Gateway School District|Patrick Mayer|pmayer@agsd.us|(907) 883-5151
Anchorage School District|Dr. Jharrett Bryantt|bryantt_jharrett@asdk12.org|(907) 742-4312
Bristol Bay Borough School District|Shannon Harvilla|superintendent@bbbsd.net|(907) 246-4225
Copper River School District|Theresa Laville|tlaville@crsd.us|(907) 822-3234
Delta/Greely School District|Michael Lee|mlee@dgsd.us|(907) 895-4657
Fairbanks North Star Borough School District|Dr. Luke Meinert|luke.meinert@k12northstar.org|(907) 452-2000
Hoonah City School District|Howard Diamond|howarddiamond@yahoo.com|(907) 945-3611
Aleutians East Borough School District|Mike Franklin|mfranklin@aebsd.org|(907) 383-5222
Aleutian Region School District|Michael Hanley|mhanley@aleutregion.org|(907) 277-2648
Bering Strait School District|Tammy Dodd|tdodd@bssd.org|(907) 624-4261
Chugach School District|Ty Mase|tmase@chugachschools.com|(907) 522-7400
Craig City School District|Jackie Hanson|jhanson@craigschools.org|(907) 826-3274
Dillingham City School District|Amy Brower|abrower@dlgsd.org|(907) 842-5223
Haines Borough School District|Dr. Roy Getchell|rgetchell@hbsd.net|(907) 766-6725
Iditarod Area School District|John Bruce|johnbruce@iditarodsd.org|(907) 524-1221
Juneau School District|Frank Hauser|frank.hauser@juneauschools.org|(907) 523-1702
Kenai Peninsula Borough School District|Clayton Holland|cholland@kpbsd.k12.ak.us|(907) 714-8888
Kodiak Island Borough School District|Dr. Cyndy Mika|cyndy.mika@kibsd.org|(907) 486-7550
Lower Kuskokwim School District|Suzzuk Huntington|suzzukh@mehs.us|(907) 966-3201
North Slope Borough School District|David Vadiveloo|david.vadiveloo@nsbsd.org|(907) 852-5311
Kashunamiut School District|Jeanne Campbell|jcampbell@chevakschool.org|(907) 858-7713
Klawock City School District|Jim Holien|jim.holien@klawockschool.com|(907) 755-2917
Lake and Peninsula School District|Kasie Luke|kluke@lpsd.com|(907) 313-3841
Matanuska-Susitna Borough School District|Dr. Randy Trani|randy.trani@matsuk12.us|(907) 746-9272
Nome Public Schools|Jamie Burgess|jburgess@nomeschools.org|(907) 443-2231
Pelican City School District|Brett Agenbroad|bagenbroad@pelicanschools.org|(907) 735-2236
Sitka School District|Deidre Jenson|jensond@sitkaschools.org|(907) 966-1251
Skagway School District|Dr. Joshua Coughran|jcoughran@skagwayschool.org|(907) 983-2960
St. Mary's School District|Troy Poage|tpoage@smcsd.us|(907) 438-2411
Wrangell Public School District|Bill Burr|bburr@wpsd.us|(907) 874-2347
Yukon-Koyukuk School District|Kerry Boyd|kboyd@yksd.com|(907) 374-9400
Southwest Region School District|Audra Finkenbinder|afinkenbinder@swrsd.org|(907) 842-5287
Valdez City School District|Jason Weber|jweber@valdezcityschools.org|(907) 835-4357
Yukon Flats School District|Dr. Debbe Lancaster|debbe.lancaster@yfsd.org|(907) 662-2515
Yupiit School District|George Ballard|sballard@yupiit.org|(907) 825-3600
Kuspuk School District|Hannibal Anderson|handerson@kuspuk.org|(907) 795-3218
Lower Yukon School District|John Hargis|jhargis@lysd.org|(907) 591-2411
Galena City School District|Shannon Harvilla|sharvilla@galenanet.com|(907) 656-1205
Hydaburg City School District|Theresa Laville|tlaville@hydaburg.k12.ak.us|(907) 285-3491
Ketchikan Gateway Borough School District|Michael Robbins|michael.robbins@k21schools.org|(907) 247-2109
Northwest Arctic Borough School District|Suzzuk Huntington|shuntington@nwarctic.org|(907) 442-3472
Petersburg School District|Robyn Taylor|rtaylor@pcsd.us|(907) 772-3661"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


def get_hi_records():
    return [make_record('Hawaii Department of Education', 'Keith Hayashi', '', '(808) 586-3230')]


def get_dc_records():
    return [make_record('District of Columbia Public Schools', 'Dr. Lewis Ferebee',
                        'lewis.ferebee@k12.dc.gov', '(202) 442-5885')]


def get_nv_records():
    """Nevada - 17 county districts plus a few others."""
    raw = """Clark County School District|Jesus Jara|jjara@nv.ccsd.net|(702) 799-5000
Washoe County School District|Susan Enfield|senfield@washoeschools.net|(775) 348-0200
Carson City School District|Andrew Feuling|feuling@carsoncityschools.com|(775) 283-2000
Churchill County School District|Summer Stephens|sstephens@churchillcsd.com|(775) 423-5184
Douglas County School District|Keith Lewis|keith.lewis@dcsd.k12.nv.us|(775) 782-5131
Elko County School District|Michael Cuesta|mcuesta@ecsdnv.net|(775) 738-5196
Esmeralda County School District|Jason Bowers|jbowers@ecsdnv.com|(775) 485-6373
Eureka County School District|Brent Southwick|bsouthwick@eurekaschools.org|(775) 237-5337
Humboldt County School District|David Jensen|djensen@hcsdnv.com|(775) 623-8100
Lander County School District|David Jensen|djensen@landercountysd.org|(775) 635-2886
Lincoln County School District|Kelly Workman|kworkman@lcsdnv.com|(775) 728-4471
Lyon County School District|Wayne Workman|wworkman@lyoncsd.org|(775) 463-6800
Mineral County School District|Jeffrey Towne|jtowne@mineralcountyschooldistrict.net|(775) 945-2403
Nye County School District|Sam Scovell|sscovell@nyeschools.org|(775) 482-6248
Pershing County School District|Warren Dodge|wdodge@pcsdnv.com|(775) 273-7573
Storey County School District|Todd Hess|thess@storeycountyschools.org|(775) 847-0945
White Pine County School District|Adam Young|ayoung@wpcsd.org|(775) 289-4846"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    print("=" * 70)
    print("Superintendent Contact Import - 22 States/Territories")
    print("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS, verify=False)

    # State configurations: (state_code, data_function, uses_client)
    states = [
        ('MS', lambda: get_ms_records(), False),
        ('ID', None, False),  # No data source found
        ('NM', None, False),  # No data source found
        ('AL', None, False),  # Will use PDF-extracted data below
        ('MD', lambda: get_md_records(), False),
        ('WV', lambda: get_wv_records(), False),
        ('TN', lambda: get_tn_data(), False),
        ('KY', lambda: get_ky_data(client), True),
        ('WY', None, False),  # No accessible data source
        ('RI', lambda: get_ri_records(), False),
        ('HI', lambda: get_hi_records(), False),
        ('AK', lambda: get_ak_records(), False),
        ('DE', lambda: get_de_records(), False),
        ('DC', lambda: get_dc_records(), False),
        ('PR', None, False),
        ('VI', None, False),
        ('GU', None, False),
        ('AS', None, False),
        ('MP', None, False),
        ('BI', None, False),
        ('NV', lambda: get_nv_records(), False),
        ('UT', lambda: get_ut_records(), False),
    ]

    # Alabama PDF data (extracted from ALSDE PDF)
    al_data = get_al_pdf_data()

    results = []
    total_inserted = 0
    total_districts = 0

    for state_code, data_func, uses_client in states:
        db_lookup, n_districts = get_db_districts(cur, state_code)
        existing = get_existing_contacts(cur, state_code)

        if n_districts == 0:
            results.append((state_code, 0, 0))
            continue

        # Get records
        records = []
        if state_code == 'AL':
            records = al_data
        elif data_func:
            try:
                records = data_func()
            except Exception as e:
                print(f"  {state_code}: Data function error: {e}")

        if records:
            inserted = insert_contacts(cur, conn, records, db_lookup, existing, state_code)
        else:
            inserted = 0
            if state_code not in ('PR', 'VI', 'GU', 'AS', 'MP', 'BI', 'ID', 'NM', 'WY'):
                print(f"  {state_code}: No records available")

        pct = (inserted / n_districts * 100) if n_districts > 0 else 0
        print(f"  {state_code}: {inserted} contacts inserted / {n_districts} districts ({pct:.0f}%)")
        results.append((state_code, inserted, n_districts))
        total_inserted += inserted
        total_districts += n_districts

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

    # Grand total
    cur.execute("SELECT COUNT(*) FROM contacts WHERE role = 'superintendent'")
    grand_total = cur.fetchone()[0]
    print(f"\n  GRAND TOTAL superintendent contacts in DB: {grand_total}")

    cur.close()
    conn.close()
    client.close()
    print("\nDone!")


def get_al_pdf_data():
    """Alabama - extracted from ALSDE Directory PDF."""
    raw = """Alabama Aerospace and Aviation|Ruben Morris||(205) 538-0702
Alabama Youth Services|Dr. Tracy Smitherman||(334) 215-3856
Alabaster City|Wayne Vickers||(205) 663-8400
Albertville City|Johnathan Bart Reeves||(256) 891-1183
Alexander City|Jose Reyes Jr.||(256) 496-1262
Andalusia City|Daniel Shakespeare||(334) 222-7569
Anniston City|Dr. Donna Ray Hill||(256) 231-5000
Arab City|Johnny Clyde Berry III||(256) 586-6011
Athens City|Beth Patton||(256) 233-6600
Attalla City|Jeffrey Brian Colegrove||(256) 459-7017
Auburn City|Cristen P Herring||(334) 887-2100
Autauga County|Lyman Randall Woodfin||(334) 387-1910
Baldwin County|Carl Edward Tyler Jr.||(251) 937-0308
Barbour County|Keith Allen Stewart||(334) 775-3453
Bessemer City|Dana Nicole Arreola||(205) 235-8246
Bibb County|Kevin Cotner||(205) 938-2451
Birmingham City|Mark Anthony Sullivan||(205) 231-4600
Blount County|Rodney P Green||(205) 775-1950
Boaz City|Gregory Todd Haynie||(256) 593-9211
Brewton City|Kevin Wieseman||(251) 867-8400
Bullock County|Sean C Dees||(334) 738-2860
Butler County|Joseph C Eiland||(334) 382-2665
Calhoun County|Charles Anthony Willis||(256) 552-3000
Chambers County|Casey Brian Chambley Sr.||(334) 705-6020
Cherokee County|Michael Lee Welsh||(256) 447-7045
Chickasaw City|Jodie Mcpherson||(251) 380-8114
Chilton County|Harold Corey Clements||(205) 646-0303
Choctaw County|Jacquelyn Tatum James||(205) 459-3031
Clarke County|Ashlie Adams Flowers||(251) 250-2155
Clay County|Jared Keith Wesley||(256) 396-1466
Cleburne County|David F. Howle||(256) 591-6331
Coffee County|Kelly Cobb||(334) 897-5016
Colbert County|J. Christopher Hand||(256) 386-8565
Conecuh County|Tonya A Bozeman||(251) 578-2576
Coosa County|David Wayne Stover||(256) 377-1490
Covington County|Kristi July||(251) 307-1863
Crenshaw County|Gregory Scott Faught||(334) 335-6519
Cullman City|Kyle Kallhoff||(256) 734-2233
Cullman County|Shane Barnette||(256) 734-2933
Dale County|Benjamin Earl Baker||(334) 774-2355
Daleville City|Joshua W Robertson||(334) 598-2456
Dallas County|Anthony Sampson||(334) 407-8066
Decatur City|Stephen Michael Douglas||(256) 552-3000
DeKalb County|Wayne Lyles||(256) 845-7501
Demopolis City|Bobby Hathcock||(334) 289-1670
Dothan City|Dennis R Coe||(334) 793-1397
Elmore County|Richard E Dennis||(334) 567-1200
Enterprise City|Meredith Davis||(334) 347-6900
Escambia County|Michele Collier||(251) 867-6251
Etowah County|Robert Alan Cosby||(256) 549-7560
Eufaula City|Patrick Joseph Brannan Jr.||(334) 687-1100
Fairfield City|Regina D. Thompson||(205) 783-6850
Fayette County|James Clifton Burkhalter||(205) 932-4611
Florence City|Jimmy D Shaw Jr.||(256) 768-3016
Fort Payne City|Brian Jett||(256) 845-0535
Franklin County|Gregory Gene Hamilton||(256) 332-1360
Gadsden City|Roblin Webb||(256) 549-7500
Geneva City|Ronald L Snell||(334) 684-1090
Geneva County|Becky Birdsong||(334) 684-5690
Greene County|Corey Lee Jones||(205) 372-3214
Gulf Shores City|Matthew Akin||(251) 968-7395
Guntersville City|Jason Brent Barnett||(256) 524-3277
Hale County|Michael Corey Ryans||(334) 624-8836
Haleyville City|Holly W Sutherland||(205) 486-3122
Hartselle City|Brian Clayton||(256) 216-5313
Henry County|Lori P Beasley||(334) 585-2206
Homewood City|Justin Michael Hefner||(205) 624-3702
Hoover City|Kevin Maddox||(205) 259-0947
Houston County|Brandy Alexander White||(334) 792-5744
Huntsville City|Clarence Sutton Jr.||(256) 428-6800
Jackson County|David Withun||(256) 259-9500
Jacksonville City|Micheal Guy Barber||(256) 782-5947
Jasper City|Ann Jackson||(205) 384-6880
Jefferson County|Walter B Gonsoulin Jr.||(205) 379-2001
Lamar County|Alan Vance Herron||(205) 695-7615
Lanett City|Jennifer S Boyd||(334) 644-5900
Lauderdale County|Jerry Bradley Hill||(256) 757-2115
Lawrence County|Jon Bret Smith||(256) 905-2400
Lee County|Stanley Michael Howard||(334) 749-7044
Leeds City|John Joseph Moore Jr.||(205) 699-5437
Limestone County|Charles Randall Shearouse||(256) 232-5353
Linden City|Timothy Thurman||(334) 295-8802
Lowndes County|Samita Jeter||(334) 548-2145
Macon County|Melissa T Williams||(334) 727-1600
Madison City|Edwin C Nichols Jr.||(256) 464-8370
Madison County|Kenneth Kubik||(256) 852-2557
Marengo County|Kalvin Emanuel Eaton||(334) 295-3626
Marion County|Ann D West||(205) 921-3191
Marshall County|Cindy Wigley||(256) 582-3171
Midfield City|Shun Travace Williams||(205) 923-2262
Mobile County|Chresal Threadgill||(251) 221-4000
Monroe County|Greg Shehan||(251) 575-3156
Montgomery County|Melvin James Brown||(334) 223-6700
Morgan County|Tracie Renea Turrentine||(256) 286-3396
Mountain Brook City|Richard C Barlow||(205) 871-4608
Muscle Shoals City|Chad D. Holden||(256) 389-2600
Oneonta City|Craig W Sosebee||(205) 625-4402
Opelika City|Farrell B Seymore||(334) 745-9715
Opp City|Emily Edgar||(334) 493-3173
Orange Beach City|Robbie Smith||(251) 981-1200
Oxford City|William R. Wilkes||(256) 241-3100
Ozark City|Reeivice L. Girtman||(334) 774-5197
Pelham City|Charles L. Ledbetter Jr.||(205) 624-3700
Pell City|James Martin||(205) 884-4440
Perry County|Marcia A. Smiley||(334) 683-6528
Phenix City|Zachary Frey||(334) 298-0534
Pickens County|James W Chapman Jr.||(205) 367-2080
Piedmont City|Mike Hayes||(256) 447-8831
Pike County|Samuel Mark Bazzell||(334) 566-1850
Pike Road City|Daniel Keith Lankford||(334) 420-5300
Randolph County|John Jacobs||(256) 357-4611
Roanoke City|Gregory Donnell Foster||(334) 539-5266
Russell County|Brenda Johnson Coley||(334) 468-5540
Russellville City|Timothy J Guinn||(256) 331-2110
Saraland City|Justin Brent Harrison||(251) 602-8970
Satsuma City|Dana Lynn Price||(251) 380-8231
Scottsboro City|Amy M. Childress||(256) 218-2116
Selma City|Darryl Vashon Aikerson||(334) 874-1600
Sheffield City|Carlos M. Nelson||(256) 383-0400
Shelby County|Lewis Brooks||(205) 682-7052
St Clair County|Justin David Burns||(205) 594-7131
Sumter County|Marcy Burroughs||(205) 652-9605
Sylacauga City|Michele Eller||(256) 249-0305
Talladega City|Quentin Jerome Lee||(256) 315-5635
Talladega County|Suzanne Lacey||(256) 315-5104
Tallapoosa County|Casey D Davis||(256) 825-0746
Tallassee City|Joshua Brock Nolin||(334) 283-2151
Tarrant City|Sherlene Mcdonald||(205) 849-3700
Thomasville City|Vickie R Morris||(334) 636-9955
Troy City|Cynthia G. Thomas||(334) 566-3741
Trussville City|Patrick M Martin||(205) 228-3018
Tuscaloosa City|Mike Daria||(205) 759-3523
Tuscaloosa County|Keri Cosper Johnson||(205) 342-2700
Tuscumbia City|Russell Ivan Tate||(256) 389-2900
Vestavia Hills City|Michael Todd Freeman||(205) 402-5116
Walker County|Dennis Ray Willingham||(205) 387-0555
Washington County|Lisa L Connell||(251) 847-2401
Wilcox County|Andre P. Saulsberry||(334) 682-4716
Winfield City|Randy Thomley||(205) 487-6900
Winston County|Gregory Pendley||(205) 489-5018"""
    records = []
    for line in raw.strip().split('\n'):
        parts = line.split('|')
        if len(parts) == 4:
            records.append(make_record(parts[0], parts[1], parts[2], parts[3]))
    return records


if __name__ == '__main__':
    main()
