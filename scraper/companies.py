"""
Target company career page monitor.
Scrapes Greenhouse API (free, no auth) for companies that use it,
and falls back to simple HTML scraping for others.
Also queries academictransfer.com for Dutch academic postdoc positions.
"""

import logging
import re
import requests
import time
from dataclasses import dataclass
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from . import db
from .scraper import _should_exclude

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
        "type": "ashby",
        "url": "https://jobs.ashbyhq.com/innatera",
        "linkedin_slug": "innatera",
    },
    "imec": {
        "type": "imec",
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
    # ── Belgium additions ────────────────────────────────────────────────────
    "Melexis": {
        "type": "html",
        "url": "https://www.melexis.com/en/about/careers/vacancies",
        "linkedin_slug": "melexis",
    },
    "NERF": {
        "type": "html",
        "url": "https://nerf.be/vacancies",
        "linkedin_slug": "nerf-be",
    },
    "VIB": {
        "type": "html",
        "url": "https://jobs.vib.be/en/jobs",
        "linkedin_slug": "vib-life-sciences",
    },
    "Flanders Make": {
        "type": "html",
        "url": "https://www.flandersmake.be/en/about-us/jobs",
        "linkedin_slug": "flanders-make",
    },
    # ── Belgium startup portfolios (Getro boards) ────────────────────────────
    "imec.istart": {
        "type": "getro",
        "board_url": "https://jobs.imecistart.com",
        "linkedin_slug": "imec-istart",
    },
    "Leuven.Inc": {
        "type": "getro",
        "board_url": "https://jobs.leuven.inc",
        "linkedin_slug": "leuven-inc",
    },
    # ── Netherlands additions ────────────────────────────────────────────────
    "HighTechXL": {
        "type": "getro",
        "board_url": "https://jobs.hightechxl.com",
        "linkedin_slug": "hightechxl",
    },
    "Yes!Delft": {
        "type": "html",
        "url": "https://yesdelft.com/jobs/",
        "linkedin_slug": "yes-delft",
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
# Ashby scraper (e.g., Innatera) — only real openings from the Ashby board
# ---------------------------------------------------------------------------
def _scrape_ashby(company: str, board_url: str) -> list[CompanyJob]:
    try:
        resp = requests.get(board_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Ashby fetch failed for %s: %s", company, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    seen_urls: set[str] = set()

    # Real openings live at jobs.ashbyhq.com/{org}/{uuid}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("https://jobs.ashbyhq.com/"):
            continue
        parts = href.rstrip("/").split("/")
        if len(parts) < 5:
            continue
        slug = parts[-1]
        # Keep only job detail URLs (uuid-like)
        if not re.match(r"^[0-9a-fA-F-]{30,}$", slug):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        title = a.get_text(" ", strip=True)
        if not title or len(title) < 4:
            continue
        if "learn more" in title.lower() or "privacy" in title.lower():
            continue

        # Fetch detail page to get a real description payload
        try:
            detail = requests.get(href, headers=HEADERS, timeout=TIMEOUT)
            detail.raise_for_status()
            dsoup = BeautifulSoup(detail.text, "html.parser")
            h1 = dsoup.find("h1")
            if h1 and len(h1.get_text(strip=True)) >= len(title):
                title = h1.get_text(strip=True)

            description = dsoup.get_text(separator=" ", strip=True)
            description = re.sub(r"\s+", " ", description)[:4000]

            location = ""
            for marker in ["Location", "Employment Type", "Location Type"]:
                marker_el = dsoup.find(string=re.compile(fr"^{marker}$", re.I))
                if marker_el:
                    sib = marker_el.find_parent().find_next_sibling() if marker_el.find_parent() else None
                    if sib:
                        location = (location + " " + sib.get_text(" ", strip=True)).strip()
        except Exception:
            description = f"[Visit {href} for full description]"
            location = ""

        # Skip non-job pages / noise
        if len(description) < 120:
            continue

        jobs.append(CompanyJob(
            url=href,
            title=title,
            company=company,
            location=location,
            description=description,
            source="ashby",
        ))

    return jobs


# ---------------------------------------------------------------------------
# imec dedicated scraper — only real job listings with full descriptions
# ---------------------------------------------------------------------------
_IMEC_JOB_PATH = "/en/work-at-imec/job-opportunities/"


def _scrape_imec(url: str) -> list[CompanyJob]:
    """Scrape imec job listings page, then fetch each job detail page for a real description."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("imec listing fetch failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    job_links: list[tuple[str, str]] = []  # (url, title)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # Only keep links to individual job pages (not the listing page itself)
        if not href.startswith(_IMEC_JOB_PATH):
            continue
        slug = href[len(_IMEC_JOB_PATH):].rstrip("/")
        if not slug:  # skip the listing page link itself
            continue
        if not text or len(text) < 5:
            continue
        full_url = f"https://www.imec-int.com{href}"
        if any(u == full_url for u, _ in job_links):
            continue
        job_links.append((full_url, text))

    logger.info("  imec: %d job links found on listing page, fetching details…", len(job_links))
    jobs = []
    for job_url, title in job_links:
        try:
            detail = requests.get(job_url, headers=HEADERS, timeout=TIMEOUT)
            detail.raise_for_status()
            dsoup = BeautifulSoup(detail.text, "html.parser")
            # Extract main content sections
            parts = []
            for section_title in ["What you will do", "Who you are", "What we do for you"]:
                header = dsoup.find(lambda tag: tag.name in ("h2", "h3") and section_title.lower() in tag.get_text(strip=True).lower())
                if header:
                    # Collect sibling text until next header
                    for sib in header.find_next_siblings():
                        if sib.name in ("h2", "h3"):
                            break
                        t = sib.get_text(separator=" ", strip=True)
                        if t:
                            parts.append(t)
            # Also grab intro paragraph before "What you will do"
            intro_el = dsoup.find("div", class_=lambda c: c and "field--body" in c)
            if intro_el:
                parts.insert(0, intro_el.get_text(separator=" ", strip=True)[:500])
            description = "\n\n".join(parts)[:4000] if parts else f"[Visit {job_url} for full description]"

            page_text = dsoup.get_text(separator=" ", strip=True).lower()
            has_apply = "apply" in page_text
            has_role_sections = ("what you will do" in page_text) or ("who you are" in page_text)
            if not (has_apply and has_role_sections):
                continue

            # Extract location from the detail page
            location = ""
            loc_match = dsoup.find(string=re.compile(r"(Leuven|Eindhoven|Gent|Antwerp|Holst|Netherlands|Belgium|Germany|Japan|Spain)", re.I))
            if loc_match:
                location = loc_match.strip()[:80]

        except Exception as exc:
            logger.debug("  imec detail fetch failed for %s: %s", job_url, exc)
            description = f"[Visit {job_url} for full description]"
            location = ""
        time.sleep(0.5)  # Be polite

        jobs.append(CompanyJob(
            url=job_url,
            title=title,
            company="imec",
            location=location,
            description=description,
            source="imec_career",
        ))

    return jobs


# ---------------------------------------------------------------------------
# Getro job board scraper (used by imec.istart, Leuven.Inc, HighTechXL, etc.)
# ---------------------------------------------------------------------------
def _scrape_getro(company: str, board_url: str) -> list[CompanyJob]:
    """Scrape a Getro-powered job board.

    Getro boards load jobs via a JSON API. We try the known endpoint first;
    if that fails we fall back to scraping the board HTML page.
    """
    board_url = board_url.rstrip("/")

    # Strategy 1: Getro API (works for many boards)
    api_candidates = [
        f"{board_url}/api/v1/jobs",
        f"{board_url}/api/v2/jobs",
    ]
    for api_url in api_candidates:
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                raw_jobs = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
                if raw_jobs:
                    jobs = []
                    for item in raw_jobs[:100]:
                        title = item.get("title") or item.get("name") or ""
                        org = item.get("organization", {}) or {}
                        co = org.get("name") or item.get("company") or company
                        loc_parts = [
                            item.get("city") or "",
                            item.get("country") or "",
                        ]
                        location = ", ".join(p for p in loc_parts if p) or item.get("location") or ""
                        job_url = item.get("url") or item.get("job_url") or item.get("apply_url") or ""
                        description = item.get("description") or item.get("body") or ""
                        if description:
                            description = BeautifulSoup(description, "html.parser").get_text(separator=" ")[:4000]
                        if not title or not job_url:
                            continue
                        jobs.append(CompanyJob(
                            url=job_url,
                            title=title,
                            company=co,
                            location=location,
                            description=description or f"[Visit {job_url} for full description]",
                            source="getro",
                        ))
                    if jobs:
                        logger.info("  Getro API: %d jobs from %s", len(jobs), api_url)
                        return jobs
        except Exception:
            pass

    # Strategy 2: Scrape the board HTML for job links
    jobs_page = f"{board_url}/jobs"
    try:
        resp = requests.get(jobs_page, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Getro HTML fetch failed for %s (%s): %s", company, jobs_page, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if not href or not text or len(text) < 5 or len(text) > 150:
            continue
        # Getro job links typically contain /jobs/ in the path
        if "/jobs/" not in href and "job" not in href:
            continue
        if href.startswith("/"):
            parsed = urlparse(board_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        elif not href.startswith("http"):
            continue
        if href in seen or href == jobs_page:
            continue
        seen.add(href)
        if any(kw in text.lower() for kw in ["home", "about", "contact", "privacy", "login", "sign up"]):
            continue
        jobs.append(CompanyJob(
            url=href,
            title=text,
            company=company,
            location="",
            description=f"[Visit {href} for full description]",
            source="getro",
        ))

    logger.info("  Getro HTML: %d job links from %s", len(jobs), jobs_page)
    return jobs[:50]


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
        elif config["type"] == "ashby":
            jobs = _scrape_ashby(company, config["url"])
        elif config["type"] == "imec":
            jobs = _scrape_imec(config["url"])
        elif config["type"] == "html":
            jobs = _scrape_html(company, config["url"])
        elif config["type"] == "getro":
            jobs = _scrape_getro(company, config["board_url"])
        else:
            jobs = []
        logger.info("  %s: %d listings found.", company, len(jobs))
        all_jobs.extend(jobs)
        time.sleep(2)

    all_jobs.extend(_scrape_academictransfer())

    # Apply pre-save filters (Dutch, PhD, internship, etc.)
    filtered = []
    for j in all_jobs:
        reason = _should_exclude(j.title, j.description)
        if reason:
            logger.info("  Filtered out '%s' at %s — %s", j.title, j.company, reason)
        else:
            filtered.append(j)

    # Filter to only new jobs
    new_jobs = [j for j in filtered if not db.is_seen(j.url)]
    logger.info("Company monitor: %d scraped, %d after filter, %d new.",
                len(all_jobs), len(filtered), len(new_jobs))
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
        db.touch_last_seen(job.url)
    logger.info("Saved %d new company jobs to database.", len(ids))
    return ids
