"""
Scrape relevant NL university department pages to find research groups
that may not appear in OpenAlex keyword searches.

Searches known department URLs + extracting group/lab names, PI names,
and research themes. Results are appended to data/labs_dept.json.

Usage:
    python scripts/labs_dept_search.py [--institutions all|tudelft|uva|...] [--dry-run]

Then merge with labs.json via labs_enrich.py or manually.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_JSON = DATA_DIR / "labs_dept.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-search-agent/1.0; +mailto:research@example.com)"
}
TIMEOUT = 15

# ─────────────────────────────────────────────────────────────────────────────
# Department pages to scrape. Each entry:
#   name      : short label
#   institution: full institution name
#   location  : city
#   url       : department/group listing page
#   strategy  : 'links' (follow each group link) | 'page' (parse the page directly)
#   keywords  : must match at least one in page text (keeps signal-to-noise high)
# ─────────────────────────────────────────────────────────────────────────────
DEPARTMENTS = [
    # TU Delft
    {
        "name": "TU Delft EEMCS",
        "institution": "Delft University of Technology",
        "location": "Delft",
        "url": "https://www.tudelft.nl/ewi/over-de-faculteit/afdelingen",
        "strategy": "page",
        "keywords": ["neural", "neuro", "spike", "embedded", "edge", "sensor", "signal processing", "hardware"],
    },
    {
        "name": "TU Delft ME / BioMechanical Engineering",
        "institution": "Delft University of Technology",
        "location": "Delft",
        "url": "https://www.tudelft.nl/3me/over/afdelingen/biomechanical-engineering",
        "strategy": "page",
        "keywords": ["neural", "neuro", "brain", "motor", "sensory", "prosthetics", "neuroprosthetics"],
    },
    # TU/e
    {
        "name": "TU/e Electrical Engineering",
        "institution": "Eindhoven University of Technology",
        "location": "Eindhoven",
        "url": "https://www.tue.nl/en/research/research-groups",
        "strategy": "page",
        "keywords": ["neural", "neuro", "neuromorphic", "spike", "embedded", "brain", "edge AI", "signal"],
    },
    {
        "name": "TU/e Biomedical Engineering",
        "institution": "Eindhoven University of Technology",
        "location": "Eindhoven",
        "url": "https://www.tue.nl/en/education/graduate-school/biomedical-engineering",
        "strategy": "page",
        "keywords": ["neural", "neuro", "brain", "sensor", "interface", "implant"],
    },
    # UvA
    {
        "name": "UvA Informatics Institute",
        "institution": "University of Amsterdam",
        "location": "Amsterdam",
        "url": "https://ivi.fnwi.uva.nl/ivi/research/",
        "strategy": "links",
        "keywords": ["neural", "neuro", "brain", "spike", "computational", "learning", "vision", "embedded"],
    },
    {
        "name": "UvA Swammerdam/CNS",
        "institution": "University of Amsterdam",
        "location": "Amsterdam",
        "url": "https://sils.uva.nl/research/research-groups.html",
        "strategy": "page",
        "keywords": ["neural", "neuro", "computational", "systems", "electrophysiology", "brain"],
    },
    # VU Amsterdam
    {
        "name": "VU Amsterdam Computational Cognitive Neuroscience",
        "institution": "Vrije Universiteit Amsterdam",
        "location": "Amsterdam",
        "url": "https://ccn.sites.vu.nl/",
        "strategy": "page",
        "keywords": ["neural", "neuro", "spike", "computational", "cognitive", "brain", "model"],
    },
    # Radboud / Donders
    {
        "name": "Donders Institute Research Groups",
        "institution": "Radboud University",
        "location": "Nijmegen",
        "url": "https://www.ru.nl/donders/research/theme-1-neural-computation-neurotechnology/",
        "strategy": "page",
        "keywords": ["neural", "computation", "neuro", "spike", "electrophysiology", "brain", "sensory"],
    },
    {
        "name": "Donders Neurotechnology",
        "institution": "Radboud University",
        "location": "Nijmegen",
        "url": "https://www.ru.nl/donders/research/theme-2-perception-action-control/",
        "strategy": "page",
        "keywords": ["perception", "sensory", "neural", "brain", "motor", "control", "electrophysiology"],
    },
    # Leiden
    {
        "name": "Leiden Institute of Advanced Computer Science",
        "institution": "Leiden University",
        "location": "Leiden",
        "url": "https://www.universiteitleiden.nl/en/science/computer-science/research",
        "strategy": "page",
        "keywords": ["neural", "neuro", "AI", "learning", "brain", "computational", "pattern"],
    },
    # Utrecht
    {
        "name": "Utrecht Neuroscience",
        "institution": "Utrecht University",
        "location": "Utrecht",
        "url": "https://www.uu.nl/en/research/helmholtz-institute/research",
        "strategy": "page",
        "keywords": ["neural", "neuro", "computational", "spike", "brain", "sensory", "electrophysiology"],
    },
    # SRON / Holst / imec
    {
        "name": "imec NL Research",
        "institution": "imec the Netherlands",
        "location": "Eindhoven",
        "url": "https://www.imec-int.com/en/imec-netherlands",
        "strategy": "page",
        "keywords": ["neural", "neuro", "chip", "sensor", "edge", "AI", "brain", "spike", "interface"],
    },
    {
        "name": "Holst Centre",
        "institution": "Holst Centre",
        "location": "Eindhoven",
        "url": "https://www.holstcentre.com/research-and-technology",
        "strategy": "page",
        "keywords": ["neural", "body sensor", "wearable", "EEG", "EcoG", "biopotential", "electrophysiology"],
    },
]

RELEVANCE_KEYWORDS = [
    "neural", "neuro", "neuromorphic", "spike", "spiking",
    "brain-computer", "brain-machine", "electrophysiology",
    "computational neuroscience", "systems neuroscience",
    "edge AI", "embedded AI", "sensor fusion", "sensory encoding",
    "in-vivo", "in vivo", "BCI", "BMI",
]


def is_relevant(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def fetch_page(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        print(f"  [WARN] Failed to fetch {url}: {exc}")
        return None


def extract_text_blocks(soup: BeautifulSoup) -> list[str]:
    """Return meaningful text blocks (headings + paragraphs)."""
    blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "a"]):
        txt = tag.get_text(" ", strip=True)
        if len(txt) > 20:
            blocks.append(txt)
    return blocks


def scrape_dept_page(dept: dict, dry_run: bool = False) -> list[dict]:
    """Scrape one department entry and return a list of lab candidates."""
    print(f"\n→ {dept['name']} ({dept['url']})")
    if dry_run:
        print("  [dry-run] skipping fetch")
        return []

    soup = fetch_page(dept["url"])
    if soup is None:
        return []

    results = []
    relevant_blocks = []

    if dept["strategy"] == "links":
        # Follow all in-domain links and check each sub-page
        base_netloc = urlparse(dept["url"]).netloc
        links_seen = set()
        for a_tag in soup.find_all("a", href=True):
            href = urljoin(dept["url"], a_tag["href"])
            if urlparse(href).netloc != base_netloc:
                continue
            if href in links_seen:
                continue
            links_seen.add(href)
            link_text = a_tag.get_text(" ", strip=True)
            if not is_relevant(link_text, dept["keywords"]):
                continue
            sub_soup = fetch_page(href)
            if sub_soup is None:
                continue
            blocks = extract_text_blocks(sub_soup)
            page_text = " ".join(blocks)
            if is_relevant(page_text, dept["keywords"]):
                # Try to find a PI / group name from the page
                title_tag = sub_soup.find("h1") or sub_soup.find("h2")
                group_name = title_tag.get_text(" ", strip=True) if title_tag else link_text
                relevant_blocks.append({
                    "group_name": group_name,
                    "url": href,
                    "snippet": page_text[:300],
                })
            time.sleep(0.5)
    else:
        # Parse the listing page itself
        blocks = extract_text_blocks(soup)
        page_text = " ".join(blocks)
        if is_relevant(page_text, dept["keywords"]):
            # Extract headings as potential group names
            for tag in soup.find_all(["h2", "h3", "h4"]):
                txt = tag.get_text(" ", strip=True)
                if len(txt) < 5 or len(txt) > 120:
                    continue
                if is_relevant(txt, dept["keywords"]) or is_relevant(
                    tag.find_next("p", limit=1).get_text() if tag.find_next("p") else "", dept["keywords"]
                ):
                    href_tag = tag.find("a") or tag.find_next("a")
                    href = urljoin(dept["url"], href_tag["href"]) if href_tag and href_tag.get("href") else dept["url"]
                    relevant_blocks.append({
                        "group_name": txt,
                        "url": href,
                        "snippet": (tag.find_next("p").get_text()[:250] if tag.find_next("p") else ""),
                    })

    for block in relevant_blocks:
        results.append({
            "name": block["group_name"],
            "lab": dept["institution"],
            "location": dept["location"],
            "url": block["url"],
            "source_dept": dept["name"],
            "snippet": block["snippet"],
            "source": "dept_scrape",
        })
        print(f"  ✓ Found: {block['group_name'][:70]}")

    if not results:
        print("  (no relevant groups found on this page)")
    time.sleep(1)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape NL department pages for relevant research groups")
    parser.add_argument("--institutions", default="all",
        help="Comma-separated institution names to scrape, or 'all'")
    parser.add_argument("--dry-run", action="store_true", help="List departments but don't fetch")
    args = parser.parse_args()

    selected = DEPARTMENTS
    if args.institutions != "all":
        names = [n.strip().lower() for n in args.institutions.split(",")]
        selected = [d for d in DEPARTMENTS if any(n in d["name"].lower() or n in d["institution"].lower() for n in names)]

    print(f"Scraping {len(selected)} department pages…")
    all_results: list[dict] = []
    for dept in selected:
        results = scrape_dept_page(dept, dry_run=args.dry_run)
        all_results.extend(results)

    # Load existing dept results and merge (dedupe by url)
    existing: list[dict] = []
    if OUTPUT_JSON.exists():
        existing = json.loads(OUTPUT_JSON.read_text())
    existing_urls = {r["url"] for r in existing}
    new_entries = [r for r in all_results if r["url"] not in existing_urls]
    merged = existing + new_entries

    OUTPUT_JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"\nDone. {len(new_entries)} new entries added (total {len(merged)}) → {OUTPUT_JSON}")
    print("Review results and run labs_curate.py or merge manually into labs.json")


if __name__ == "__main__":
    main()
