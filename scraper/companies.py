"""
Target company career page monitor.
Scrapes Greenhouse API (free, no auth) for companies that use it,
and falls back to simple HTML scraping for others.
Also queries academictransfer.com for Dutch academic postdoc positions.
"""

import logging
import requests
import time
from dataclasses import dataclass
from bs4 import BeautifulSoup

from . import db

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15


@dataclass
class CompanyJob:
    url: str
    title: str
    company: str
    location: str
    description: str
    source: str = "company_career"
    date_posted: str | None = None


# ---------------------------------------------------------------------------
# Company registry
# Format: {display_name: {type: "greenhouse"|"html"|"academictransfer", config: {...}}}
# ---------------------------------------------------------------------------
COMPANIES = {
    "Innatera": {
        "type": "html",
        "url": "https://www.innatera.com/careers",
        "linkedin_slug": "innatera",
    },
    "imec": {
        "type": "html",
        "url": "https://www.imec-int.com/en/work-at-imec/job-opportunities",
        "linkedin_slug": "imec",
    },
    "Axelera AI": {
        "type": "greenhouse",
        "board_token": "axeleraai",
        "linkedin_slug": "axelera-ai",
    },
    "Prophesee": {
        "type": "greenhouse",
        "board_token": "prophesee",
        "linkedin_slug": "prophesee",
    },
    "Noldus": {
        "type": "html",
        "url": "https://www.noldus.com/about/jobs",
        "linkedin_slug": "noldus-information-technology",
    },
    "Demcon": {
        "type": "html",
        "url": "https://demcon.com/en/vacancies/",
        "linkedin_slug": "demcon",
    },
    "TNO": {
        "type": "html",
        "url": "https://www.tno.nl/en/career/vacancies/",
        "linkedin_slug": "tno",
    },
}

# Academictransfer — NL academic job board (structural feed)
ACADEMICTRANSFER_BASE = "https://www.academictransfer.com/api/jobs/"
ACADEMICTRANSFER_QUERIES = [
    "neuroscience",
    "neuromorphic",
    "computational neuroscience",
    "neuroengineering",
    "brain-inspired",
]


# ---------------------------------------------------------------------------
# Greenhouse API scraper
# ---------------------------------------------------------------------------
def _scrape_greenhouse(company: str, board_token: str) -> list[CompanyJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Greenhouse fetch failed for %s: %s", company, exc)
        return []

    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "").strip()
        location_list = job.get("offices", [])
        location = ", ".join(o.get("name", "") for o in location_list) if location_list else ""
        job_url = job.get("absolute_url", "")
        description = BeautifulSoup(job.get("content", ""), "html.parser").get_text(separator=" ")[:4000]
        if not title or not job_url:
            continue
        jobs.append(CompanyJob(
            url=job_url,
            title=title,
            company=company,
            location=location,
            description=description,
            source="greenhouse",
        ))
    return jobs


# ---------------------------------------------------------------------------
# Generic HTML scraper (best-effort — looks for job title links)
# ---------------------------------------------------------------------------
def _scrape_html(company: str, url: str) -> list[CompanyJob]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("HTML fetch failed for %s: %s", company, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    # Heuristic: find anchor tags whose text looks like job titles
    # (contains uppercase words, not navigation items)
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if not text or len(text) < 8 or len(text) > 120:
            continue
        # Skip nav/footer-like links
        if any(kw in text.lower() for kw in ["home", "about", "contact", "privacy", "cookie", "login"]):
            continue
        # Keep links that look like job postings (contain letters, reasonable length)
        if not any(c.isalpha() for c in text):
            continue
        # Resolve relative URLs
        if href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        elif not href.startswith("http"):
            continue

        # Avoid duplicates within this company
        if any(j.url == href for j in jobs):
            continue

        jobs.append(CompanyJob(
            url=href,
            title=text,
            company=company,
            location="",           # Not extractable from listing page generically
            description=f"[Visit {href} for full description]",
            source="company_html",
        ))

    # Limit to avoid noise from non-career-page anchors
    return jobs[:30]


# ---------------------------------------------------------------------------
# Academictransfer
# ---------------------------------------------------------------------------
def _scrape_academictransfer() -> list[CompanyJob]:
    """Query AcademicTransfer for relevant NL academic positions."""
    jobs = []
    seen_urls: set[str] = set()

    for query in ACADEMICTRANSFER_QUERIES:
        try:
            resp = requests.get(
                "https://www.academictransfer.com/en/jobs/",
                params={"q": query, "country": "NL"},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("AcademicTransfer failed for '%s': %s", query, exc)
            time.sleep(3)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("article.job-card, div.job-card, li.vacancy"):
            a = card.find("a", href=True)
            title_el = card.find(["h2", "h3", "h4"])
            if not a or not title_el:
                continue
            href = a["href"]
            if href.startswith("/"):
                href = "https://www.academictransfer.com" + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            institution_el = card.find(class_=lambda c: c and ("institution" in c or "employer" in c))
            company = institution_el.get_text(strip=True) if institution_el else "Academic Institution (NL)"
            jobs.append(CompanyJob(
                url=href,
                title=title_el.get_text(strip=True),
                company=company,
                location="Netherlands",
                description=f"[Academic position — visit {href} for full description]",
                source="academictransfer",
            ))

        time.sleep(3)

    logger.info("AcademicTransfer: found %d positions.", len(jobs))
    return jobs


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def scrape_companies() -> list[CompanyJob]:
    """Scrape all registered companies and AcademicTransfer. Return new jobs only."""
    all_jobs: list[CompanyJob] = []

    for company, config in COMPANIES.items():
        logger.info("Scraping company: %s", company)
        if config["type"] == "greenhouse":
            jobs = _scrape_greenhouse(company, config["board_token"])
        elif config["type"] == "html":
            jobs = _scrape_html(company, config["url"])
        else:
            jobs = []
        logger.info("  %s: %d listings found.", company, len(jobs))
        all_jobs.extend(jobs)
        time.sleep(2)

    all_jobs.extend(_scrape_academictransfer())

    # Filter to only new jobs
    new_jobs = [j for j in all_jobs if not db.is_seen(j.url)]
    logger.info("Company monitor: %d total, %d new.", len(all_jobs), len(new_jobs))
    return new_jobs


def save_company_jobs(jobs: list[CompanyJob]) -> list[str]:
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
    logger.info("Saved %d new company jobs to database.", len(ids))
    return ids
