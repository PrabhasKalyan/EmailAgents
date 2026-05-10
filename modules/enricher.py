"""
Per-domain enrichment: 1-line description + 1 recent news headline.

Cached in DB (companies.description / news_headline). If a row already has
a description we keep it and only fetch news. Silent-fail on timeouts.
"""
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import (
    companies_needing_enrichment,
    update_company_enrichment,
    get_company,
)

TIMEOUT = 8
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def scrape_homepage(domain):
    if not domain:
        return None
    url = f"https://{domain}"
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        if r.status_code >= 400:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", attrs={"name": "description"})
        if not meta:
            meta = soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):
            return _clean(meta["content"])
        title = soup.find("title")
        if title and title.text.strip():
            return _clean(title.text)
        p = soup.find("p")
        if p and p.text.strip():
            return _clean(p.text)
    except Exception:
        return None
    return None


def fetch_news_headline(company_name):
    """Most recent news headline (last ~30 days) via DuckDuckGo. Returns None on failure."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS(timeout=TIMEOUT) as ddgs:
            results = list(ddgs.news(company_name, timelimit="m", max_results=3))
        if not results:
            return None
        title = results[0].get("title")
        return _clean(title) if title else None
    except Exception:
        return None


def _clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:300] if text else None


def enrich_company(company_id):
    c = get_company(company_id)
    if not c:
        return None
    description = c.get("description")
    if not description:
        description = scrape_homepage(c.get("domain"))
    news = c.get("news_headline") or fetch_news_headline(c["name"])
    update_company_enrichment(company_id, description, news)
    return {"description": description, "news_headline": news}


def enrich_batch(limit=None, sleep_between=0.5):
    rows = companies_needing_enrichment(limit=limit)
    print(f"Enriching {len(rows)} companies")
    for i, c in enumerate(rows, 1):
        result = enrich_company(c["id"])
        desc_ok = "Y" if result and result.get("description") else "N"
        news_ok = "Y" if result and result.get("news_headline") else "N"
        print(f"[{i}/{len(rows)}] {c['name']} desc={desc_ok} news={news_ok}")
        time.sleep(sleep_between)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    enrich_batch(limit=n)
