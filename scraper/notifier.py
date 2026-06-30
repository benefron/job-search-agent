"""
Email notifications for the job search pipeline.

Requires environment variables:
  GMAIL_APP_PASSWORD    — Gmail App Password (not your regular password)
  NOTIFY_EMAIL          — recipient address (e.g. your-email@gmail.com)
  NOTIFY_EMAIL_SENDER   — sender address (same as NOTIFY_EMAIL if using Gmail)

To create a Gmail App Password:
  Google Account → Security → 2-Step Verification → App Passwords
  Create one named "Job Search Agent" and store it as a GitHub repo secret.
"""

import logging
import os
import smtplib
from collections import defaultdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SENDER = os.getenv("NOTIFY_EMAIL_SENDER", os.getenv("NOTIFY_EMAIL", ""))
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def is_configured() -> bool:
    return bool(os.getenv("GMAIL_APP_PASSWORD"))


def _send(subject: str, html_body: str) -> None:
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not password:
        logger.warning("GMAIL_APP_PASSWORD not set — skipping email send.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SENDER, password)
        smtp.sendmail(SENDER, NOTIFY_EMAIL, msg.as_string())

    logger.info("Email sent: %s → %s", subject, NOTIFY_EMAIL)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

_SCORE_COLORS = {
    "perfect": ("#166534", "#dcfce7"),
    "strong":  ("#1e3a8a", "#dbeafe"),
    "moderate": ("#713f12", "#fef3c7"),
    "stretch": ("#374151", "#f3f4f6"),
    "poor":    ("#7f1d1d", "#fee2e2"),
}


def _job_card_html(job: dict) -> str:
    cat = job.get("fit_category", "stretch")
    fg, bg = _SCORE_COLORS.get(cat, ("#374151", "#f3f4f6"))
    score = job.get("score", "?")
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    url = job.get("url", "#")
    summary = job.get("job_summary", "")
    rationale = job.get("rationale", "")
    job_cat = job.get("job_category", "")

    return f"""
<div style="border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:12px;background:#fff;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
    <div style="flex:1;">
      <div style="font-size:15px;font-weight:600;color:#1e293b;">{title}</div>
      <div style="font-size:13px;color:#475569;margin-top:2px;">{company} · {location}</div>
      {f'<div style="font-size:11px;color:#64748b;margin-top:2px;">{job_cat}</div>' if job_cat else ''}
    </div>
    <div style="min-width:42px;text-align:center;font-size:18px;font-weight:700;
                padding:4px 8px;border-radius:6px;background:{bg};color:{fg};">
      {score}
    </div>
  </div>
  {f'<div style="font-size:13px;color:#334155;margin-top:8px;line-height:1.5;">{summary}</div>' if summary else ''}
  {f'<div style="font-size:12px;color:#64748b;margin-top:6px;font-style:italic;">{rationale}</div>' if rationale else ''}
  <div style="margin-top:10px;">
    <a href="{url}" style="font-size:13px;color:#1952a0;text-decoration:none;font-weight:500;">
      View posting →
    </a>
  </div>
</div>
"""


def _email_wrapper(title: str, subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:32px auto;background:#fff;border-radius:10px;
            border:1px solid #e2e8f0;overflow:hidden;">
  <div style="background:#1952a0;color:#fff;padding:20px 24px;">
    <div style="font-size:18px;font-weight:700;">{title}</div>
    <div style="font-size:13px;opacity:0.85;margin-top:4px;">{subtitle}</div>
  </div>
  <div style="padding:20px 24px;">
    {body}
  </div>
  <div style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:12px 24px;
              font-size:12px;color:#64748b;text-align:center;">
    Job Search Agent · <a href="#"
    style="color:#1952a0;">Dashboard</a>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_high_score_alert(jobs: list[dict]) -> None:
    """Send an immediate alert email for newly-scored jobs at 80+."""
    if not jobs:
        return

    n = len(jobs)
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"[Job Alert] {n} new top match{'es' if n > 1 else ''} — {today}"

    cards = "".join(_job_card_html(j) for j in sorted(jobs, key=lambda x: x.get("score", 0), reverse=True))
    intro = (
        f"<p style='font-size:14px;color:#334155;margin-bottom:16px;'>"
        f"<strong>{n} job{'s' if n > 1 else ''}</strong> scored 80 or above since the last run."
        f" Review and apply soon — these are strong matches.</p>"
    )
    body = intro + cards

    html = _email_wrapper(
        title="Top Job Alert",
        subtitle=f"{n} new match{'es' if n > 1 else ''} scoring 80+ · {today}",
        body=body,
    )
    _send(subject, html)


def send_weekly_digest(jobs: list[dict]) -> None:
    """Send the weekly digest of new jobs found in the past 7 days."""
    if not jobs:
        return

    n = len(jobs)
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"[Weekly Digest] {n} new jobs — week of {today}"

    # Group by job_category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for j in sorted(jobs, key=lambda x: x.get("score", 0), reverse=True):
        cat = j.get("job_category") or "Other"
        by_cat[cat].append(j)

    sections = ""
    for cat, cat_jobs in by_cat.items():
        cards = "".join(_job_card_html(j) for j in cat_jobs)
        sections += f"""
<div style="margin-bottom:24px;">
  <div style="font-size:13px;font-weight:700;color:#1952a0;text-transform:uppercase;
              letter-spacing:0.06em;border-bottom:2px solid #dbeafe;
              padding-bottom:4px;margin-bottom:10px;">{cat}</div>
  {cards}
</div>"""

    intro = (
        f"<p style='font-size:14px;color:#334155;margin-bottom:20px;'>"
        f"<strong>{n} new job{'s' if n > 1 else ''}</strong> found in the past 7 days "
        f"with a score of 35 or above, grouped by role type.</p>"
    )
    body = intro + sections

    html = _email_wrapper(
        title="Weekly Job Digest",
        subtitle=f"{n} new jobs · week of {today}",
        body=body,
    )
    _send(subject, html)
