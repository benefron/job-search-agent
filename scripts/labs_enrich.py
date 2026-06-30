"""
Enrich labs.json entries with lab website URLs and Google Scholar profiles.

For each lab without a `website` field, this script:
  1. Queries the OpenAlex /authors endpoint for the researcher's current
     institution URL and any concept/topic affiliations.
  2. Optionally searches the institution's website for the researcher's page
     using a DuckDuckGo HTML search (no API key required).
  3. Writes updated labs.json and a human-readable report.

Usage:
    # Enrich all labs missing a website
    python scripts/labs_enrich.py

    # Enrich only labs at a specific institution
    python scripts/labs_enrich.py --institution "Radboud"

    # Dry run (show what would be searched, don't update)
    python scripts/labs_enrich.py --dry-run

    # Limit to N labs (useful for testing)
    python scripts/labs_enrich.py --limit 20

Output:
    data/labs.json  — updated in place with website/scholar_page fields
    data/labs_enrich_report.txt — human-readable summary
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data"
LABS_JSON = DATA_DIR / "labs.json"
REPORT_TXT = DATA_DIR / "labs_enrich_report.txt"

OPENALEX_BASE = "https://api.openalex.org"
TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-agent/1.0; +mailto:research@example.com)"
}

# Well-known institutional domain patterns → base URL for staff page searches
INSTITUTION_DOMAINS = {
    "delft university of technology": "tudelft.nl",
    "tu delft": "tudelft.nl",
    "eindhoven university of technology": "tue.nl",
    "tu/e": "tue.nl",
    "university of amsterdam": "uva.nl",
    "vrije universiteit": "vu.nl",
    "vu amsterdam": "vu.nl",
    "leiden university": "universiteitleiden.nl",
    "utrecht university": "uu.nl",
    "radboud university": "ru.nl",
    "radboudumc": "radboudumc.nl",
    "amsterdam umc": "amsterdamumc.nl",
    "amsterdam neuroscience": "amsterdam-neuroscience.nl",
    "imec the netherlands": "imec-int.com",
    "holst centre": "holstcentre.com",
}


def load_labs() -> tuple[dict, list[dict]]:
    """Return (raw_data_dict, list_of_labs)."""
    raw = json.loads(LABS_JSON.read_text())
    if isinstance(raw, dict):
        return raw, raw.get("labs", [])
    return {"labs": raw}, raw


def save_labs(raw: dict, labs: list[dict]) -> None:
    raw["labs"] = labs
    LABS_JSON.write_text(json.dumps(raw, indent=2, ensure_ascii=False))


def get_institution_domain(inst_name: str) -> str | None:
    inst_l = inst_name.lower()
    for key, domain in INSTITUTION_DOMAINS.items():
        if key in inst_l:
            return domain
    return None


def ddg_search(query: str, site: str | None = None) -> list[dict]:
    """DuckDuckGo HTML search (no JS, no API key). Returns list of {title, url, snippet}."""
    q = f"site:{site} {query}" if site else query
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:5]:
            a = r.select_one(".result__a")
            snippet_tag = r.select_one(".result__snippet")
            if not a:
                continue
            href = a.get("href", "")
            # DDG wraps URLs in redirects — extract the real URL
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                from urllib.parse import unquote
                href = unquote(m.group(1))
            results.append({
                "title": a.get_text(strip=True),
                "url": href,
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
            })
        return results
    except Exception as exc:
        print(f"    [WARN] DDG search failed: {exc}")
        return []


def openalex_enrich(author_openalex_id: str) -> dict:
    """Fetch additional fields from OpenAlex /authors for this researcher."""
    short_id = author_openalex_id.split("/")[-1]
    try:
        resp = requests.get(
            f"{OPENALEX_BASE}/authors/{short_id}",
            params={"select": "id,display_name,ids,last_known_institutions,x_concepts,works_api_url"},
            headers={"User-Agent": "job-search-agent/1.0 (mailto:research@example.com)"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"    [WARN] OpenAlex fetch failed for {short_id}: {exc}")
        return {}


def find_researcher_website(name: str, institution: str) -> str:
    """
    Try to find the researcher's institutional page.
    Returns URL string or empty string.
    """
    domain = get_institution_domain(institution)
    results = ddg_search(f'"{name}" research', site=domain)
    if not results:
        results = ddg_search(f'"{name}" {institution} lab research page')

    for r in results:
        url = r.get("url", "")
        # Prefer institutional pages over generic listing sites
        if domain and domain in url:
            return url
        if any(x in url for x in ["people", "staff", "lab", "research", "group"]):
            return url
    return results[0]["url"] if results else ""


def enrich_lab(lab: dict, dry_run: bool) -> dict:
    """Enrich a single lab entry with website/scholar fields. Returns updated lab."""
    name = lab.get("name", "")
    institution = lab.get("lab", "")
    author_id = lab.get("url", "")

    print(f"  → {name} @ {institution}")

    if dry_run:
        print("    [dry-run] skipping")
        return lab

    # 1. Fetch extra OpenAlex data (homepage_display_name, alternate identifiers)
    if author_id.startswith("https://openalex.org/"):
        oa_data = openalex_enrich(author_id)
        # Institutional homepage from OpenAlex
        try:
            inst_url = oa_data.get("last_known_institutions", [{}])[0].get("homepage_url") or ""
            if inst_url and not lab.get("inst_url"):
                lab["inst_url"] = inst_url
        except (IndexError, TypeError):
            pass
        time.sleep(0.3)

    # 2. Find researcher page via DuckDuckGo
    if not lab.get("website"):
        website = find_researcher_website(name, institution)
        if website:
            lab["website"] = website
            print(f"    website: {website[:80]}")
        time.sleep(1.5)  # be gentle with DDG

    # 3. Build scholar URL if missing
    if not lab.get("scholar_url"):
        lab["scholar_url"] = (
            f"https://scholar.google.com/scholar?q={quote_plus(name + ' ' + institution)}"
        )

    # 4. Build google URL if missing
    if not lab.get("google_url"):
        lab["google_url"] = (
            f"https://www.google.com/search?q={quote_plus(name + ' ' + institution + ' neuroscience research')}"
        )

    return lab


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich labs.json with website / scholar links")
    parser.add_argument("--institution", help="Filter by institution name substring")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Max labs to enrich (0 = all)")
    args = parser.parse_args()

    raw, labs = load_labs()

    # Select labs that need enrichment
    targets = [
        l for l in labs
        if not l.get("website")
    ]
    if args.institution:
        targets = [l for l in targets if args.institution.lower() in l.get("lab", "").lower()]
    if args.limit:
        targets = targets[:args.limit]

    print(f"Enriching {len(targets)} labs (out of {len(labs)} total)…\n")
    report_lines = []

    for i, lab in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}]")
        lab_id = lab["id"]
        # Find this lab in the full list and update in place
        idx = next((j for j, l in enumerate(labs) if l["id"] == lab_id), None)
        if idx is None:
            continue
        labs[idx] = enrich_lab(lab, dry_run=args.dry_run)

        website = labs[idx].get("website", "")
        report_lines.append(
            f"{lab.get('name','?')} | {lab.get('lab','?')} | {website or '(not found)'}"
        )

    if not args.dry_run:
        save_labs(raw, labs)
        print(f"\nUpdated {LABS_JSON}")

    REPORT_TXT.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report written to {REPORT_TXT}")


if __name__ == "__main__":
    main()
