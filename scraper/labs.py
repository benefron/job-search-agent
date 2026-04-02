"""
Monthly lab mapping for potential outreach (even without open positions).
Uses OpenAlex public API to discover researchers/labs in target NL locations.

Strategy: search recent WORKS (papers) from NL institutions by topic keyword,
then collect unique authors with their institutions. This is more reliable than
searching author names (which is what /authors?search= does).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import db

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
LABS_JSON = DATA_DIR / "labs.json"
LABS_META = DATA_DIR / "labs_meta.json"

OPENALEX_BASE = "https://api.openalex.org"
TIMEOUT = 20

TARGET_CITIES = {
    "delft",
    "rotterdam",
    "the hague",
    "amsterdam",
    "leiden",
    "utrecht",
    "eindhoven",
    "haarlem",
    "nijmegen",
}

# Maps institution names (lowercase) to city label
LOCATION_HINTS = {
    "delft": ["delft university of technology", "tudelft", "tu delft"],
    "rotterdam": ["erasmus mc", "erasmus university rotterdam", "erasmus university"],
    "the hague": ["hague", "den haag", "leiden university medical center"],
    "amsterdam": ["university of amsterdam", "vu amsterdam", "amsterdam umc", "vrije universiteit"],
    "leiden": ["leiden university", "lumc", "universiteit leiden"],
    "utrecht": ["utrecht university", "umc utrecht", "universiteit utrecht"],
    "eindhoven": [
        "eindhoven university of technology",
        "tu/e",
        "tu eindhoven",
        "holst",
        "imec the netherlands",
        "imec nl",
        "philips research",
        "nxp",
    ],
    "haarlem": ["haarlem"],
    "nijmegen": ["radboud university", "radboudumc", "nijmegen"],
}

# Topics to search as paper keywords (results = NL authors publishing on these topics)
TOPICS = [
    "neuromorphic computing",
    "spiking neural network",
    "computational neuroscience",
    "systems neuroscience",
    "brain-computer interface",
    "brain-machine interface",
    "bio-inspired computing",
    "experimental neuroscience electrophysiology",
    "embedded AI edge computing",
    "robotics perception neural",
]

EXCLUDE_TERMS = [
    "molecular",
    "genetic",
    "genomics",
    "single-cell",
    "transcriptomics",
]


def _id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _is_due(force: bool = False, every_days: int = 30) -> bool:
    if force:
        return True
    if not LABS_META.exists():
        return True
    try:
        meta = json.loads(LABS_META.read_text())
        last = datetime.fromisoformat(meta.get("last_run_utc", ""))
    except Exception:
        return True
    delta = datetime.now(timezone.utc) - last
    return delta.days >= every_days


def _match_target_city(inst_name: str) -> str | None:
    """Map institution display name to a target city label, or None."""
    name_l = inst_name.lower()
    for city, hints in LOCATION_HINTS.items():
        if any(h in name_l for h in hints):
            return city
    return None


def _fetch_nl_authors_for_topic(topic: str) -> list[dict]:
    """Query recent NL-affiliated works for a topic and return deduped author dicts."""
    try:
        resp = requests.get(
            f"{OPENALEX_BASE}/works",
            params={
                "filter": "authorships.institutions.country_code:NL",
                "search": topic,
                "per-page": 50,
                "select": "id,title,authorships",
                "sort": "cited_by_count:desc",
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "job-search-agent/1.0 (mailto:research@example.com)"},
        )
        resp.raise_for_status()
        works = resp.json().get("results", [])
    except Exception as exc:
        logger.warning("Works query failed for topic '%s': %s", topic, exc)
        return []

    authors: dict[str, dict] = {}
    for work in works:
        for authorship in work.get("authorships", []):
            author_meta = authorship.get("author") or {}
            author_id = (author_meta.get("id") or "").strip()
            if not author_id or author_id in authors:
                continue

            # Find NL institution in this authorship
            nl_inst = None
            for inst in authorship.get("institutions", []):
                if inst.get("country_code") == "NL":
                    nl_inst = inst
                    break
            if nl_inst is None:
                continue

            inst_name = (nl_inst.get("display_name") or "").strip()
            city_label = _match_target_city(inst_name)
            if city_label is None:
                continue

            name = (author_meta.get("display_name") or "").strip()
            if not name:
                continue

            # Exclude molecular/genomics researchers
            label_check = f"{name} {inst_name}".lower()
            if any(t in label_check for t in EXCLUDE_TERMS):
                continue

            authors[author_id] = {
                "id": _id(author_id),
                "name": name,
                "lab": inst_name,
                "location": city_label.title(),
                "topic": topic,
                "url": author_id,
                "source": "openalex",
            }

    return list(authors.values())


def refresh_labs_if_due(force: bool = False) -> None:
    """Refresh labs mapping monthly (or when forced)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _is_due(force=force, every_days=30):
        logger.info("Lab mapping not due yet — keeping existing labs.json")
        return

    logger.info("Refreshing potential labs/researchers map via OpenAlex works…")
    found: dict[str, dict] = {}  # keyed by OpenAlex author URL

    for topic in TOPICS:
        logger.info("  Querying NL works for topic: %s", topic)
        authors = _fetch_nl_authors_for_topic(topic)
        for a in authors:
            url = a["url"]
            if db.is_hidden_entity(url, "lab"):
                continue
            if url not in found:
                found[url] = a
            # Keep the entry but record all topics (first match wins for display)
        time.sleep(0.5)

    labs = sorted(
        found.values(),
        key=lambda x: (x.get("location", ""), x.get("name", "")),
    )

    payload = {
        "generated": datetime.utcnow().isoformat(),
        "count": len(labs),
        "labs": labs,
    }
    LABS_JSON.write_text(json.dumps(payload, indent=2))
    LABS_META.write_text(
        json.dumps({"last_run_utc": datetime.now(timezone.utc).isoformat()}, indent=2)
    )
    logger.info("Labs map exported: %d entries", len(labs))

