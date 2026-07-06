# Job Search Agent

Automated daily job search tailored to your profile. Runs via GitHub Actions, scrapes LinkedIn/Indeed and target company career pages, scores matches using the GitHub Models API, and publishes results to a static dashboard on GitHub Pages.

## Setup

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export GITHUB_TOKEN=your_personal_access_token  # needs models:read scope
   ```
   For GitHub Actions, add these repository secrets:
   - `MODELS_TOKEN` — PAT with `models:read` scope, used for LLM scoring
   - `GMAIL_APP_PASSWORD` / `NOTIFY_EMAIL` — for high-score alerts and the weekly digest email
   - `PROFILE_PRIVATE_B64` — your real candidate profile, kept out of the public repo.
     Copy `scraper/profile.py` to `scraper/profile_private.py` (gitignored), fill in your
     details, then store it base64-encoded:
     ```bash
     base64 -i scraper/profile_private.py   # paste output into the secret
     ```
     Without it, scoring falls back to the template profile in `scraper/profile.py`.

3. **Run locally:**
   ```bash
   python -m scraper.main
   ```

4. **View dashboard:**
   Open `dashboard/index.html` in a browser (or use the GitHub Pages URL after deployment).

## Structure

```
job-search-agent/
├── scraper/
│   ├── main.py          # Pipeline entrypoint
│   ├── profile.py       # Candidate profile (customize this)
│   ├── db.py            # SQLite database layer
│   ├── scraper.py       # JobSpy-based LinkedIn/Indeed scraper
│   ├── companies.py     # Target company career page monitor
│   ├── connections.py   # LinkedIn connection URL generator
│   └── export.py        # JSON + CSV export
├── scorer/
│   └── scorer.py        # GitHub Models API scoring
├── dashboard/
│   ├── index.html       # Static dashboard (deployed to GitHub Pages)
│   └── template.html    # Jinja2 template
├── data/
│   ├── jobs.db          # SQLite database (gitignored)
│   ├── jobs.json        # Exported scored jobs (committed)
│   ├── stats.json       # Daily stats (committed)
│   └── feedback.json    # Feedback from dashboard (committed by user)
├── .github/
│   └── workflows/
│       └── daily-search.yml
└── requirements.txt
```

## Feedback Loop

1. Rate jobs on the dashboard (👍/👎) and add connection notes
2. Click "Export Feedback" to download `feedback.json`
3. Commit it to `data/feedback.json`
4. Next run will incorporate your preferences into scoring

## LinkedIn Connection Discovery

For each high-scoring job, the dashboard provides pre-built LinkedIn search URLs
filtered to your 1st and 2nd-degree connections at that company. No automated
people scraping — you click and search yourself in your own browser.
