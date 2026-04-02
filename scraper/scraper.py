"""
Job scraper using python-jobspy — LinkedIn + Indeed + Google Jobs.
Anonymous session only (no credentials needed for public job listings).
"""

import time
import logging
from dataclasses import dataclass

try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False

from . import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Search matrix: (query, location, site_names)
# Keep total queries ≤ 20/day to stay within LinkedIn anonymous rate limits.
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # Core neuromorphic domain
    ("neuromorphic engineer", "Netherlands"),
    ("spiking neural network engineer", "Netherlands"),
    ("brain-inspired computing", "Netherlands"),
    ("neuromorphic AI", "Netherlands"),
    # Neuroengineering
    ("neuroengineering", "Netherlands"),
    ("neurotech scientist", "Netherlands"),
    ("computational neuroscience", "Netherlands"),
    # Edge AI / embedded AI (high volume, add keywords to filter noise)
    ("edge AI scientist", "Netherlands"),
    ("embedded AI engineer", "Netherlands"),
    ("embedded sensing engineer", "Netherlands"),
    # Applied/R&D scientist
    ("R&D scientist sensing", "Netherlands"),
    ("applied scientist signal processing", "Netherlands"),
    ("research scientist neuromorphic", "Netherlands"),
    # Belgium
    ("neuromorphic", "Leuven Belgium"),
    ("neuroengineering", "Leuven Belgium"),
    ("embedded AI", "Eindhoven Netherlands"),
    # Academic postdocs
    ("postdoctoral researcher computational neuroscience", "Netherlands"),
    ("postdoc neuroengineering", "Netherlands"),
]

SITES = ["linkedin", "indeed"]


@dataclass
class RawJob:
    source: str
    url: str
    title: str
    company: str
    location: str
    description: str
    date_posted: str | None


def scrape_all(max_results_per_query: int = 20, delay_between_queries: float = 8.0) -> list[RawJob]:
    """
    Run all search queries and return deduplicated RawJob objects not yet in DB.
    """
    if not JOBSPY_AVAILABLE:
        logger.error("python-jobspy is not installed. Run: pip install python-jobspy")
        return []

    seen_urls: set[str] = set()
    new_jobs: list[RawJob] = []

    for query, location in SEARCH_QUERIES:
        logger.info("Searching: '%s' in %s", query, location)
        try:
            df = scrape_jobs(
                site_name=SITES,
                search_term=query,
                location=location,
                results_wanted=max_results_per_query,
                hours_old=72,           # Only jobs posted in last 3 days
                country_indeed="Netherlands",
                verbose=0,
            )
        except Exception as exc:
            logger.warning("Query '%s' / '%s' failed: %s", query, location, exc)
            time.sleep(delay_between_queries)
            continue

        if df is None or df.empty:
            logger.info("  No results.")
            time.sleep(delay_between_queries)
            continue

        for _, row in df.iterrows():
            url = str(row.get("job_url", "") or "").strip()
            if not url or url in seen_urls:
                continue
            if db.is_seen(url):
                continue
            seen_urls.add(url)

            title = str(row.get("title", "") or "").strip()
            company = str(row.get("company", "") or "Unknown").strip()
            location_str = str(row.get("location", "") or "").strip()
            description = str(row.get("description", "") or "").strip()
            date_posted = str(row.get("date_posted", "") or "").strip() or None
            source = str(row.get("site", "unknown")).strip()

            if not title or not company:
                continue
            if len(description) < 50:
                # Skip stub listings with no real description
                continue

            new_jobs.append(RawJob(
                source=source,
                url=url,
                title=title,
                company=company,
                location=location_str,
                description=description[:4000],  # Trim very long descriptions
                date_posted=date_posted,
            ))

        logger.info("  Found %d new results so far (this query).", len(new_jobs))
        time.sleep(delay_between_queries)

    logger.info("Scrape complete. %d new jobs found.", len(new_jobs))
    return new_jobs


def save_raw_jobs(jobs: list[RawJob]) -> list[str]:
    """Persist raw jobs to DB and return list of new job IDs."""
    ids = []
    for job in jobs:
        job_id = db.insert_job(
            source=job.source,
            url=job.url,
            title=job.title,
            company=job.company,
            location=job.location,
            description=job.description,
            date_posted=job.date_posted,
        )
        ids.append(job_id)
    logger.info("Saved %d new jobs to database.", len(ids))
    return ids
