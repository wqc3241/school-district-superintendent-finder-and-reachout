# School District Superintendent Finder & Outreach

## Product Overview
A full-stack SaaS tool that automatically finds superintendent contact information for U.S. school districts (especially those with ESL programs receiving Title I and Title III federal funding) and manages personalized email outreach campaigns.

**Target Customer:** EdTech companies selling ESL/ELL teaching tools to school districts.

**Value Proposition:** Automate the discovery of ~13,000+ school district decision-makers and run compliant cold outreach campaigns to sell ESL learning materials.

## Architecture

### Tech Stack
- **Backend:** Python 3.12+ / FastAPI (async)
- **Database:** PostgreSQL on Supabase (project ref: `mymxwesilduzjfniecky`, region: `us-west-2`)
- **Task Queue:** Celery + Redis
- **Email Provider:** Mailgun (cold outreach tolerant, inbound routing for reply detection)
- **Frontend:** Next.js 16 + shadcn/ui + Tailwind CSS
- **Scraping:** httpx + BeautifulSoup + rapidfuzz (for fuzzy matching)

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
│   ├── states/             # State DOE superintendent scrapers (FL, CA, TX, NY, IL)
│   ├── enrichment/         # Email verification (Mailgun) + contact enrichment (Hunter/Apollo)
│   └── pipeline.py         # Orchestrator: scrape → normalize → fuzzy-match → dedup → verify → store
frontend/
├── src/app/                # Next.js pages (dashboard, districts, contacts, campaigns, templates, settings)
├── src/components/         # Sidebar nav + shadcn/ui components
├── src/lib/                # API client, mock data, formatters
└── src/types/              # TypeScript interfaces
```

### Database Schema (Supabase)
10 tables: `districts`, `contacts`, `contact_sources`, `campaigns`, `campaign_steps`, `campaign_enrollments`, `email_templates`, `email_messages`, `email_events`, `users`

- **NCES ID** is the golden key for deduplication across data sources
- Districts track both `title_i_allocation` and `title_iii_allocation`
- Contacts have `email_status` (unverified/valid/invalid/risky/unknown) and `confidence_score` (0-100)
- Campaign enrollments track `next_send_at` for Celery Beat processing

## Data Sources
- **NCES CCD** (free): 13,300+ districts with addresses, phones, ELL student counts
- **Ed Data Express** (free): Title I and Title III funding allocations by district
- **State DOE Directories** (free): Superintendent names and emails (scraped from 50 state sites)
- **Enrichment APIs** (paid): Apollo.io, Hunter.io for email discovery; Mailgun for verification

## Legal Compliance
- **CAN-SPAM:** Physical address footer + unsubscribe link on every email
- **FERPA:** Does NOT apply (superintendent data is public employee info, not student data)
- **Scraping:** Public government directories are lowest legal risk; respect robots.txt
- **No FOIA:** Use published directories only (many states restrict commercial FOIA use)

## Key Commands
```bash
# Frontend (runs in mock mode without backend)
cd frontend && npm run dev        # http://localhost:3000

# Backend
cd backend && uvicorn app.main:app --reload   # http://localhost:8000

# Import NCES data
cd backend && python -m scrapers.nces.ccd_importer
cd backend && python -m scrapers.nces.title_i
cd backend && python -m scrapers.nces.title_iii

# Celery worker + beat
cd backend && celery -A app.tasks.celery_app worker --loglevel=info
cd backend && celery -A app.tasks.celery_app beat --loglevel=info
```

## Development Notes
- Frontend runs fully in mock data mode when `NEXT_PUBLIC_API_URL` is not set
- Mailgun warmup schedule: start at 20-50/day, ramp over 8 weeks to 1000-2000/day
- Campaign processor runs every 60 seconds via Celery Beat
- Email templates use Jinja2 with `StrictUndefined` — missing variables cause errors, not blank sends
- Superintendent turnover is ~15-20%/year — scrapers should run biweekly to monthly
