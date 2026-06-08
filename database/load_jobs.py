"""
database/load_jobs.py
Loads all job postings from CSV into Neon PostgreSQL.
Run once locally — never push the CSV to GitHub.

Usage:
    python database/load_jobs.py
"""

import os
import math
import pandas as pd
import psycopg2
import psycopg2.extras
from datetime import date
from dotenv import load_dotenv

load_dotenv()

CSV_PATH     = r"C:\Users\Abdulmohsen Alghamdi\OneDrive\Desktop\Learning\ML & DL\Agentic AI\SDA\Project\Project Data\saudi_job_market_final.csv"
DATABASE_URL = os.getenv("DATABASE_URL")
BATCH_SIZE   = 500


def clean_str(val) -> str | None:
    """Any value → string or None."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    if s.lower() in ("nan", "nat", "none", "null", ""):
        return None
    return s


def clean_float(val) -> float | None:
    """Any value → float or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f):
            return None
        return f
    except Exception:
        return None


def clean_date(val) -> date | None:
    """Any value → date or None."""
    s = clean_str(val)
    if s is None:
        return None
    try:
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.isnull(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def make_row(r) -> tuple:
    """Convert a DataFrame row into a clean tuple for insertion."""
    return (
        clean_str(r["company_name"]),
        clean_str(r["job_title"]),
        clean_str(r["description_text"]),
        clean_str(r["location"]),
        clean_str(r["country"]),
        clean_date(r["date_posted_parsed"]),        # date or None
        clean_float(r["company_rating"]),            # float or None
        clean_str(r["company_link"]),
        clean_str(r["domain"]),
        clean_str(r["apply_link"]),
        clean_str(r["url"]),
        clean_str(r["input_discovery_input_domain"]),
        clean_str(r["input_discovery_input_keyword_search"]),
    )


def load_jobs():
    print("Reading CSV...")
    df = pd.read_csv(CSV_PATH, low_memory=False, dtype=str)  # read EVERYTHING as string
    print(f"Total rows in CSV: {len(df):,}")

    insert_sql = """
        INSERT INTO job_postings (
            company_name, job_title, description_text,
            location, country, date_posted_parsed,
            company_rating, company_link, domain,
            apply_link, url,
            input_discovery_input_domain,
            input_discovery_input_keyword_search
        ) VALUES %s
        ON CONFLICT DO NOTHING
    """

    # Build all rows upfront — every value cleaned before touching the DB
    print("Cleaning data...")
    rows = [make_row(r) for _, r in df.iterrows()]
    print(f"Rows ready to insert: {len(rows):,}")

    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()

    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        psycopg2.extras.execute_values(cur, insert_sql, batch)
        conn.commit()
        total += len(batch)
        print(f"  Inserted {total:,} / {len(rows):,} rows...")

    cur.close()
    conn.close()
    print(f"\nDone! {total:,} job postings loaded into Neon.")


if __name__ == "__main__":
    load_jobs()