"""
ingest_geolocation_api.py
--------------------------
ELT Bronze Layer – Ingest CSV data from the Google Apps Script
geolocation endpoint into the local SQL Server [bronze] schema.

The endpoint returns a raw CSV file (not JSON).
URL is read from: GEOLOCATION_API_URL in .env
"""

import os
import sys
import io
import time
import logging
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.db_connections import get_dest_engine, ensure_bronze_schema

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv()

BRONZE_SCHEMA = "bronze"
BRONZE_TABLE = "geolocation"
# SQL Server ODBC limit: 2100 parameters — safe_chunk computed at runtime

# Google Apps Script endpoint (returns CSV)
API_URL = os.getenv("GEOLOCATION_API_URL", "")


def fetch_geolocation_csv(api_url: str) -> pd.DataFrame:
    """Call the Google Apps Script endpoint and parse the CSV response."""
    log.info(f"    GET {api_url}")

    response = requests.get(
        api_url,
        timeout=120,          # GAS cold-start can be slow
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    log.info(f"    Response Content-Type: {content_type}")
    log.info(f"    Response size: {len(response.content):,} bytes")

    # Defensive check: if an error JSON was returned instead of CSV
    if "application/json" in content_type or response.content.strip().startswith(b"{"):
        raise ValueError(
            f"API returned JSON (likely an error) instead of CSV: {response.text[:300]}"
        )

    # Parse the CSV from the response bytes
    df = pd.read_csv(
        io.BytesIO(response.content),
        encoding="utf-8",
        low_memory=False,
    )
    log.info(f"    Parsed {len(df):,} rows × {len(df.columns)} columns.")
    return df


def run() -> None:
    log.info("=" * 60)
    log.info("Bronze Ingestion – Geolocation API (GAS) → SQL Server")
    log.info("=" * 60)

    if not API_URL:
        log.error("GEOLOCATION_API_URL is not set in .env – aborting.")
        sys.exit(1)

    dest_engine = get_dest_engine()
    ensure_bronze_schema(dest_engine)

    start = time.time()

    # ── 1. Fetch CSV data from GAS endpoint ────────────────────────────────
    log.info(f"  ↳ Fetching geolocation CSV from Google Apps Script …")
    try:
        df = fetch_geolocation_csv(API_URL)
    except Exception as exc:
        log.error(f"  ✗ Failed to fetch from API: {exc}")
        sys.exit(1)

    if df.empty:
        log.warning("  API returned 0 rows – nothing to load.")
        sys.exit(0)

    # ── 2. Add ingestion audit columns ─────────────────────────────────────
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "geolocation_gas_api"
    df["_api_url"] = API_URL

    # ── 3. Write to SQL Server bronze ──────────────────────────────────────
    # SQL Server ODBC limit: 2100 parameters per statement.
    # safe_chunk = floor(2000 / num_columns) avoids the limit.
    num_cols = len(df.columns)
    safe_chunk = max(1, 2000 // num_cols)
    log.info(f"  Writing to [BI_AI].[{BRONZE_SCHEMA}].[{BRONZE_TABLE}] (chunksize={safe_chunk}) …")
    with dest_engine.begin() as conn:
        conn.execute(
            text(
                f"IF OBJECT_ID('{BRONZE_SCHEMA}.{BRONZE_TABLE}', 'U') IS NOT NULL "
                f"DROP TABLE [{BRONZE_SCHEMA}].[{BRONZE_TABLE}]"
            )
        )

    df.to_sql(
        name=BRONZE_TABLE,
        schema=BRONZE_SCHEMA,
        con=dest_engine,
        if_exists="replace",
        index=False,
        chunksize=safe_chunk,
        method=None,  # SQLAlchemy executemany — avoids SQL Server 2100-param limit
    )

    elapsed = time.time() - start
    log.info(f"  ✓ Done – {len(df):,} rows loaded in {elapsed:.1f}s")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
