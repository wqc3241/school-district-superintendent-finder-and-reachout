# Data Sources

## Federal Sources

- **NCES Common Core of Data (CCD)**: https://nces.ed.gov/ccd/files.asp
  - District names, addresses, phones, ELL student counts
  - Updated annually (1-2 year lag)
  - Used for: baseline district universe (19,263 districts across all 50 states + DC + territories)

- **Urban Institute Education Data Portal**: https://educationdata.urban.org/
  - ELL counts, Title I/III funding, district demographics
  - Used for: enriching district records with demographic and funding data

- **Ed Data Express**: https://eddataexpress.ed.gov/
  - Title I and Title III funding allocations
  - Used for: identifying districts with federal ESL/ELL funding

## State DOE Sources

| State | Source | URL | Data Available | Contacts | Last Verified |
|-------|--------|-----|---------------|----------|---------------|
| FL | FL Dept of Education - Education Directory | https://www.fldoe.org/accountability/data-sys/school-dis-data/superintendents.stml | Name, email, phone | 67 | 2026-03-17 |
| CA | CA Dept of Education - Public Schools File | https://www.cde.ca.gov/ds/si/ds/pubschls.asp | Name, phone (no emails) | 1,032 | 2026-03-17 |
| TX | TX Education Agency - AskTED Directory | https://tea4avholly.tea.state.tx.us/tea.askted.web/Forms/Home.aspx | Name, email, phone | 1,166 | 2026-03-17 |
| NY | NY State Education Dept - School Directory | https://schoolconn.nysed.gov/ | Name, phone (no emails) | 646 | 2026-03-17 |
| IL | IL State Board of Education - Directory | https://www.isbe.net/Pages/Illinois-State-Board-of-Education-School-Directory.aspx | Name, phone (no emails) | 841 | 2026-03-17 |
| MA | MA Dept of Elementary & Secondary Education | https://profiles.doe.mass.edu/ | Name, email, phone | 370 | 2026-03-17 |
| WA | WA Office of Superintendent of Public Instruction | https://www.k12.wa.us/data-reporting/data-portal | Name, email, phone | 292 | 2026-03-17 |
| OR | OR Dept of Education - Institution Directory | https://www.oregon.gov/ode/schools-and-districts/Pages/default.aspx | Name, email (partial), phone | 202 | 2026-03-17 |
| NJ | NJ Dept of Education - Directory | https://www.nj.gov/education/directory/ | Name, phone (no emails) | 506 | 2026-03-17 |
| IN | IN Dept of Education - School Directory | https://www.in.gov/doe/it/data-center-and-reports/ | Name, email (90%), phone | 420 | 2026-03-17 |
| MO | MO Dept of Elementary & Secondary Education - School Directory | https://dese.mo.gov/school-directory | Name, email, phone | 503 | 2026-03-17 |
| MT | MT Office of Public Instruction - Searchable Directory | https://opi.mt.gov/Leadership/Data-Reporting/Searchable-Directory | Name, email (no phones) | 231 | 2026-03-17 |
| OK | OK State Dept of Education - State School Directory | https://oklahoma.gov/education/resources/state-school-directory.html | Name, email, phone | 507 | 2026-03-17 |
| KS | KS State Dept of Education - Kansas Education Directory | https://www.ksde.org/Agency/Fiscal-and-Administrative-Services/School-Finance/Directory | Name, email, phone | 278 | 2026-03-17 |

## Enrichment Sources (Paid APIs)

- **Apollo.io**: https://www.apollo.io/
  - Email discovery and verification for contacts missing emails
  - Used for: supplementing state DOE data where emails are not published

- **Hunter.io**: https://hunter.io/
  - Email finder and domain search
  - Used for: discovering email patterns for school district domains

- **Mailgun**: https://www.mailgun.com/
  - Email verification (deliverability checking)
  - Used for: verifying scraped email addresses before outreach

## Data Quality Notes

- NCES data has a 1-2 year lag; district names and boundaries may be slightly outdated
- State DOE directories are the primary source for superintendent names
- Superintendent turnover is approximately 15-20% per year; data should be refreshed biweekly to monthly
- Confidence scores are algorithmically assigned: 90 = name + email from DOE source, 85 = name + phone only, 80 = name from secondary source
- No contacts have been formally verified via email_verified_at (all NULL); confidence scores reflect source reliability

## Verification Results (2026-03-17)

| State | Sample Size | Verified | Accuracy | Notes |
|-------|------------|----------|----------|-------|
| IN | 16 | 4/4 accessible | 100% | Scott Wyndham, Joseph Cronk, Byron Sanders, Kerry Johnson confirmed |
| OK | 15 | 2/3 accessible | 67% | Pat Liticker confirmed; Steven Spangler (Achille) MISMATCH - actual is Rick Beene |
| MO | 10 | 1/1 accessible | 100% | Aaron Dalton (Ava R-I) confirmed |
| MT | 10 | 0/0 accessible | N/A | All sampled district websites returned no parseable content |
| KS | 10 | 2/2 accessible | 100% | Brett White (Andover), Mark Dodge (Baldwin City) confirmed |
| FL | -- | -- | -- | Previously verified |
| CA | -- | -- | -- | Previously verified |
| TX | -- | -- | -- | Previously verified |
| NY | -- | -- | -- | Previously verified |
| IL | -- | -- | -- | Previously verified |
| MA | -- | -- | -- | Previously verified |
| WA | -- | -- | -- | Previously verified |
| OR | -- | -- | -- | Previously verified |
| NJ | -- | -- | -- | Previously verified |
