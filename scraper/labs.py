"""
Monthly lab mapping for potential outreach (even without open positions).
Uses OpenAlex public API to discover researchers/labs in target NL locations.
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

LOCATION_HINTS = {
    "delft": ["delft university of technology", "tudelft", "tu delft"],
    "rotterdam": ["erasmus mc", "erasmus university rotterdam"],
    "the hague": ["hague", "den haag", "leiden university medical center"],
    "amsterdam": ["university of amsterdam", "vu amsterdam", "amsterdam umc"],
    "leiden": ["leiden university", "lumc", "leiden"],
    "utrecht": ["utrecht university", "umc utrecht", "utrecht"],
    "eindhoven": ["eindhoven university of technology", "tu/e", "holst", "imec the netherlands"],
    "haarlem": ["haarlem"],
    "nijmegen": ["radboud university", "radboudumc", "nijmegen"],
}

TOPICS = [
    "neuromorphic",
    "computational neuroscience",
    "systems neuroscience",
    "brain computer interface",
    "brain machine interface",
    "bio inspired",
    "biomimetic",
    "experimental neuroscience",
    "robotics",
    "embedded ai",
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


def _fetch_institution_city(inst_id: str, cache: dict[str, str]) -> str:
    if inst_id in cache:
        return cache[inst_id]
    try:
        r = requests.get(f"{OPENALEX_BASE}/institutions/{inst_id.split('/')[-1]}", timeout=TIMEOUT)
        r.raise_for_status()
        obj = r.json()
        city = ((obj.get("geo") or {}).get("city") or "").strip().lower()
        cache[inst_id] = city
        return city
    except Exception:
        cache[inst_id] = ""
        return ""


def _match_target_city(inst_name: str, city: str) -> str | None:
    inst_name_l = inst_name.lower()
    if city in TARGET_CITIES:
        return city
    for target, hints in LOCATION_HINTS.items():
        if any(h in inst_name_l for h in hints):
            return target
    return None


def _author_to_lab(author: dict, topic: str, city_label: str) -> dict | None:
    name = (author.get("display_name") or "").strip()
    if not name:
        return None
    institution = ""
    institution_url = ""
    lki = author.get("last_known_institutions") or []
    if lki:
        inst = lki[0]
        institution = (inst.get("display_name") or "").strip()
        institution_url = (inst.get("id") or "").strip()

    if not institution:
        return None

    # Build a stable URL for researcher profile when possible.
    url = (author.get("id") or "").strip()
    if not url:
        return None

    label = f"{name} — {institution}".lower()
    if any(t in label for t in EXCLUDE_TERMS):
        return None

    return {
        "id": _id(url),
        "name": name,
        "lab": institution,
        "location": city_label.title(),
        "topic": topic,
        "url": url,
        "institution_url": institution_url,
        "works_count": author.get("works_count", 0),
        "source": "openalex",
    }


def refresh_labs_if_due(force: bool = False) -> None:
    """Refresh labs mapping monthly (or when forced)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _is_due(force=force, every_days=30):
        logger.info("Lab mapping not due yet — keeping existing labs.json")
        return

    logger.info("Refreshing potential labs/researchers map…")
    institution_city_cache: dict[str, str] = {}
    found: dict[str, dict] = {}

    for topic in TOPICS:
        for city in sorted(TARGET_CITIES):
            q = f"{topic} {city} netherlands"
            try:
                resp = requests.get(
                    f"{OPENALEX_BASE}/authors",
                    params={"search": q, "per-page": 20},
                    timeout=TIMEOUT,
                )
                resp.raise_for_status()
                results = (resp.json() or {}).get("results", [])
            except Exception as exc:
                logger.warning("Lab query failed for '%s': %s", q, exc)
                time.sleep(1)
                continue

            for author in results:
                lki = author.get("last_known_institutions") or []
                if not lki:
                    continue
                inst = lki[0]
                inst_name = (inst.get("display_name") or "")
                inst_id = (inst.get("id") or "")
                inst_city = _fetch_institution_city(inst_id, institution_city_cache) if inst_id else ""
                city_label = _match_target_city(inst_name, inst_city)
                if not city_label:
                    continue
                lab_item = _author_to_lab(author, topic, city_label)
                if not lab_item:
                    continue
                if db.is_hidden_entity(lab_item["url"], "lab"):
                    continue
                # Keep best signal per author URL
                prev = found.get(lab_item["url"])
                if prev is None or lab_item.get("works_count", 0) > prev.get("works_count", 0):
                    found[lab_item["url"]] = lab_item
            time.sleep(0.6)

    labs = sorted(
        found.values(),
        key=lambda x: (x.get("location", ""), -int(x.get("works_count", 0)), x.get("name", "")),
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
