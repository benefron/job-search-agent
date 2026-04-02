"""
SQLite database layer — deduplication, job storage, feedback.
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                source        TEXT NOT NULL,
                url           TEXT NOT NULL,
                title         TEXT NOT NULL,
                company       TEXT NOT NULL,
                location      TEXT,
                description   TEXT,
                date_posted   TEXT,
                date_found    TEXT NOT NULL,
                score         INTEGER,
                fit_category  TEXT,
                key_matches   TEXT,
                key_gaps      TEXT,
                rationale     TEXT,
                status        TEXT DEFAULT 'new',
                feedback      INTEGER DEFAULT 0,
                connection_notes TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_log (
                job_id       TEXT NOT NULL,
                timestamp    TEXT NOT NULL,
                feedback     INTEGER NOT NULL,
                notes        TEXT
            )
        """)


def _job_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def is_seen(url: str) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (_job_id(url),)).fetchone()
        return row is not None


def insert_job(
    source: str,
    url: str,
    title: str,
    company: str,
    location: str,
    description: str,
    date_posted: str | None = None,
) -> str:
    """Insert a new job. Returns the job id."""
    job_id = _job_id(url)
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (id, source, url, title, company, location, description, date_posted, date_found)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, source, url, title, company, location, description,
                date_posted, datetime.utcnow().isoformat(),
            ),
        )
    return job_id


def update_score(
    job_id: str,
    score: int,
    fit_category: str,
    key_matches: list[str],
    key_gaps: list[str],
    rationale: str,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                score = ?, fit_category = ?,
                key_matches = ?, key_gaps = ?, rationale = ?
            WHERE id = ?
            """,
            (
                score, fit_category,
                json.dumps(key_matches), json.dumps(key_gaps), rationale,
                job_id,
            ),
        )


def apply_feedback(feedback_records: list[dict]) -> None:
    """Apply feedback from dashboard export to the DB."""
    with _get_conn() as conn:
        for rec in feedback_records:
            job_id = rec.get("id")
            if not job_id:
                continue
            conn.execute(
                "UPDATE jobs SET feedback = ?, status = ?, connection_notes = ? WHERE id = ?",
                (
                    rec.get("feedback", 0),
                    rec.get("status", "new"),
                    rec.get("connection_notes", ""),
                    job_id,
                ),
            )
            if rec.get("feedback", 0) != 0:
                conn.execute(
                    "INSERT INTO feedback_log (job_id, timestamp, feedback, notes) VALUES (?, ?, ?, ?)",
                    (job_id, datetime.utcnow().isoformat(), rec["feedback"], rec.get("connection_notes", "")),
                )


def get_recent_feedback(n_positive: int = 5, n_negative: int = 5) -> dict:
    """Return recent liked/disliked jobs for few-shot scoring context."""
    with _get_conn() as conn:
        positive = conn.execute(
            "SELECT title, company, description, rationale FROM jobs WHERE feedback = 1 ORDER BY date_found DESC LIMIT ?",
            (n_positive,),
        ).fetchall()
        negative = conn.execute(
            "SELECT title, company, description, rationale FROM jobs WHERE feedback = -1 ORDER BY date_found DESC LIMIT ?",
            (n_negative,),
        ).fetchall()
    return {
        "positive": [dict(r) for r in positive],
        "negative": [dict(r) for r in negative],
    }


def get_jobs_for_export(min_score: int = 40) -> list[dict]:
    """Return all scored jobs above min_score, sorted by score descending."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source, url, title, company, location, date_posted, date_found,
                   score, fit_category, key_matches, key_gaps, rationale,
                   status, feedback, connection_notes
            FROM jobs
            WHERE score IS NOT NULL AND score >= ?
            ORDER BY score DESC, date_found DESC
            """,
            (min_score,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["key_matches"] = json.loads(d["key_matches"] or "[]")
        d["key_gaps"] = json.loads(d["key_gaps"] or "[]")
        results.append(d)
    return results


def get_unscored_jobs() -> list[dict]:
    """Return jobs that have not yet been scored."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, company, location, description FROM jobs WHERE score IS NULL",
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        scored = conn.execute("SELECT COUNT(*) FROM jobs WHERE score IS NOT NULL").fetchone()[0]
        liked = conn.execute("SELECT COUNT(*) FROM jobs WHERE feedback = 1").fetchone()[0]
        skipped = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'skip'").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'applied'").fetchone()[0]
    return {
        "total": total,
        "scored": scored,
        "liked": liked,
        "skipped": skipped,
        "applied": applied,
        "last_updated": datetime.utcnow().isoformat(),
    }
