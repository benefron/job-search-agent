"""
Claude Code scoring helper — intended to be run BY Claude Code / Claude Cowork.

Claude reads unscored jobs, applies the scoring criteria itself (no external API),
and writes scores back to the database.

Workflow for Claude Code autonomous session:
  1. python -m scraper.score_local --dump [--max N]
       → writes data/scoring_batch.json  (jobs waiting to be scored)
  2. Claude reads data/scoring_batch.json, scores each job, writes data/scored_results.json
  3. python -m scraper.score_local --apply
       → ingests data/scored_results.json into DB, exports JSON, cleans up temp files
  4. git pull --rebase origin main
     git add data/jobs.db data/jobs.json data/stats.json data/jobs_export.csv
     git commit -m "chore: local scoring via Claude Code [skip ci]"
     git push origin main

Run from repo root.
"""

import argparse
import json
import logging
import os
import sys

os.makedirs("data", exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BATCH_FILE   = "data/scoring_batch.json"
RESULTS_FILE = "data/scored_results.json"

SCORING_CRITERIA = """
You are scoring job postings for the candidate (systems neuroscientist, AI/ML research engineer,
postdoc at a neurotech research institute). Their ideal roles: neuromorphic computing, neurotech R&D,
embedded AI, machine vision, real-time systems, HIL/SIL, computational neuroscience in industry.

HARD EXCLUSION — score 0 if any apply:
- PhD/doctoral student positions (he already has a PhD)
- Internships, student/werkstudent roles
- Research Assistant (overqualified)
- Job is primarily in Dutch
- Requires Dutch fluency/native as hard requirement
- Explicitly no visa sponsorship ("cannot sponsor", "no visa sponsorship", "must be authorized to work", etc.)
- VIE program (requires age 18-28)

SCORING RUBRIC:
90-100  Perfect fit: qualifications, domain, role level, location all aligned
70-89   Strong fit: strong qualification match, minor gaps
50-69   Moderate fit: overlapping skills, some gaps, worth considering
30-49   Stretch: some transferable skills, meaningful gaps
0-29    Poor fit / hard exclusion

HIGH FIT skills: Python, PyTorch, ML/deep learning, signal processing, C++, MATLAB,
  computer vision, machine vision, embedded AI, real-time systems, HIL/SIL simulation,
  Simulink, sensor fusion, Kalman filtering, closed-loop control, neuroscience methods,
  spiking neural networks (SNN), electrophysiology, bio-inspired algorithms.

LOW FIT: chip/IC/VLSI/RTL design, VHDL/Verilog, clinical medicine, pure sales/management.

DOMAIN RULES:
- Data Scientist → HIGH only if in bio/neuro/biomedical/health/medical-imaging domain.
  Cap at 45 for fintech/BI/marketing/e-commerce DS.
- Neuroscience / biomedical / BCI / neurotech / neuromorphic / medical-imaging roles →
  apply a strong +8–15 pt bonus vs. equivalent role outside these domains. These are
  the candidate's home domain. Do NOT undervalue them.
- Research Scientist / Applied Scientist / Research Engineer at a neurotech, neuromorphic,
  brain-inspired, or neuroAI company (e.g. Innatera, SynSense, BrainChip, imec, NERF, VIB,
  Prophesee) → HIGH fit (65-80) if the role is ML/software/algorithm/research (not chip/VLSI).
- R&D Scientist / Research Scientist / Applied Scientist in neuroscience or brain-inspired
  domain → HIGH (65-80) when the candidate's skills align.
- HIL/SIL/real-time control → HIGH (rare differentiator on his CV)
- Postdoc in computational neuroscience/neuroAI → MODERATE (50-65); legitimate fallback.

LOCATION:
- Belgium (Leuven, Brussels, Liège, Ghent, Antwerp, Mechelen, Zaventem, Hasselt, Tervuren):
  standard scoring — all acceptable commute from Leuven.
- Netherlands (NL-only, not remote): slightly stricter bar; roles scoring 55-65 for Belgium → 50-60 for NL.
  Strong matches (70+) unaffected.
- Lab tech/manager Belgium → max 30-50; NL → max 0-20.

fit_category values: "perfect" | "strong" | "moderate" | "stretch" | "poor"

job_category — pick exactly one:
  "Neuromorphic / Brain-Inspired" | "Edge AI / Embedded AI" | "Machine Learning / Deep Learning"
  "Data Science / Applied ML" | "Computer Vision / Perception" | "Signal Processing / DSP"
  "Neuroscience / Neurotech / BCI" | "Research / Academic (Postdoc)" | "Software Engineering"
  "Hardware / Embedded Systems" | "Biomedical / Bioengineering" | "Real-Time Systems / Control"
  "Consulting / Business" | "Other"

For each job output a JSON object:
{
  "id": "<job id from input>",
  "score": <int 0-100>,
  "fit_category": "<value>",
  "job_category": "<value>",
  "job_summary": "<1-2 sentences: what the role is and what the person will do>",
  "top_qualifications": ["<required qual 1>", "<required qual 2>", "<required qual 3>"],
  "key_matches": ["<candidate skill matching a stated requirement>", ...],
  "key_gaps": ["<stated requirement the candidate does not meet>", ...],
  "rationale": "<one sentence explaining the score, citing specific job requirements>"
}
"""


def cmd_dump(max_jobs: int) -> None:
    """Export unscored jobs to data/scoring_batch.json for Claude to read."""
    from scraper import db
    db.init_db()
    pending = db.get_unscored_jobs()[:max_jobs]
    if not pending:
        log.info("No unscored jobs.")
        sys.exit(0)

    batch = []
    for job in pending:
        batch.append({
            "id":          job["id"],
            "title":       job["title"],
            "company":     job["company"],
            "location":    job.get("location", ""),
            "description": (job.get("description") or "")[:3500],
            "source":      job.get("source", ""),
            "date_found":  job.get("date_found", ""),
        })

    with open(BATCH_FILE, "w") as f:
        json.dump({"scoring_criteria": SCORING_CRITERIA, "jobs": batch}, f, indent=2)

    log.info("Wrote %d jobs to %s — Claude should now score them and write %s",
             len(batch), BATCH_FILE, RESULTS_FILE)
    print(f"\nNext step: Claude reads {BATCH_FILE}, scores each job, writes {RESULTS_FILE}")
    print(f"Then run:  python -m scraper.score_local --apply\n")


def cmd_apply() -> None:
    """Ingest Claude's scored results from data/scored_results.json into the DB."""
    from scraper import db
    from scraper import export

    if not os.path.exists(RESULTS_FILE):
        log.error("%s not found. Claude must write scored results there first.", RESULTS_FILE)
        sys.exit(1)

    with open(RESULTS_FILE) as f:
        results = json.load(f)

    if not isinstance(results, list):
        log.error("%s must be a JSON array of scored job objects.", RESULTS_FILE)
        sys.exit(1)

    db.init_db()
    applied = 0
    for r in results:
        job_id = r.get("id")
        if not job_id:
            log.warning("Skipping result with no id: %s", r)
            continue
        try:
            db.update_score(
                job_id=job_id,
                score=int(r.get("score", 0)),
                fit_category=str(r.get("fit_category", "poor")),
                key_matches=r.get("key_matches", []),
                key_gaps=r.get("key_gaps", []),
                rationale=str(r.get("rationale", "")),
                job_summary=str(r.get("job_summary", "")),
                top_qualifications=r.get("top_qualifications", []),
                job_category=str(r.get("job_category", "Other")),
            )
            log.info("  Applied [%d] %s", r.get("score", 0), job_id)
            applied += 1
        except Exception as exc:
            log.warning("  Failed to apply score for %s: %s", job_id, exc)

    log.info("Applied %d/%d scores to DB.", applied, len(results))

    log.info("Exporting JSON…")
    export.export_jobs()
    export.export_stats()

    # Clean up temp files
    for f in (BATCH_FILE, RESULTS_FILE):
        if os.path.exists(f):
            os.remove(f)
            log.info("Removed %s", f)

    stats = db.get_stats()
    log.info("Done. Total: %d | Scored: %d | Strong+: %d",
             stats.get("total", 0), stats.get("scored", 0), stats.get("strong_plus", 0))
    print("\nNext step:")
    print("  git pull --rebase origin main")
    print("  git add data/jobs.db data/jobs.json data/stats.json data/jobs_export.csv")
    print('  git commit -m "chore: local scoring via Claude Code [skip ci]"')
    print("  git push origin main\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude Code local scoring helper")
    parser.add_argument("cmd", choices=["dump", "apply"], help="dump | apply")
    parser.add_argument("--max", type=int, default=50, help="Max jobs to export (default: 50, used with dump)")
    args = parser.parse_args()

    if args.cmd == "dump":
        cmd_dump(args.max)
    else:
        cmd_apply()
