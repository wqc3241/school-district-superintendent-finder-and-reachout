"""School District Superintendent data scraping pipeline.

This package provides scrapers for federal (NCES) and state DOE data,
contact enrichment/verification services, and an orchestration pipeline
that normalizes, deduplicates, and stores superintendent contact records.
"""

from scrapers.base import BaseSpider
from scrapers.pipeline import run_pipeline

__all__ = ["BaseSpider", "run_pipeline"]
