"""
Export scored jobs to JSON and CSV for the dashboard.
Also ingests feedback from data/feedback.json if present.
"""

import json
import csv
import logging
from pathlib import Path
from datetime import datetime

from . import db
from .connections import enrich_jobs_with_connections

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
JOBS_JSON = DATA_DIR / "jobs.json"
STATS_JSON = DATA_DIR / "stats.json"
FEEDBACK_JSON = DATA_DIR / "feedback.json"
JOBS_CSV = DATA_DIR / "jobs_export.csv"


def ingest_feedback() -> None:
    """Read feedback.json (exported from dashboard) and apply to DB."""
    if not FEEDBACK_JSON.exists():
        logger.info("No feedback.json found — skipping feedback ingestion.")
        return

    with open(FEEDBACK_JSON) as f:
        records = json.load(f)

    if not isinstance(records, list):
        logger.warning("feedback.json is not a list — skipping.")
        return

    db.apply_feedback(records)
    logger.info("Applied %d feedback records.", len(records))


def export_jobs(min_score: int = 35) -> None:
    """Export scored jobs to jobs.json and jobs_export.csv."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    jobs = db.get_jobs_for_export(min_score=min_score)
    jobs = enrich_jobs_with_connections(jobs)

    # Strip personal notes before writing to the public-committed JSON
    for job in jobs:
        job.pop("connection_notes", None)

    # Write JSON
    with open(JOBS_JSON, "w") as f:
        json.dump(
            {"generated": datetime.utcnow().isoformat(), "jobs": jobs},
            f,
            indent=2,
        )
    logger.info("Exported %d jobs to %s", len(jobs), JOBS_JSON)

    # Write CSV (flattened, human-readable)
    if jobs:
        csv_fields = [
            "score", "fit_category", "job_category", "title", "company", "location",
            "date_posted", "date_found", "source", "url",
            "rationale", "key_matches", "key_gaps", "status", "feedback",
        ]
        with open(JOBS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            for job in jobs:
                row = dict(job)
                row["key_matches"] = "; ".join(job.get("key_matches", []))
                row["key_gaps"] = "; ".join(job.get("key_gaps", []))
                writer.writerow(row)
        logger.info("Exported CSV to %s", JOBS_CSV)


def export_stats() -> None:
    """Write stats.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stats = db.get_stats()
    with open(STATS_JSON, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info("Stats: %s", stats)
