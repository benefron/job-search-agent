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
    # Data science & applied ML — Ben's qualifications align well
    ("data scientist machine learning", "Netherlands"),
    ("applied machine learning scientist", "Netherlands"),
    ("computer vision scientist", "Netherlands"),
    ("ML engineer research", "Netherlands"),
    ("machine learning engineer", "Amsterdam Netherlands"),
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
    # Belgium — same keyword breadth as NL, broad location covers
    # Leuven, Brussels, Mechelen, Hasselt, Zaventem, Antwerp, Ghent, etc.
    ("neuromorphic engineer", "Belgium"),
    ("spiking neural network engineer", "Belgium"),
    ("brain-inspired computing", "Belgium"),
    ("neuromorphic AI", "Belgium"),
    ("neuroengineering", "Belgium"),
    ("neurotech scientist", "Belgium"),
    ("computational neuroscience", "Belgium"),
    ("edge AI scientist", "Belgium"),
    ("embedded AI engineer", "Belgium"),
    ("embedded sensing engineer", "Belgium"),
    ("R&D scientist sensing", "Belgium"),
    ("applied scientist signal processing", "Belgium"),
    ("research scientist neuromorphic", "Belgium"),
    ("data scientist machine learning", "Belgium"),
    ("applied machine learning scientist", "Belgium"),
    ("computer vision scientist", "Belgium"),
    ("ML engineer research", "Belgium"),
    ("machine learning engineer", "Leuven Belgium"),
    ("postdoctoral researcher computational neuroscience", "Belgium"),
    ("postdoc neuroengineering", "Belgium"),
    ("postdoctoral researcher neuroscience", "Belgium"),
    ("brain computer interface", "Belgium"),
    ("embedded systems engineer ai", "Belgium"),
    ("robotics engineer perception", "Belgium"),
]

SITES = ["linkedin", "indeed"]

# ---------------------------------------------------------------------------
# Location filter — hierarchical allow-list
# Only jobs whose location string matches a target country or city pass.
# Remote jobs are always allowed if the title/description signals remote.
# ---------------------------------------------------------------------------
LOCATION_FILTER: dict[str, list[str]] = {
    "Netherlands": [
        "amsterdam", "eindhoven", "delft", "utrecht", "rotterdam",
        "nijmegen", "leiden", "haarlem", "the hague", "den haag",
        "tilburg", "groningen", "maastricht", "breda", "arnhem",
        "netherlands", "nederland",
    ],
    "Belgium": [
        "leuven", "brussels", "brussel", "bruxelles", "mechelen",
        "hasselt", "zaventem", "belgium", "belgie", "belgique",
    ],
}

# Flat set of all allowed location tokens for fast lookup
_ALLOWED_LOCATIONS: set[str] = {
    token
    for tokens in LOCATION_FILTER.values()
    for token in tokens
}

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
    # Research Assistant — overqualified for PhD candidate
    r"\bresearch\s+assistant\b",
]

# Common Dutch words that signal a Dutch-language posting
_DUTCH_SIGNALS = [
    "functieomschrijving", "verantwoordelijkheden", "vereisten",
    "wat ga je doen", "wat verwachten wij", "wat bieden wij",
    "jouw profiel", "wij zoeken", "jouw taken", "je bent",
    "wij bieden", "over ons", "als je", "ervaring met",
    "kennis van", "je hebt", "je beschikt", "ons team",
    "vacature", "solliciteer", "arbeidsvoorwaarden", "werkgever",
    "je werkt", "je gaat", "wij zijn", "ben jij", "heb jij",
]

# Common French words that signal a French-language posting
_FRENCH_SIGNALS = [
    "description du poste", "responsabilités", "compétences requises",
    "nous recherchons", "profil recherché", "ce que nous offrons",
    "votre profil", "vos missions", "votre rôle", "rejoignez",
    "nous vous offrons", "notre équipe", "poste à pourvoir",
    "expérience en", "connaissance de", "maîtrise de",
]

_DUTCH_FLUENCY = [
    "dutch fluency", "fluent in dutch", "fluent dutch",
    "native dutch", "dutch native", "moedertaal nederlands",
    "vloeiend nederlands", "dutch required", "dutch is required",
    "knowledge of dutch", "proficiency in dutch",
    "dutch language required", "nederlands vereist",
    "beheersing van het nederlands", "goede kennis van het nederlands",
]


def _is_remote(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(kw in text for kw in ("remote", "work from home", "fully remote", "hybrid remote"))


def _location_allowed(location: str, title: str, description: str) -> bool:
    """Return True if job is in a target location or is remote."""
    if not location:
        return True  # unknown location — let scorer handle it
    if _is_remote(title, description):
        return True
    loc = location.lower()
    return any(token in loc for token in _ALLOWED_LOCATIONS)


def _should_exclude(title: str, description: str, location: str = "") -> str | None:
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
    if dutch_hits >= 2:
        return f"Dutch-language posting ({dutch_hits} signals)"

    # French-language description
    french_hits = sum(1 for s in _FRENCH_SIGNALS if s in d)
    if french_hits >= 2:
        return f"French-language posting ({french_hits} signals)"

    # Dutch fluency requirement
    for pat in _DUTCH_FLUENCY:
        if pat in d:
            return f"requires Dutch fluency: {pat}"

    # Location outside target area
    if not _location_allowed(location, title, description):
        return f"location outside target area: {location!r}"

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
            reason = _should_exclude(title, description, location_str)
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
    """Persist raw jobs to DB and return list of new job IDs.

    Deduplication strategy (same title + company across sources):
    - If a LinkedIn entry and a non-LinkedIn entry represent the same job,
      keep/prefer the LinkedIn URL.
    - Within the incoming batch: deduplicate by (normalised_title, company),
      preferring LinkedIn over other sources.
    - Against the DB: if a LinkedIn job arrives and an identical non-LinkedIn
      job already exists, replace the DB entry with the LinkedIn URL.
      Conversely, skip a non-LinkedIn job if a LinkedIn version is already in DB.
    """
    # ── Within-batch deduplication ──────────────────────────────────────────
    seen_key: dict[tuple[str, str], RawJob] = {}
    for job in jobs:
        key = (db._normalize_title(job.title), job.company.lower())
        existing = seen_key.get(key)
        if existing is None:
            seen_key[key] = job
        elif job.source == "linkedin" and existing.source != "linkedin":
            # Prefer LinkedIn
            seen_key[key] = job
        # else: keep the existing entry (LinkedIn already there, or first-seen wins)
    deduped = list(seen_key.values())

    ids = []
    for job in deduped:
        if job.source == "linkedin":
            # If an older non-LinkedIn duplicate exists in DB, replace it
            old = db.find_non_linkedin_job_by_title_company(job.title, job.company)
            if old:
                old_id, old_url = old
                # Only replace if not already hidden/tombstoned
                new_id = db.replace_with_linkedin(old_id, job.url)
                logger.info(
                    "  Replaced non-LinkedIn duplicate '%s' with LinkedIn URL.", job.title
                )
                ids.append(new_id)
                continue
        else:
            # Non-LinkedIn: skip if LinkedIn version already in DB
            li_id = db.find_linkedin_job_by_title_company(job.title, job.company)
            if li_id:
                logger.debug(
                    "  Skipping '%s' from %s — LinkedIn version already in DB.",
                    job.title, job.source,
                )
                # Tombstone the non-LinkedIn URL so it won't be re-checked
                db.hide_entity(job.url, "job", f"{job.title} at {job.company} [linkedin preferred]")
                continue

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
