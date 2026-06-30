"""
LinkedIn connection URL generator.
Generates pre-built search URLs for 1st and 2nd-degree connections at a company.
No automated scraping — Ben clicks these manually in his own browser.
"""

import urllib.parse


def make_linkedin_urls(company: str) -> dict[str, str]:
    """
    Generate LinkedIn people search URLs filtered to 1st/2nd degree connections.
    
    Args:
        company: Company name as it appears on LinkedIn
    
    Returns:
        dict with keys: first_degree, second_degree, combined, company_page
    """
    encoded_company = urllib.parse.quote(company)
    base = "https://www.linkedin.com/search/results/people/"

    first_degree = (
        f"{base}?keywords={encoded_company}"
        f"&network=%5B%22F%22%5D"
    )
    second_degree = (
        f"{base}?keywords={encoded_company}"
        f"&network=%5B%22S%22%5D"
    )
    combined = (
        f"{base}?keywords={encoded_company}"
        f"&network=%5B%22F%22%2C%22S%22%5D"
    )
    # LinkedIn company search (finds the company page)
    company_search = (
        f"https://www.linkedin.com/search/results/companies/"
        f"?keywords={encoded_company}"
    )

    return {
        "first_degree": first_degree,
        "second_degree": second_degree,
        "combined": combined,
        "company_search": company_search,
    }


def enrich_jobs_with_connections(jobs: list[dict]) -> list[dict]:
    """Add LinkedIn connection URLs to each job dict."""
    for job in jobs:
        company = job.get("company", "")
        if company:
            job["linkedin_urls"] = make_linkedin_urls(company)
        else:
            job["linkedin_urls"] = {}
    return jobs
