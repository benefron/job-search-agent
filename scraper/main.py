"""
Pipeline entrypoint.

Usage (local):
    export GITHUB_TOKEN=ghp_...
    python -m scraper.main

Run from repo root. Creates data/ if needed.
"""

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


if __name__ == "__main__":
    main()
