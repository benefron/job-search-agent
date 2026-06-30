"""
Pipeline entrypoint.

Usage (local):
    export GITHUB_TOKEN=ghp_...
    python -m scraper.main                    # full pipeline
    python -m scraper.main --score-only [--max N]
    python -m scraper.main --weekly-digest    # score + send weekly email digest

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


def _run_notifications(db, notifier) -> None:
    """Send high-score alerts for any newly-scored jobs at 80+."""
    if not notifier.is_configured():
        return
    try:
        alert_jobs = db.get_new_high_score_jobs(min_score=80)
        if alert_jobs:
            log.info("Sending high-score alerts for %d jobs…", len(alert_jobs))
            notifier.send_high_score_alert(alert_jobs)
            db.mark_alerts_sent([j["id"] for j in alert_jobs])
    except Exception:
        log.exception("High-score alert failed — continuing")


def main() -> None:
    from scraper import db, scraper, companies, export
    from scraper import notifier
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

    # ── 4b. Archive stale jobs ──
    try:
        archived = db.archive_stale_jobs()
        if archived:
            log.info("Archived %d stale jobs (>14 days old, not seen recently)", archived)
    except Exception:
        log.exception("Stale job archiving failed — continuing")

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

    # ── 5b. Send high-score alerts ──
    _run_notifications(db, notifier)

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
    from scraper import notifier
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

    # Send high-score alerts for any newly-scored 80+ jobs
    _run_notifications(db, notifier)

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


def weekly_digest() -> None:
    """Send the weekly email digest of new jobs, then export updated data."""
    from scraper import db, export
    from scraper import notifier
    from scorer import scorer

    log.info("Initialising database…")
    db.init_db()

    log.info("Ingesting feedback…")
    export.ingest_feedback()

    # Score any remaining pending jobs first
    if os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        log.info("Scoring pending jobs before digest…")
        try:
            scored = scorer.score_all_pending(max_per_run=50)
            log.info("Scored %d jobs", scored)
        except Exception:
            log.exception("Scoring failed — continuing with digest")

    # Send high-score alerts
    _run_notifications(db, notifier)

    # Send weekly digest
    if notifier.is_configured():
        try:
            digest_jobs = db.get_jobs_for_digest(days=7, min_score=35)
            if digest_jobs:
                log.info("Sending weekly digest for %d jobs…", len(digest_jobs))
                notifier.send_weekly_digest(digest_jobs)
                db.mark_digest_sent([j["id"] for j in digest_jobs])
            else:
                log.info("No new jobs for weekly digest.")
        except Exception:
            log.exception("Weekly digest failed")
    else:
        log.warning("Email not configured — skipping digest (set GMAIL_APP_PASSWORD and NOTIFY_EMAIL)")

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
        "--weekly-digest", action="store_true",
        help="Score pending jobs, send weekly email digest, and export",
    )
    parser.add_argument(
        "--max", type=int, default=50,
        help="Max jobs to score per run (default: 50)",
    )
    args = parser.parse_args()

    if args.weekly_digest:
        weekly_digest()
    elif args.score_only:
        score_only(max_jobs=args.max)
    else:
        main()
