"""
Job scorer using GitHub Models API (OpenAI-compatible endpoint).
Uses gpt-4o-mini via MODELS_TOKEN / GITHUB_TOKEN — runs in GitHub Actions.

For local scoring via Claude Code, use: python -m scraper.score_local
"""

import os
import json
import logging
import time
from openai import OpenAI

from scraper.profile import get_profile_text
from scraper import db

logger = logging.getLogger(__name__)

GITHUB_MODELS_BASE = "https://models.github.ai/inference"
# gpt-4o-mini is fast, cheap, and sufficient for job scoring.
# Other options on GitHub Models: Phi-4-mini-instruct (faster), MAI-DS-R1 (reasoning, slower).
MODEL = os.getenv("SCORING_MODEL", "gpt-4o-mini")


def _get_client() -> OpenAI:
    token = os.getenv("MODELS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "No token found for GitHub Models API. "
            "Set MODELS_TOKEN (repo secret) to a PAT with 'models:read' scope."
        )
    return OpenAI(base_url=GITHUB_MODELS_BASE, api_key=token)


SYSTEM_PROMPT = """You are an expert career advisor helping the candidate, a systems neuroscientist and AI/ML research engineer, evaluate job postings.

CRITICAL — READ THE JOB DESCRIPTION CAREFULLY:
Do NOT score based on job title keywords alone. Read the full description, focusing on:
- "Required qualifications", "Requirements", "What you bring", "Your profile", "About you" sections
- Core responsibilities and technical tasks described
Score based on whether the candidate's ACTUAL skills match what the role REQUIRES, even if domain labels differ.

HARD EXCLUSION RULES (score 0 immediately if any apply):
- PhD / doctoral positions (doctoral candidate, PhD student, promotie) — he already has a PhD
- Internships, student positions, working student, werkstudent
- Research Assistant roles — he is overqualified (PhD-level candidate)
- Job description is primarily in Dutch (not English)
- Job requires Dutch fluency / native-level Dutch as a hard requirement
- Relocation outside Netherlands / Belgium is explicitly required
- Job explicitly states it does NOT provide visa sponsorship / cannot sponsor work visas (phrases like
  "no visa sponsorship", "cannot sponsor", "not able to sponsor", "visa sponsorship is not available",
  "must be authorized to work without sponsorship", "must have right to work without sponsorship",
  "unable to sponsor work visas", "do not sponsor work visas", "no work permit support") → score 0

ELIGIBILITY NOTE:
- The candidate has both MSc and PhD. Roles requiring MSc or equivalent are fully eligible.

VISA & SALARY CONSTRAINT:
- The candidate needs a work visa for the Netherlands, which requires a minimum gross salary of ~€5,000/month.
- Score down (max 30) any industry job that likely pays below this threshold (e.g. medior/junior embedded SW, RA).
- EXCEPTION: postdoctoral positions, university positions, UMCs, and publicly funded research institutes are exempt.

QUALIFICATION ALIGNMENT — weigh these heavily (not just domain labels):
HIGH FIT if required skills include any of: Python, ML/deep learning, PyTorch, data analysis, signal processing,
  experimental design, statistical modelling, hardware-software integration, computer vision, sensor systems,
  embedded AI, real-time processing, scientific programming, C++, MATLAB (for algorithm/control work),
  machine vision / high-speed imaging, hardware-in-the-loop (HIL) / SIL simulation, Simulink,
  sensor fusion, Kalman filtering, closed-loop control, adaptive state-space methods.
LOW FIT if required skills are primarily: chip/IC/VLSI design, VHDL/Verilog/RTL, clinical medicine,
  pure audio codec standardisation, pure SLAM without AI/neuro component, program/project management as primary role,
  sales/account management, Dutch-only stack.

DOMAIN FIT — roles with genuine qualification overlap even if not labeled "neuro":
- Data Scientist / Applied ML / ML Engineer → HIGH score ONLY if the job is in neuroscience, biology,
  biomedical, bioinformatics, computational biology, health/pharma/biotech, medical imaging, or a
  research/tech company with a clear ML + signal-processing component. Pure business BI, fintech DS,
  marketing analytics, e-commerce analytics → cap score at 45 regardless of Python/ML match.
- Computer Vision / Perception Scientist → HIGH
- Embedded AI / edge inference / sensor-fusion → HIGH
- Machine vision / high-speed imaging / real-time sensing → HIGH
- HIL/SIL, co-simulation, real-time control algorithms → HIGH (strong differentiator)
- Systems & algorithms R&D requiring multi-disciplinary engineering → HIGH
- Research Scientist / Applied Scientist / Research Engineer at a neurotech, neuromorphic, brain-inspired,
  or neuroAI company (e.g. Innatera, SynSense, BrainChip, Neurosity, imec, NERF, VIB, Prophesee,
  Acuitas Medical, Synchron) → HIGH if the role is ML/software/algorithm/research (not chip/VLSI design).
  These are the candidate's home domain regardless of exact job title.
- R&D Scientist / Research Scientist / Applied Scientist in neuroscience, neurotech, brain-inspired,
  or biomedical/bioengineering → HIGH (65–80 range when the candidate's skills align). These roles are exactly
  what the candidate's PhD and postdoc have been building towards.
- Applied / Research Scientist roles in tech or engineering (outside neuro domain) → MODERATE–HIGH
- Postdoctoral researcher in neuroscience/neuroAI/computational neuro → MODERATE (50–65); note it's
  a less preferred path than industry R&D but legitimate fallback.
- Pure audio signal processing / audio coding / standardisation → LOW (niche domain mismatch)
- Pure SLAM without broader AI/neuro → LOW

BIOMEDICAL / NEUROSCIENCE DOMAIN BONUS:
- Jobs in neuroscience, bioengineering, biomedical, computational biology, brain-computer interface,
  medical imaging, biosignals, neurotech, neuromorphic computing, or life-sciences R&D → this is
  the candidate's natural home domain. Apply a strong 8–15 point bonus versus an equivalent role outside
  these domains. R&D, engineering, and research roles in these domains should score at the HIGH
  end of their range — do not undervalue these jobs. When in doubt, lean higher for neuro/bio domain.

LOCATION-CONDITIONAL RULES:
- Belgium (Leuven, Brussels, Liège, Antwerp, Ghent, Mechelen, Zaventem, Hasselt, Tervuren): standard
  scoring — all these cities are within acceptable commute distance of the candidate's base.
- Netherlands (Amsterdam, Eindhoven, Delft, Utrecht, Rotterdam, Breda, etc.): apply a slightly stricter
  standard — relocation to NL needs to be clearly justified. Roles that would score 55–65 for a Belgium
  job should score 50–60 if NL-only and not remote. Strong/perfect matches (70+) are unaffected.
- Lab technician / laboratory technician / lab manager / laboratory manager roles:
  - Belgium location → score 30–50 max (possible door-opener, not ideal)
  - Netherlands or remote → score 0–20 (not worth relocating for)
  - Always note in rationale: "Lab-level role; viable only as Belgium option."

Score rubric:
- 90-100: Perfect fit — qualifications, domain, role level, and location all aligned
- 70-89: Strong fit — strong qualification alignment, minor gaps
- 50-69: Moderate fit — overlapping qualifications, some gaps, worth considering
- 30-49: Stretch — some skills transfer but meaningful qualification gaps
- 0-29: Poor fit — minimal qualification alignment or hard exclusion

fit_category values: "perfect", "strong", "moderate", "stretch", "poor"

job_category — assign exactly one of these:
  "Neuromorphic / Brain-Inspired"
  "Edge AI / Embedded AI"
  "Machine Learning / Deep Learning"
  "Data Science / Applied ML"
  "Computer Vision / Perception"
  "Signal Processing / DSP"
  "Neuroscience / Neurotech / BCI"
  "Research / Academic (Postdoc)"
  "Software Engineering"
  "Hardware / Embedded Systems"
  "Biomedical / Bioengineering"
  "Real-Time Systems / Control"
  "Consulting / Business"
  "Other"

Return ONLY valid JSON, no markdown fences or extra text.
"""


def _build_user_prompt(job: dict, feedback_context: dict, profile_text: str) -> str:
    pos_examples = feedback_context.get("positive", [])
    neg_examples = feedback_context.get("negative", [])

    feedback_section = ""
    if pos_examples:
        feedback_section += "\nPREVIOUSLY LIKED JOBS (score high for similar):\n"
        for ex in pos_examples:
            feedback_section += f"  - {ex['title']} at {ex['company']}: {ex.get('rationale','')}\n"
    if neg_examples:
        feedback_section += "\nPREVIOUSLY DISLIKED JOBS (score low for similar):\n"
        for ex in neg_examples:
            feedback_section += f"  - {ex['title']} at {ex['company']}: {ex.get('rationale','')}\n"

    return f"""
{profile_text}
{feedback_section}

JOB TO EVALUATE:
Title: {job['title']}
Company: {job['company']}
Location: {job.get('location', 'Unknown')}
Description:
{job.get('description', '')[:3500]}

Return JSON with exactly these fields:
{{
  "score": <integer 0-100>,
  "fit_category": "<perfect|strong|moderate|stretch|poor>",
  "job_category": "<one of the job_category values from the system prompt>",
  "job_summary": "<1-2 neutral sentences: what is this role and what will the person do>",
  "top_qualifications": ["<key required qualification 1>", "<key required qualification 2>", "<key required qualification 3>"],
  "key_matches": ["<candidate skill that matches a stated requirement>", "<match2>", "<match3>"],
  "key_gaps": ["<stated requirement the candidate does not meet>", "<gap2>"],
  "rationale": "<one sentence: why this score, referencing specific requirements from the posting>"
}}
""".strip()


class _RateLimitExceeded(Exception):
    pass


def score_job(job: dict, client: OpenAI, feedback_context: dict, profile_text: str) -> dict | None:
    """Score a single job. Returns parsed JSON dict or None on failure.
    Raises _RateLimitExceeded if the API returns a 429.
    """
    prompt = _build_user_prompt(job, feedback_context, profile_text)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error for job %s: %s", job.get("id"), exc)
        return None
    except Exception as exc:
        exc_str = str(exc)
        if (
            "429" in exc_str
            or "rate limit" in exc_str.lower()
            or "budget limit" in exc_str.lower()
            or "RateLimitError" in type(exc).__name__
        ):
            raise _RateLimitExceeded(exc_str) from exc
        logger.warning("Scoring API error for job %s: %s", job.get("id"), exc)
        return None


def score_all_pending(delay: float = 3.0, max_per_run: int = 30) -> int:
    """Score unscored jobs in the DB (newest first). Returns number scored.

    Stops early on rate-limit errors to avoid burning the daily quota.
    max_per_run caps attempts to stay within GitHub Models free-tier limits.
    """
    pending = db.get_unscored_jobs()
    if not pending:
        logger.info("No unscored jobs.")
        return 0

    pending = pending[:max_per_run]
    logger.info("Scoring %d pending jobs (cap=%d)…", len(pending), max_per_run)

    client = _get_client()
    feedback_context = db.get_recent_feedback()
    profile_text = get_profile_text()
    scored = 0

    for job in pending:
        try:
            result = score_job(job, client, feedback_context, profile_text)
        except _RateLimitExceeded as exc:
            logger.warning("Rate limit hit after %d jobs — stopping: %s", scored, exc)
            break

        if result is None:
            logger.warning("  Skipping job %s (scoring failed).", job["id"])
            time.sleep(delay)
            continue

        db.update_score(
            job_id=job["id"],
            score=int(result.get("score", 0)),
            fit_category=str(result.get("fit_category", "poor")),
            key_matches=result.get("key_matches", []),
            key_gaps=result.get("key_gaps", []),
            rationale=str(result.get("rationale", "")),
            job_summary=str(result.get("job_summary", "")),
            top_qualifications=result.get("top_qualifications", []),
            job_category=str(result.get("job_category", "Other")),
        )
        logger.info(
            "  Scored [%d] %s at %s — %s",
            result.get("score", 0), job["title"], job["company"],
            result.get("rationale", "")[:80],
        )
        scored += 1
        time.sleep(delay)

    logger.info("Scoring complete. %d/%d attempted.", scored, len(pending))
    return scored
