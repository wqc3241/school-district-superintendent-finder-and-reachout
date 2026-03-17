# School District Superintendent Finder & Outreach

A lead generation and outreach platform that helps EdTech companies find and contact school district superintendents across the United States — specifically targeting districts with ESL/ELL programs funded by Title I and Title III federal grants.

## Live Demo

https://school-district-superintendent-find.vercel.app/

## The Problem

EdTech companies building ESL/ELL learning tools need to reach school district decision-makers, but:
- There's no single directory of all U.S. school district superintendents
- Contact info is scattered across 50+ state DOE websites with different formats
- Identifying which districts have active ESL programs requires cross-referencing federal funding data
- Cold outreach must comply with CAN-SPAM and education sector norms

## The Solution

This platform automates the entire pipeline:

1. **Discover** — Scrape superintendent contact info from state DOE directories
2. **Enrich** — Cross-reference with NCES federal data for ELL student counts, Title I/III funding
3. **Verify** — Validate emails, deduplicate records, standardize phone numbers
4. **Reach Out** — Run personalized, multi-step email campaigns with tracking

## Current Data

| Metric | Count |
|--------|-------|
| School Districts | 19,263 |
| Superintendent Contacts | 6,783+ |
| Contacts with Email | 3,664+ |
| States with Contact Data | 9 (FL, CA, TX, NY, IL, MA, WA, OR, NJ) |
| Title I Funded Districts | 7,440+ |

## Features

### Dashboard
- Real-time stats: districts, contacts, email verification rates, campaign performance
- Activity feed for recent outreach events

### District Browser
- Browse all 19,263 U.S. school districts
- Filter by state, ESL program status, funding type (Title I, Title III, or both)
- Sort by any column: name, ELL students, ELL %, funding amounts
- View Title I and Title III funding badges

### Contact Manager
- Search and filter superintendent contacts by name, state, role, email status
- Sort by confidence score, district, or any column
- Bulk actions: add to campaign, verify emails, export CSV

### Campaign Engine
- Multi-step email sequences with configurable delays
- Jinja2 templates with personalization variables (district name, ELL count, funding amount)
- Mailgun integration with warmup controls and daily sending limits
- Webhook-based tracking: opens, clicks, bounces, replies, unsubscribes
- Auto-pause on high bounce/complaint rates (CAN-SPAM compliance)

### Email Templates
- Pre-built outreach templates for ESL product sales
- Variable insertion: `{{contact.first_name}}`, `{{district.name}}`, `{{district.ell_students}}`
- A/B testing support

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 16, React, shadcn/ui, Tailwind CSS |
| API | Next.js API Routes (serverless on Vercel) |
| Database | PostgreSQL on Supabase |
| Backend | Python 3.12+ / FastAPI (campaign processing) |
| Task Queue | Celery + Redis |
| Email | Mailgun |
| Scraping | httpx, BeautifulSoup, rapidfuzz |
| Hosting | Vercel (frontend), Supabase (database) |

## Project Structure

```
backend/
├── app/                    # FastAPI application
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic validation
│   ├── api/                # REST endpoints
│   ├── services/           # Business logic
│   └── tasks/              # Celery tasks
├── scrapers/
│   ├── nces/               # Federal data importers (CCD, Title I, Title III)
│   ├── states/             # State DOE scrapers (9 states)
│   ├── enrichment/         # Email verification + contact enrichment
│   └── pipeline.py         # Scrape → normalize → match → dedup → verify → store
frontend/
├── src/app/                # Next.js pages + API routes
├── src/components/         # UI components
├── src/hooks/              # Custom hooks (sorting)
├── src/lib/                # Utilities (DB, API client, formatters)
└── src/types/              # TypeScript interfaces
```

## Data Sources

| Source | Data | Cost | Update Frequency |
|--------|------|------|-----------------|
| NCES Common Core of Data | 19,263 districts: addresses, phones, ELL counts | Free | Annual |
| Ed Data Express | Title I & III funding allocations | Free | Annual |
| State DOE Directories | Superintendent names, emails, phones | Free | Weekly–Quarterly |
| Apollo.io / Hunter.io | Email discovery & enrichment | Freemium | On-demand |
| Mailgun Validate | Email deliverability verification | Included | On-demand |

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.12+
- PostgreSQL (or Supabase account)

### Frontend Setup
```bash
cd frontend
npm install
echo "DATABASE_URL=your_supabase_connection_string" > .env.local
npm run dev
```

### Backend Setup (for campaign processing)
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database and Mailgun credentials
uvicorn app.main:app --port 8001
```

### Import District Data
```bash
cd backend
python -m scrapers.nces.ccd_importer    # Import 19,263 districts
python -m scrapers.nces.title_i         # Import Title I funding data
python -m scrapers.nces.title_iii       # Import Title III funding data
```

## Legal Compliance

- **CAN-SPAM:** Every email includes physical address, unsubscribe link, honest headers
- **FERPA:** Does not apply — superintendent contact info is public employee data
- **Scraping:** Only public government directories; robots.txt respected
- **No FOIA abuse:** Uses published directories, not commercial FOIA requests

## License

MIT
