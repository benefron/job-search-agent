"""
Pipeline entrypoint.

Usage (local):
    export GITHUB_TOKEN=ghp_...
    python -m scraper.main           # full pipeline (scrape + score + export)
    python -m scraper.main --score-only [--max N]  # score pending jobs only

Run from repo root. Creates data/ if needed.
"""

import argparse
import logging
import os
import sys

# Ensure data/ directory exists
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/run.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


def main() -> None:
    from scraper import db, scraper, companies, export
    from scorer import scorer

    # ── 1. Init database ──
    log.info("Initialising database…")
    db.init_db()

    # ── 2. Ingest any user feedback committed since last run ──
    log.info("Ingesting feedback…")
    export.ingest_feedback()

    # ── 2b. Prune known historical noise pages ──
    try:
        pruned = db.prune_known_noise_jobs()
        if pruned:
            log.info("Pruned %d historical noise rows (imec/Innatera generic pages)", pruned)
    except Exception:
        log.exception("Noise-prune step failed — continuing")

    # ── 3. Scrape job boards (LinkedIn + Indeed) ──
    log.info("Scraping job boards…")
    try:
        raw_jobs = scraper.scrape_all()
        saved = scraper.save_raw_jobs(raw_jobs)
        log.info("Job boards: %d new jobs saved", len(saved))
    except Exception:
        log.exception("Job-board scraping failed — continuing with company scrape")

    # ── 4. Scrape company career pages (Greenhouse + HTML + AcademicTransfer) ──
    log.info("Scraping company career pages…")
    try:
        company_jobs = companies.scrape_companies()
        c_saved = companies.save_company_jobs(company_jobs)
        log.info("Company pages: %d new jobs saved", len(c_saved))
    except Exception:
        log.exception("Company scraping failed — continuing with scoring")

    # ── 5. Score all pending jobs via GitHub Models API ──
    if not (os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        log.warning("MODELS_TOKEN not set — skipping scoring")
    else:
        log.info("Scoring pending jobs…")
        try:
            scored = scorer.score_all_pending()
            log.info("Scored %d jobs", scored)
        except Exception:
            log.exception("Scoring failed — continuing with export")

    # ── 6. Export JSON + CSV for dashboard ──
    log.info("Exporting data…")
    export.export_jobs()
    export.export_stats()

    stats = db.get_stats()
    log.info(
        "Done. Total: %d | Scored: %d | Strong+: %d",
        stats.get("total", 0),
        stats.get("scored", 0),
        stats.get("strong_plus", 0),
    )


def score_only(max_jobs: int = 50) -> None:
    """Score pending jobs without scraping. Exports updated data afterwards."""
    from scraper import db, export
    from scorer import scorer

    log.info("Initialising database…")
    db.init_db()

    log.info("Ingesting feedback…")
    export.ingest_feedback()

    if not (os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        log.warning("MODELS_TOKEN not set — skipping scoring")
    else:
        log.info("Scoring pending jobs (max=%d)…", max_jobs)
        try:
            scored = scorer.score_all_pending(max_per_run=max_jobs)
            log.info("Scored %d jobs", scored)
        except Exception:
            log.exception("Scoring failed")

    log.info("Exporting data…")
    export.export_jobs()
    export.export_stats()

    stats = db.get_stats()
    log.info(
        "Done. Total: %d | Scored: %d | Strong+: %d",
        stats.get("total", 0),
        stats.get("scored", 0),
        stats.get("strong_plus", 0),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job search pipeline")
    parser.add_argument(
        "--score-only", action="store_true",
        help="Skip scraping; only score pending jobs and export",
    )
    parser.add_argument(
        "--max", type=int, default=50,
        help="Max jobs to score per run when using --score-only (default: 50)",
    )
    args = parser.parse_args()

    if args.score_only:
        score_only(max_jobs=args.max)
    else:
        main()
