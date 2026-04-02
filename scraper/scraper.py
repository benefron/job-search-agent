"""
Job scraper using python-jobspy — LinkedIn + Indeed + Google Jobs.
Anonymous session only (no credentials needed for public job listings).
"""

import time
import logging
import re
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
    ("postdoctoral researcher neuroscience", "Netherlands"),
    ("experimental neuroscience", "Netherlands"),
    # Embedded / robotics / BMI / BCI
    ("embedded systems engineer ai", "Netherlands"),
    ("robotics engineer perception", "Netherlands"),
    ("brain computer interface", "Netherlands"),
    ("brain machine interface", "Netherlands"),
]

SITES = ["linkedin", "indeed"]

# ---------------------------------------------------------------------------
# Pre-save filters — drop jobs we never want
# ---------------------------------------------------------------------------
_EXCLUDE_TITLE_REGEX = [
    # Exclude PhD/doctoral tracks, but keep postdoc/postdoctoral positions.
    r"\bph\.?d\b",
    r"\bdoctorate\b",
    r"\bdoctoral\s+(candidate|student|researcher|position)\b",
    r"\bpromotie\b",
    r"\bpromovend(us|i|a)?\b",
    # Student/internship tracks
    r"\bintern(ship)?\b",
    r"\bstage\b",
    r"\bstagiair\b",
    r"\bwerkstudent\b",
    r"\bworking\s+student\b",
]

# Common Dutch words that signal a Dutch-language posting
_DUTCH_SIGNALS = [
    "functieomschrijving", "verantwoordelijkheden", "vereisten",
    "wat ga je doen", "wat verwachten wij", "wat bieden wij",
    "jouw profiel", "wij zoeken", "jouw taken", "je bent",
    "wij bieden", "over ons", "als je", "ervaring met",
    "kennis van", "je hebt", "je beschikt", "ons team",
]

_DUTCH_FLUENCY = [
    "dutch fluency", "fluent in dutch", "fluent dutch",
    "native dutch", "dutch native", "moedertaal nederlands",
    "vloeiend nederlands", "dutch required", "dutch is required",
    "knowledge of dutch", "proficiency in dutch",
    "dutch language required", "nederlands vereist",
    "beheersing van het nederlands", "goede kennis van het nederlands",
]


def _should_exclude(title: str, description: str) -> str | None:
    """Return reason string if job should be excluded, else None."""
    t = title.lower()
    d = description.lower()

    # Keep postdocs explicitly.
    if "postdoc" in t or "postdoctoral" in t:
        pass
    else:
        # Title-based exclusion
        for pat in _EXCLUDE_TITLE_REGEX:
            if re.search(pat, t):
                return f"excluded by title pattern: {pat}"

    # Dutch-language description
    dutch_hits = sum(1 for s in _DUTCH_SIGNALS if s in d)
    if dutch_hits >= 3:
        return f"Dutch-language posting ({dutch_hits} signals)"

    # Dutch fluency requirement
    for pat in _DUTCH_FLUENCY:
        if pat in d:
            return f"requires Dutch fluency: {pat}"

    return None


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
                linkedin_fetch_description=True,
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

            # Pre-save filter
            reason = _should_exclude(title, description)
            if reason:
                logger.debug("  Filtered out '%s' — %s", title, reason)
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
