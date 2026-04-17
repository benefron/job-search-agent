"""
Job scorer using GitHub Models API (OpenAI-compatible endpoint).
Uses GPT-4o-mini (or gpt-4o) via your GitHub Copilot Pro PAT — zero additional cost.
"""

import os
import json
import logging
import time
from openai import OpenAI

from scraper.profile import get_profile_text
from scraper import db

logger = logging.getLogger(__name__)

GITHUB_MODELS_BASE = "https://models.inference.ai.azure.com"
# gpt-4o-mini is fast, cheap on token quota, and sufficient for scoring
# Change to "gpt-4o" or "claude-3-5-sonnet" for higher quality if quota allows
MODEL = os.getenv("SCORING_MODEL", "gpt-4o-mini")


def _get_client() -> OpenAI:
    # Prefer a dedicated PAT that has the 'models' permission.
    # In Actions, store it as the MODELS_TOKEN repo secret.
    # Locally, GITHUB_TOKEN (Copilot PAT) also works if it has models access.
    token = os.getenv("MODELS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "No token found for GitHub Models API. "
            "Set MODELS_TOKEN (repo secret) to a PAT with 'models:read' scope: "
            "https://github.com/settings/tokens"
        )
    return OpenAI(
        base_url=GITHUB_MODELS_BASE,
        api_key=token,
    )


SYSTEM_PROMPT = """You are an expert career advisor helping Dr. Ben Efron, a systems neuroscientist, evaluate job postings.

CRITICAL — READ THE JOB DESCRIPTION CAREFULLY:
Do NOT score based on job title keywords alone. Read the full description, focusing on:
- "Required qualifications", "Requirements", "What you bring", "Your profile", "About you" sections
- Core responsibilities and technical tasks described
Score based on whether Ben's ACTUAL skills match what the role REQUIRES, even if domain labels differ.

HARD EXCLUSION RULES (score 0 immediately if any apply):
- PhD / doctoral positions (doctoral candidate, PhD student, promotie) — he already has a PhD
- Internships, student positions, working student, werkstudent
- Research Assistant roles — he is overqualified (PhD-level candidate)
- Job description is primarily in Dutch (not English)
- Job requires Dutch fluency / native-level Dutch as a hard requirement
- Relocation outside Netherlands / Belgium is explicitly required

ELIGIBILITY NOTE:
- Ben has both MSc and PhD. Roles requiring MSc or equivalent are fully eligible.

VISA & SALARY CONSTRAINT:
- Ben needs a work visa for the Netherlands, which requires a minimum gross salary of ~€5,000/month.
- Score down (max 30) any industry job that likely pays below this threshold (e.g. medior/junior embedded SW, RA).
- EXCEPTION: postdoctoral positions, university positions, UMCs, and publicly funded research institutes are exempt.

QUALIFICATION ALIGNMENT — weigh these heavily (not just domain labels):
HIGH FIT if required skills include any of: Python, ML/deep learning, PyTorch, data analysis, signal processing,
  experimental design, statistical modelling, hardware-software integration, computer vision, sensor systems,
  embedded AI, real-time processing, scientific programming.
LOW FIT if required skills are primarily: chip/IC/VLSI design, VHDL/Verilog/RTL, clinical medicine,
  pure audio codec standardisation, pure SLAM without AI/neuro component, program/project management as primary role,
  sales/account management, Dutch-only stack.

DOMAIN FIT — roles with genuine qualification overlap even if not labeled "neuro":
- Data Scientist / Applied ML / ML Engineer → HIGH if Python + ML + analysis required
- Computer Vision / Perception Scientist → HIGH
- Embedded AI / edge inference / sensor-fusion → HIGH
- Systems & algorithms R&D requiring multi-disciplinary engineering → HIGH
- Applied / Research Scientist roles in tech or engineering → MODERATE–HIGH
- Postdoctoral researcher in neuroscience/neuroAI/computational neuro → MODERATE–HIGH
- Pure audio signal processing / audio coding / standardisation → LOW (niche domain mismatch)
- Pure SLAM without broader AI/neuro → LOW

Score rubric:
- 90-100: Perfect fit — qualifications, domain, role level, and location all aligned
- 70-89: Strong fit — strong qualification alignment, minor gaps
- 50-69: Moderate fit — overlapping qualifications, some gaps, worth considering
- 30-49: Stretch — some skills transfer but meaningful qualification gaps
- 0-29: Poor fit — minimal qualification alignment or hard exclusion

fit_category values: "perfect", "strong", "moderate", "stretch", "poor"

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
  "job_summary": "<1-2 neutral sentences: what is this role and what will the person do>",
  "top_qualifications": ["<key required qualification 1>", "<key required qualification 2>", "<key required qualification 3>"],
  "key_matches": ["<Ben skill that matches a stated requirement>", "<match2>", "<match3>"],
  "key_gaps": ["<stated requirement Ben does not meet>", "<gap2>"],
  "rationale": "<one sentence: why this score, referencing specific requirements from the posting>"
}}
""".strip()


# Sentinel to signal the caller to stop scoring (rate-limit hit)
class _RateLimitExceeded(Exception):
    pass


def score_job(job: dict, client: OpenAI, feedback_context: dict, profile_text: str) -> dict | None:
    """Score a single job. Returns parsed JSON dict or None on failure.
    Raises _RateLimitExceeded if the API returns a 429 so the caller can stop.
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
        # Strip markdown fences if model adds them despite instructions
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
        # 429 / rate-limit errors — propagate so caller can stop cleanly
        if "429" in exc_str or "rate limit" in exc_str.lower() or "RateLimitError" in type(exc).__name__:
            raise _RateLimitExceeded(exc_str) from exc
        logger.warning("Scoring API error for job %s: %s", job.get("id"), exc)
        return None


def score_all_pending(delay: float = 3.0, max_per_run: int = 30) -> int:
    """Score unscored jobs in the DB (newest first). Returns number scored.

    Stops early on rate-limit errors to avoid burning the daily quota.
    ``max_per_run`` caps how many we attempt per workflow run to stay within
    GitHub Models free-tier limits (~15 RPM, ~150 RPD for gpt-4o-mini).
    """
    pending = db.get_unscored_jobs()
    if not pending:
        logger.info("No unscored jobs.")
        return 0

    # Prioritise recently-found jobs; cap to avoid blowing the quota.
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
            logger.warning("Rate limit hit after %d jobs — stopping scoring for this run: %s", scored, exc)
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
