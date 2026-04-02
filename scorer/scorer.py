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
Your task is to score each job posting's fit for his profile on a 0-100 scale.

Score rubric:
- 90-100: Perfect fit — domain, role, location, and level are all aligned
- 70-89: Strong fit — strong domain/skill alignment, minor gaps
- 50-69: Moderate fit — overlapping domain, some gaps, worth considering
- 30-49: Stretch — relevant skills transfer but domain or role is a mismatch
- 0-29: Poor fit — minimal alignment, don't recommend unless location and salary are exceptional

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
{job.get('description', '')[:3000]}

Return JSON with exactly these fields:
{{
  "score": <integer 0-100>,
  "fit_category": "<perfect|strong|moderate|stretch|poor>",
  "key_matches": ["<match1>", "<match2>", "<match3>"],
  "key_gaps": ["<gap1>", "<gap2>"],
  "rationale": "<one concise sentence explaining the score>"
}}
""".strip()


def score_job(job: dict, client: OpenAI, feedback_context: dict, profile_text: str) -> dict | None:
    """Score a single job. Returns parsed JSON dict or None on failure."""
    prompt = _build_user_prompt(job, feedback_context, profile_text)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=300,
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
        logger.warning("Scoring API error for job %s: %s", job.get("id"), exc)
        return None


def score_all_pending(delay: float = 1.5) -> int:
    """Score all unscored jobs in the DB. Returns number of jobs scored."""
    pending = db.get_unscored_jobs()
    if not pending:
        logger.info("No unscored jobs.")
        return 0

    logger.info("Scoring %d jobs...", len(pending))
    client = _get_client()
    feedback_context = db.get_recent_feedback()
    profile_text = get_profile_text()
    scored = 0

    for job in pending:
        result = score_job(job, client, feedback_context, profile_text)
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
        )
        logger.info(
            "  Scored: [%d] %s at %s — %s",
            result.get("score", 0), job["title"], job["company"],
            result.get("rationale", "")[:80],
        )
        scored += 1
        time.sleep(delay)

    logger.info("Scoring complete. %d/%d jobs scored.", scored, len(pending))
    return scored
