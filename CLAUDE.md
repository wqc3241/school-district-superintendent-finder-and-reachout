# School District Superintendent Finder & Outreach

## Product Overview
A full-stack SaaS tool that automatically finds superintendent contact information for U.S. school districts (especially those with ESL programs receiving Title I and Title III federal funding) and manages personalized email outreach campaigns.

**Target Customer:** EdTech companies selling ESL/ELL teaching tools to school districts.

**Value Proposition:** Automate the discovery of 19,000+ school district decision-makers and run compliant cold outreach campaigns to sell ESL learning materials.

## Architecture

### Tech Stack
- **Frontend:** Next.js 16 + shadcn/ui + Tailwind CSS (deployed on Vercel)
- **Database:** PostgreSQL on Supabase (project ref: `mymxwesilduzjfniecky`, region: `us-west-2`)
- **API Layer:** Next.js API routes (serverless on Vercel) + FastAPI (local development)
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
│   ├── states/             # State DOE superintendent scrapers (FL, CA, TX, NY, IL, MA, WA, OR, NJ)
│   ├── enrichment/         # Email verification (Mailgun) + contact enrichment (Hunter/Apollo)
│   └── pipeline.py         # Orchestrator: scrape → normalize → fuzzy-match → dedup → verify → store
frontend/
├── src/app/                # Next.js pages (dashboard, districts, contacts, campaigns, templates, settings)
│   └── api/                # Next.js API routes (serverless — query Supabase directly)
│       ├── districts/      # Paginated district queries with filters
│       ├── contacts/       # Contact queries with district JOIN
│       └── dashboard/      # Stats aggregation + activity feed
├── src/components/         # Sidebar nav, SortableHeader, shadcn/ui components
├── src/hooks/              # useSort hook for client-side sorting
├── src/lib/                # API client, db connection pool, sort utilities, formatters, mock data
└── src/types/              # TypeScript interfaces
```

### Database Schema (Supabase)
10 tables: `districts`, `contacts`, `contact_sources`, `campaigns`, `campaign_steps`, `campaign_enrollments`, `email_templates`, `email_messages`, `email_events`, `users`

- **NCES ID** is the golden key for deduplication across data sources
- Districts track `title_i_allocation`, `title_iii_allocation`, `ell_student_count`, `ell_percentage`
- Contacts have `role` (superintendent/asst_superintendent/esl_director/other), `email_status`, `confidence_score` (0-100)
- Campaign enrollments track `next_send_at` for Celery Beat processing

### Current Data (as of 2026-03-17)
- **19,263 districts** (all 50 states + DC + territories)
- **~6,783 contacts** across 9 states (FL, CA, TX, NY, IL, MA, WA, OR, NJ)
- **~3,664 contacts with verified emails**
- **7,440 districts flagged with Title I funding**
- Data verified: deduplicated, names cleaned, phones standardized, emails validated

## Data Sources
- **NCES CCD** (free): 19,263 districts with addresses, phones, ELL student counts
- **Ed Data Express** (free): Title I and Title III funding allocations by district
- **State DOE Directories** (free): Superintendent names and emails scraped from 9 state sites
- **Enrichment APIs** (paid): Apollo.io, Hunter.io for email discovery; Mailgun for verification

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
- Frontend uses Next.js API routes (serverless) to query Supabase directly — no separate backend needed for read operations
- Backend FastAPI is only needed for campaign processing (Celery), webhooks, and email sending
- SSL config: `pg` Pool uses `ssl: { rejectUnauthorized: false }` and strips `sslmode` from connection string
- All table columns are sortable (client-side) via SortableHeader component + useSort hook
- Campaigns and templates currently use mock data (not yet connected to DB)
- Mailgun warmup schedule: start at 20-50/day, ramp over 8 weeks to 1000-2000/day
- Campaign processor runs every 60 seconds via Celery Beat
- Email templates use Jinja2 with `StrictUndefined` — missing variables cause errors, not blank sends
- Superintendent turnover is ~15-20%/year — scrapers should run biweekly to monthly
- Contact roles verified against original state DOE sources for accuracy
