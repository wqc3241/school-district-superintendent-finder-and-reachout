# School District Superintendent Finder & Outreach

## Product Overview
A full-stack SaaS tool that automatically finds superintendent contact information for U.S. school districts (especially those with ESL programs receiving Title I and Title III federal funding) and manages personalized email outreach campaigns.

**Target Customer:** EdTech companies selling ESL/ELL teaching tools to school districts.

**Value Proposition:** Automate the discovery of 19,000+ school district decision-makers and run compliant cold outreach campaigns to sell ESL learning materials.

## Architecture

### Tech Stack
- **Frontend:** Next.js 16 + shadcn/ui + Tailwind CSS (deployed on Vercel)
- **Database:** PostgreSQL on Supabase (project ref: `mymxwesilduzjfniecky`, region: `us-west-2`)
- **API Layer:** Next.js API routes (serverless on Vercel) — queries Supabase directly via `pg` connection pool
- **Backend (optional):** Python 3.12+ / FastAPI — only needed for campaign processing (Celery), webhooks, email sending
- **Task Queue:** Celery + Redis (for campaign processing and scheduled scraping)
- **Email Provider:** Mailgun (cold outreach tolerant, inbound routing for reply detection)
- **Scraping:** httpx + BeautifulSoup + rapidfuzz (for fuzzy matching)

### Deployment
- **Frontend + API:** Vercel at https://school-district-superintendent-find.vercel.app/
- **Database:** Supabase PostgreSQL (aws-0-us-west-2.pooler.supabase.com)
- **GitHub:** https://github.com/wqc3241/school-district-superintendent-finder-and-reachout

### Project Structure
```
backend/
├── app/                    # FastAPI application
│   ├── models/             # SQLAlchemy models (district, contact, campaign, email, user)
│   ├── schemas/            # Pydantic validation schemas
│   ├── api/                # REST endpoints (districts, contacts, campaigns, webhooks)
│   ├── services/           # Business logic (email rendering, campaign orchestration)
│   └── tasks/              # Celery tasks (campaign processor, scraping, enrichment)
├── scrapers/               # Data collection pipeline
│   ├── nces/               # Federal data importers (CCD, Title I, Title III)
│   ├── states/             # State DOE superintendent scrapers (28 states)
│   ├── enrichment/         # Email verification (Mailgun) + contact enrichment (Hunter/Apollo)
│   └── pipeline.py         # Orchestrator: scrape → normalize → fuzzy-match → dedup → verify → store
frontend/
├── src/app/                # Next.js pages
│   ├── page.tsx            # Dashboard (real-time stats from Supabase)
│   ├── districts/          # District browser with filters and sorting
│   ├── contacts/           # Contact manager with bulk actions and CSV export
│   ├── campaigns/          # Campaign builder (mockup)
│   ├── templates/          # Email templates (mockup)
│   ├── settings/           # App settings (mockup)
│   └── api/                # Next.js API routes (serverless)
│       ├── districts/      # Paginated district queries with server-side sorting
│       ├── contacts/       # Contact queries with district JOIN + server-side sorting
│       ├── dashboard/      # Stats aggregation + activity feed
│       ├── district-filter-options/  # Dynamic filter options with counts
│       ├── filter-options/  # Contact filter options (roles, statuses, states)
│       └── states/         # Distinct state lists
├── src/components/         # Sidebar nav, SortableHeader, Pagination, shadcn/ui
├── src/hooks/              # useSort hook (client-side, for mock data pages)
├── src/lib/                # API client, db.ts (pg pool), sort.ts, export-csv.ts, formatters
└── src/types/              # TypeScript interfaces (all dynamic — no hardcoded enums)
```

### Database Schema (Supabase)
10 tables: `districts`, `contacts`, `contact_sources`, `campaigns`, `campaign_steps`, `campaign_enrollments`, `email_templates`, `email_messages`, `email_events`, `users`

- **NCES ID** is the golden key for deduplication across data sources
- Districts track `title_i_allocation`, `title_iii_allocation`, `ell_student_count`, `ell_percentage`
- Contacts have `role` (string — superintendent/asst_superintendent/esl_director/other), `email_status` (string), `confidence_score` (0-100)
- Campaign enrollments track `next_send_at` for Celery Beat processing
- All filter dropdown values are dynamic from DB (no hardcoded enums)

### Current Data (as of 2026-03-18)
- **19,263 districts** (all 50 states + DC + territories)
- **8,118 contacts** across 28 states
- **4,525 contacts with email**
- **7,452 contacts with phone**
- **15,388 districts with Title I funding** (avg $955,929)
- **12,647 districts with ESL/Title III programs**
- **12,582 districts with ELL student counts** (avg 418 students, 9.56%)
- **42.1% overall contact coverage**
- Data verified: deduplicated, names cleaned, phones standardized, emails validated, roles verified against source DOE websites

### Contact Coverage by State
- **90%+ coverage (10 states):** IN, TX, OR, TN, KY, WV, AL, MS, MD, HI
- **50-89% coverage (13 states):** OK, MO, MA, WA, NE, KS, NV, FL, AK, IL, NJ, NY, RI
- **<50% coverage (5 states):** CA, MT, UT, DE, DC
- **0% coverage (29 states):** OH, MI, PA, AZ, MN, WI, NC, IA, AR, ME, CO, GA, ND, VA, CT, NH, LA, VT, ID, SD, NM, SC, WY + territories
- **Remaining states blocked by:** JS-heavy DOE portals needing Playwright/Selenium

## Data Sources
- **NCES CCD** (free): 19,263 districts with addresses, phones, ELL student counts
- **Urban Institute Education Data Portal** (free): ELL counts, Title I/III funding data
- **State DOE Directories** (free): Superintendent names/emails scraped from 28 state DOE sites
- **Enrichment APIs** (paid): Apollo.io, Hunter.io for email discovery; Mailgun for verification
- See `DATA_SOURCES.md` for complete source list with URLs
- See `contact.md` for per-state tracking with verification status

## Key Features
- **Dashboard:** Real-time stats from Supabase (districts, contacts, funding, coverage)
- **Districts:** Browse 19,263 districts with server-side sorting, filtering by state/ESL/funding type (mutually exclusive: Title I Only, Title III Only, Both)
- **Contacts:** Search/filter 8,118 superintendent contacts, sortable columns, bulk CSV export
- **Pagination:** Page numbers with ellipsis, configurable records per page (10/20/50/100)
- **All filters dynamic:** State, role, email status, ESL, funding type — all populated from DB values with counts
- **Data source disclaimers:** Both pages show sourced DOE links
- **Campaigns/Templates/Settings:** Mockup (marked in sidebar)

## Legal Compliance
- **CAN-SPAM:** Physical address footer + unsubscribe link on every email
- **FERPA:** Does NOT apply (superintendent data is public employee info, not student data)
- **Scraping:** Public government directories are lowest legal risk; respect robots.txt
- **No FOIA:** Use published directories only (many states restrict commercial FOIA use)

## Key Commands
```bash
# Frontend (connects to Supabase via API routes)
cd frontend && npm run dev        # http://localhost:3000

# Backend (optional — for campaign processing)
cd backend && uvicorn app.main:app --port 8001   # http://localhost:8001

# Import NCES data
cd backend && python -m scrapers.nces.ccd_importer
cd backend && python -m scrapers.nces.title_i
cd backend && python -m scrapers.nces.title_iii

# Celery worker + beat (for campaign email sending)
cd backend && celery -A app.tasks.celery_app worker --loglevel=info
cd backend && celery -A app.tasks.celery_app beat --loglevel=info
```

## Environment Variables

### Frontend (.env.local)
```
DATABASE_URL=postgresql://postgres.mymxwesilduzjfniecky:<password>@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
```

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://postgres.mymxwesilduzjfniecky:<password>@aws-0-us-west-2.pooler.supabase.com:5432/postgres?ssl=require
DATABASE_URL_SYNC=postgresql://postgres.mymxwesilduzjfniecky:<password>@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
REDIS_URL=redis://localhost:6379/0
MAILGUN_API_KEY=<key>
MAILGUN_DOMAIN=<domain>
```

### Vercel Environment Variables
```
DATABASE_URL=postgresql://postgres.mymxwesilduzjfniecky:<password>@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
```

## Development Notes
- Frontend uses Next.js API routes (serverless) to query Supabase directly via `pg` Pool — no separate backend needed for read operations
- Backend FastAPI is only needed for campaign processing (Celery), webhooks, and email sending
- SSL config: `pg` Pool strips `sslmode` from connection string and uses `ssl: { rejectUnauthorized: false }`
- Server-side sorting: API routes accept `sort_key` + `sort_dir` params with whitelisted column maps (prevents SQL injection)
- All filter dropdowns populated from DB via `/api/district-filter-options` and `/api/filter-options` — zero hardcoded values
- Funding type filter is mutually exclusive: "Title I Only" excludes districts with Title III, and vice versa
- Build script: `rm -rf .next && next build` to prevent stale TypeScript cache on Vercel
- Types use plain `string` for role/emailStatus (not TypeScript enums) since values come from DB
- Campaigns and templates use mock data (marked "Mockup" in sidebar)
- Mailgun warmup schedule: start at 20-50/day, ramp over 8 weeks to 1000-2000/day
- Campaign processor runs every 60 seconds via Celery Beat
- Email templates use Jinja2 with `StrictUndefined` — missing variables cause errors, not blank sends
- Superintendent turnover is ~15-20%/year — scrapers should run biweekly to monthly
- Contact roles verified against original state DOE sources (91.4% accuracy across 8 verified states)
- 29 states at 0% coverage — blocked by JS-heavy DOE portals, need Playwright or commercial data (MDR Education)
