"""
One-time CSV import.

CSV columns observed in FilteredData - Sheet1 (1).csv:
First Name, Last Name, Email, Website, Company, City, Country,
Funding Date, Funding Amount (in USD), Funding Type, LinkedIn,
Industry, Description

Mapping:
  name        <- Company
  domain      <- Website (host extracted)
  ceo_email   <- Email
  role        <- "CEO"
  description <- Description (already present, skips enrichment for description)
"""
import csv
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import init_db, insert_company, get_conn


def extract_domain(url):
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return None


def load(csv_path):
    init_db()
    inserted = 0
    skipped = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("Email") or "").strip().lower()
            company = (row.get("Company") or "").strip()
            if not email or not company:
                skipped += 1
                continue
            domain = extract_domain(row.get("Website") or "")
            description = (row.get("Description") or "").strip() or None
            rid = insert_company(
                name=company,
                domain=domain,
                ceo_email=email,
                role="CEO",
                description=description,
            )
            if rid:
                inserted += 1
            else:
                skipped += 1
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
    print(f"Inserted: {inserted}  Skipped (dupes/blank): {skipped}  Total in DB: {total}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/prabhaskalyan/Downloads/FilteredData - Sheet1 (1).csv"
    load(path)
