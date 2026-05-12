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
    # Belgium
    "leuven",
    "ghent",
    "brussels",
    "mechelen",
    "hasselt",
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
    # Belgium
    "leuven": [
        "ku leuven",
        "katholieke universiteit leuven",
        "imec",
        "vib",
        "leuven",
    ],
    "ghent": ["ghent university", "universiteit gent", "ugent", "vib-ugent", "ghent"],
    "brussels": [
        "vrije universiteit brussel",
        "vub",
        "ulb",
        "université libre de bruxelles",
        "brussels",
    ],
    "mechelen": ["mechelen"],
    "hasselt": ["uhasselt", "hasselt university", "hasselt"],
}

# Topics to search as paper keywords (results = NL authors publishing on these topics)
TOPICS = [
    "neuromorphic computing",
    "spiking neural network",
    "computational neuroscience",
    "systems neuroscience",
    "brain-computer interface",
    "brain-machine interface",
    "event-driven neuromorphic sensor",
    "in vivo electrophysiology neural recording",
    "spike-based computing hardware",
    "neurorobotics sensory",
    "sensory encoding neural population",
    "embedded neural inference edge",
]

# Exclude researchers whose OpenAlex topics/concepts include these fields
EXCLUDE_TERMS = [
    "molecular",
    "genetic",
    "genomics",
    "single-cell",
    "transcriptomics",
    "oncology",
    "cancer",
    "cardiology",
    "vascular",
    "pulmonary",
    "epidemiology",
    "gastroenterology",
    "immunology",
    "hydrology",
    "atmospheric",
    "climate",
    "geoscience",
    "geophysics",
    "sociology",
    "psychology clinical",
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


def _batch_verify_nl_current(author_ids: list[str]) -> dict[str, dict]:
    """Batch-fetch author records; return those whose *current* institution is NL or BE.

    OpenAlex `last_known_institutions` reflects where the author is now,
    not where they did a past PhD. This filters out former NL/BE students abroad.
    Returned dict maps full OpenAlex author URL → enriched author record.
    """
    if not author_ids:
        return {}

    BATCH = 50  # OpenAlex OR-filter limit
    verified: dict[str, dict] = {}

    for i in range(0, len(author_ids), BATCH):
        chunk = author_ids[i : i + BATCH]
        short_ids = [aid.split("/")[-1] for aid in chunk]
        filter_str = "|".join(short_ids)
        try:
            resp = requests.get(
                f"{OPENALEX_BASE}/authors",
                params={
                    "filter": f"ids.openalex:{filter_str}",
                    "per-page": len(short_ids),
                    "select": "id,display_name,last_known_institutions,ids,works_count,topics",
                },
                timeout=TIMEOUT,
                headers={"User-Agent": "job-search-agent/1.0 (mailto:research@example.com)"},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:
            logger.warning("Author batch fetch failed: %s", exc)
            continue

        for a in results:
            institutions = a.get("last_known_institutions") or []
            if not institutions:
                continue
            if institutions[0].get("country_code") not in ("NL", "BE"):
                continue  # currently abroad

            # Field-based exclusion: check top topics/concepts for irrelevant fields
            topic_labels = " ".join(
                (t.get("display_name") or "").lower()
                for t in (a.get("topics") or [])[:10]
            )
            if any(term in topic_labels for term in EXCLUDE_TERMS):
                continue

            verified[a["id"]] = a
        time.sleep(0.5)  # be polite between batches

    return verified


def _fetch_nl_authors_for_topic(topic: str) -> list[dict]:
    """Two-step pipeline: find NL/BE paper authors, then verify current NL/BE affiliation."""
    # --- Phase 1: /works search (may include past affiliations on older papers) ---
    try:
        resp = requests.get(
            f"{OPENALEX_BASE}/works",
            params={
                "filter": "authorships.institutions.country_code:NL|BE",
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

    # Collect candidate authors (NL institution on the paper)
    candidates: dict[str, dict] = {}  # author_id → {inst_name, city_label, name}
    for work in works:
        for authorship in work.get("authorships", []):
            author_meta = authorship.get("author") or {}
            author_id = (author_meta.get("id") or "").strip()
            if not author_id or author_id in candidates:
                continue

            nl_inst = None
            for inst in authorship.get("institutions", []):
                if inst.get("country_code") in ("NL", "BE"):
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

            # Quick name-based exclusion (catches obvious mismatches)
            label_check = f"{name} {inst_name}".lower()
            if any(t in label_check for t in EXCLUDE_TERMS):
                continue

            candidates[author_id] = {
                "name": name,
                "inst_name": inst_name,
                "city_label": city_label,
            }

    if not candidates:
        return []

    # --- Phase 2: verify current NL affiliation via /authors batch fetch ---
    verified = _batch_verify_nl_current(list(candidates.keys()))

    # --- Phase 3: build enriched entries ---
    results: list[dict] = []
    for author_id, cand in candidates.items():
        if author_id not in verified:
            continue  # no longer in NL

        adat = verified[author_id]

        # Prefer current institution from /authors over paper's institution
        current_insts = adat.get("last_known_institutions") or []
        current_inst_name = (
            current_insts[0].get("display_name") or cand["inst_name"]
        ) if current_insts else cand["inst_name"]
        city_label = _match_target_city(current_inst_name) or cand["city_label"]

        orcid = (adat.get("ids") or {}).get("orcid") or ""
        orcid_url = orcid if orcid.startswith("http") else (
            f"https://orcid.org/{orcid}" if orcid else ""
        )
        name = adat.get("display_name") or cand["name"]
        google_url = (
            "https://www.google.com/search?q="
            + requests.utils.quote(f'{name} {current_inst_name} neuroscience research')
        )
        scholar_url = (
            "https://scholar.google.com/scholar?q="
            + requests.utils.quote(f'{name} {current_inst_name}')
        )

        results.append({
            "id": _id(author_id),
            "name": name,
            "lab": current_inst_name,
            "location": city_label.title(),
            "topic": topic,
            "url": author_id,
            "orcid_url": orcid_url,
            "google_url": google_url,
            "scholar_url": scholar_url,
            "works_count": adat.get("works_count") or 0,
            "source": "openalex",
        })

    return results


def refresh_labs_if_due(force: bool = False) -> None:
    """Refresh labs mapping monthly (or when forced)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _is_due(force=force, every_days=30):
        logger.info("Lab mapping not due yet — keeping existing labs.json")
        return

    logger.info("Refreshing potential labs/researchers map via OpenAlex works (NL + BE)…")
    found: dict[str, dict] = {}  # keyed by OpenAlex author URL

    for topic in TOPICS:
        logger.info("  Querying NL/BE works for topic: %s", topic)
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

