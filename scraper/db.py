"""
SQLite database layer — deduplication, job storage, feedback.
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

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
                job_summary   TEXT,
                top_qualifications TEXT,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hidden_items (
                id           TEXT NOT NULL,
                entity_type  TEXT NOT NULL,
                url          TEXT NOT NULL,
                label        TEXT DEFAULT '',
                deleted_at   TEXT NOT NULL,
                PRIMARY KEY (id, entity_type)
            )
        """)
        _migrate_db(conn)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add missing columns to handle schema upgrades on existing databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    new_cols = {
        "job_summary": "TEXT",
        "top_qualifications": "TEXT",
    }
    for col, coltype in new_cols.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {coltype}")

def _job_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def is_seen(url: str) -> bool:
    job_id = _job_id(url)
    with _get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is not None:
            return True
        hidden = conn.execute(
            "SELECT 1 FROM hidden_items WHERE id = ? AND entity_type = 'job'",
            (job_id,),
        ).fetchone()
        return hidden is not None


def is_hidden_entity(url: str, entity_type: str) -> bool:
    entity_id = _job_id(url)
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM hidden_items WHERE id = ? AND entity_type = ?",
            (entity_id, entity_type),
        ).fetchone()
    return row is not None


def hide_entity(url: str, entity_type: str, label: str = "") -> None:
    entity_id = _job_id(url)
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO hidden_items (id, entity_type, url, label, deleted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entity_id, entity_type, url, label, datetime.utcnow().isoformat()),
        )


def delete_job_and_tombstone(job_id: str, reason: str = "") -> None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, url, title, company FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return
        label = f"{row['title']} at {row['company']}"
        if reason:
            label = f"{label} [{reason}]"
        conn.execute(
            """
            INSERT OR IGNORE INTO hidden_items (id, entity_type, url, label, deleted_at)
            VALUES (?, 'job', ?, ?, ?)
            """,
            (row["id"], row["url"], label, datetime.utcnow().isoformat()),
        )
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


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


# ---------------------------------------------------------------------------
# Cross-source deduplication helpers
# ---------------------------------------------------------------------------

import re as _re


def _normalize_title(title: str) -> str:
    """Normalise a job title for cross-source duplicate detection."""
    t = title.lower().strip()
    # Strip trailing location tags like "- NL", "(Netherlands)", "- Amsterdam"
    t = _re.sub(
        r"\s*[-–|]\s*(nl|netherlands|the netherlands|amsterdam|eindhoven|delft|utrecht|rotterdam|nijmegen|all genders).*$",
        "", t,
    )
    t = _re.sub(r"\s*\(.*?(nl|netherlands|all genders).*?\)", "", t)
    # Collapse whitespace
    return _re.sub(r"\s+", " ", t).strip()


def find_linkedin_job_by_title_company(title: str, company: str) -> str | None:
    """Return the job_id of an existing LinkedIn job with a matching title+company, or None."""
    norm = _normalize_title(title)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title FROM jobs WHERE company = ? AND source = 'linkedin'",
            (company,),
        ).fetchall()
    for row in rows:
        if _normalize_title(row["title"]) == norm:
            return row["id"]
    return None


def find_non_linkedin_job_by_title_company(title: str, company: str) -> tuple[str, str] | None:
    """Return (job_id, url) of an existing non-LinkedIn job with matching title+company, or None."""
    norm = _normalize_title(title)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, url FROM jobs WHERE company = ? AND source != 'linkedin'",
            (company,),
        ).fetchall()
    for row in rows:
        if _normalize_title(row["title"]) == norm:
            return row["id"], row["url"]
    return None


def replace_with_linkedin(
    old_job_id: str,
    linkedin_url: str,
    linkedin_source: str = "linkedin",
) -> str:
    """Tombstone an existing non-LinkedIn job and re-insert it with the LinkedIn URL.

    Returns the new job_id (hash of the LinkedIn URL).
    """
    new_id = _job_id(linkedin_url)
    with _get_conn() as conn:
        old = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (old_job_id,)
        ).fetchone()
        if old is None:
            return new_id

        # Tombstone the old URL so it won't be re-ingested
        conn.execute(
            """
            INSERT OR IGNORE INTO hidden_items (id, entity_type, url, label, deleted_at)
            VALUES (?, 'job', ?, ?, ?)
            """,
            (
                old_job_id, old["url"],
                f"{old['title']} at {old['company']} [replaced by linkedin]",
                datetime.utcnow().isoformat(),
            ),
        )
        # Insert (or ignore if already present) with the LinkedIn URL
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (id, source, url, title, company, location, description,
                 date_posted, date_found, score, fit_category, key_matches,
                 key_gaps, rationale, job_summary, top_qualifications,
                 status, feedback, connection_notes)
            SELECT ?, ?, ?, title, company, location, description,
                   date_posted, date_found, score, fit_category, key_matches,
                   key_gaps, rationale, job_summary, top_qualifications,
                   status, feedback, connection_notes
            FROM jobs WHERE id = ?
            """,
            (new_id, linkedin_source, linkedin_url, old_job_id),
        )
        # Remove the old record
        conn.execute("DELETE FROM jobs WHERE id = ?", (old_job_id,))
    return new_id


def update_score(
    job_id: str,
    score: int,
    fit_category: str,
    key_matches: list[str],
    key_gaps: list[str],
    rationale: str,
    job_summary: str = "",
    top_qualifications: list[str] | None = None,
) -> None:
    if top_qualifications is None:
        top_qualifications = []
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                score = ?, fit_category = ?,
                key_matches = ?, key_gaps = ?, rationale = ?,
                job_summary = ?, top_qualifications = ?
            WHERE id = ?
            """,
            (
                score, fit_category,
                json.dumps(key_matches), json.dumps(key_gaps), rationale,
                job_summary, json.dumps(top_qualifications),
                job_id,
            ),
        )


def apply_feedback(feedback_records: list[dict]) -> None:
    """Apply feedback from dashboard export to the DB."""
    with _get_conn() as conn:
        for rec in feedback_records:
            record_type = rec.get("record_type", "job")

            # Labs are tracked as hidden URLs if user marks delete.
            if record_type == "lab":
                if rec.get("status") == "delete" and rec.get("url"):
                    entity_id = _job_id(rec["url"])
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO hidden_items
                            (id, entity_type, url, label, deleted_at)
                        VALUES (?, 'lab', ?, ?, ?)
                        """,
                        (
                            entity_id,
                            rec["url"],
                            rec.get("name", ""),
                            datetime.utcnow().isoformat(),
                        ),
                    )
                continue

            job_id = rec.get("id")
            if not job_id:
                continue

            feedback_val = rec.get("feedback", 0)
            status_val = rec.get("status", "new")

            # thumbs-down OR explicit delete → tombstone and remove from DB
            should_delete = (
                rec.get("status") == "delete"
                or feedback_val == -1
            )
            if should_delete:
                row = conn.execute(
                    "SELECT id, url, title, company FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is not None:
                    reason = "disliked" if feedback_val == -1 else "deleted"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO hidden_items
                            (id, entity_type, url, label, deleted_at)
                        VALUES (?, 'job', ?, ?, ?)
                        """,
                        (
                            row["id"],
                            row["url"],
                            f"{row['title']} at {row['company']} [{reason}]",
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                continue

            # "gone" → keep the record (preserve thumbs-up) but mark as gone
            conn.execute(
                "UPDATE jobs SET feedback = ?, status = ?, connection_notes = ? WHERE id = ?",
                (
                    feedback_val,
                    status_val,
                    rec.get("connection_notes", ""),
                    job_id,
                ),
            )
            if feedback_val != 0:
                conn.execute(
                    "INSERT INTO feedback_log"
                    " (job_id, timestamp, feedback, notes)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        job_id,
                        datetime.utcnow().isoformat(),
                        feedback_val,
                        rec.get("connection_notes", ""),
                    ),
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


def get_jobs_for_export(min_score: int = 35) -> list[dict]:
    """Return scored jobs (>= min_score) plus all unscored jobs, sorted by score desc."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, source, url, title, company, location, date_posted, date_found,
                   score, fit_category, key_matches, key_gaps, rationale,
                   job_summary, top_qualifications,
                   status, feedback, connection_notes
            FROM jobs
            WHERE score IS NULL OR score >= ?
            ORDER BY score DESC NULLS LAST, date_found DESC
            """,
            (min_score,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["key_matches"] = json.loads(d["key_matches"] or "[]")
        d["key_gaps"] = json.loads(d["key_gaps"] or "[]")
        d["top_qualifications"] = json.loads(d["top_qualifications"] or "[]")
        results.append(d)
    return results


def get_unscored_jobs() -> list[dict]:
    """Return jobs that have not yet been scored."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, company, location, description FROM jobs WHERE score IS NULL",
        ).fetchall()
    return [dict(r) for r in rows]


def prune_known_noise_jobs() -> int:
    """Remove historical noisy pages and tombstone them to prevent re-ingestion."""
    removed = 0
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, url, title, company
            FROM jobs
            WHERE
                (company IN ('imec', 'Innatera') AND source = 'company_html')
                OR (company = 'Innatera' AND url LIKE 'https://www.innatera.com/%')
            """
        ).fetchall()

        for r in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO hidden_items (id, entity_type, url, label, deleted_at)
                VALUES (?, 'job', ?, ?, ?)
                """,
                (
                    r["id"],
                    r["url"],
                    f"{r['title']} at {r['company']} [auto-pruned-noise]",
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.execute("DELETE FROM jobs WHERE id = ?", (r["id"],))
            removed += 1
    return removed


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
        "last_updated": datetime.now(ZoneInfo("Europe/Brussels")).isoformat(timespec="seconds"),
    }
