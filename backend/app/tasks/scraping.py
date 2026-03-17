"""Celery tasks for dispatching web scraping jobs."""

import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_district_website(self, district_id: str, website_url: str) -> dict:
    """Scrape a district website for superintendent contact information.

    This task is dispatched asynchronously. It fetches the district website,
    looks for "About" or "Leadership" pages, and extracts contact details.
    """
    logger.info("Scraping district %s website: %s", district_id, website_url)

    try:
        import httpx
        from bs4 import BeautifulSoup

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(website_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for leadership / about / staff directory links
        leadership_links: list[str] = []
        keywords = ["superintendent", "leadership", "about", "administration", "staff"]
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            href = link["href"]
            if any(kw in link_text or kw in str(href).lower() for kw in keywords):
                if href.startswith("/"):
                    # Make absolute URL
                    from urllib.parse import urljoin

                    href = urljoin(website_url, href)
                if href.startswith("http"):
                    leadership_links.append(href)

        # Extract emails from the main page
        import re

        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        found_emails = set(email_pattern.findall(response.text))

        result = {
            "district_id": district_id,
            "leadership_links": leadership_links[:10],
            "found_emails": list(found_emails),
            "page_title": soup.title.string if soup.title else None,
        }

        logger.info(
            "Scraping complete for %s: found %d links, %d emails",
            district_id,
            len(leadership_links),
            len(found_emails),
        )
        return result

    except Exception as exc:
        logger.error("Scraping failed for %s: %s", district_id, exc)
        raise self.retry(exc=exc)


@celery_app.task
def batch_scrape_districts(district_ids: list[str]) -> dict:
    """Dispatch scraping tasks for a batch of districts.

    This is a coordination task that fans out individual scraping jobs.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    engine = create_engine(settings.database_url_sync)
    dispatched = 0

    with engine.connect() as conn:
        for district_id in district_ids:
            row = conn.execute(
                text("SELECT website FROM districts WHERE id = :id"),
                {"id": district_id},
            ).fetchone()

            if row and row[0]:
                scrape_district_website.delay(district_id, row[0])
                dispatched += 1

    logger.info("Dispatched %d scraping tasks from batch of %d", dispatched, len(district_ids))
    return {"dispatched": dispatched, "total": len(district_ids)}
