"""
ingest_google_drive.py
----------------------
ELT Bronze Layer – Ingest CSV files stored in Google Drive
into the local SQL Server [bronze] schema AS-IS (no transformation).

Files ingested:
  - closed_deals                  (CLOSED_DEALS_FILE_ID)
  - marketing_qualified_leads     (MQL_FILE_ID)
  - order_reviews                 (ORDER_REVIEWS_FILE_ID)  ← Google Sheet

Google Drive files are downloaded via the public export URL:
  https://drive.google.com/uc?export=download&id=<FILE_ID>

Google Sheets files use:
  https://docs.google.com/spreadsheets/d/<FILE_ID>/export?format=csv

NOTE: Files must be publicly shared (anyone with the link can view).
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
# SQL Server ODBC limit: 2100 parameters — safe_chunk computed per-table at runtime.

# ── File registry ─────────────────────────────────────────────────────────────
# Maps: bronze table name → (Google Drive File ID, is_google_sheet)
# is_google_sheet=True  → use Sheets export URL (/export?format=csv)
# is_google_sheet=False → use Drive download URL (uc?export=download)
DRIVE_FILES = {
    "closed_deals": (os.getenv("CLOSED_DEALS_FILE_ID", ""), False),
    "marketing_qualified_leads": (os.getenv("MQL_FILE_ID", ""), False),
    "order_reviews": (os.getenv("ORDER_REVIEWS_FILE_ID", ""), True),  # Google Sheet
}

SHEETS_EXPORT_URL = "https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
DRIVE_EXPORT_URL = "https://drive.google.com/uc?export=download&id={file_id}"


def build_download_url(file_id: str, is_sheets: bool = False) -> str:
    """Return a direct CSV download URL for a Google Drive or Sheets file."""
    if is_sheets:
        return SHEETS_EXPORT_URL.format(file_id=file_id)
    return DRIVE_EXPORT_URL.format(file_id=file_id)


def download_csv(file_id: str, table_name: str, is_sheets: bool = False) -> pd.DataFrame:
    """Download a CSV from Google Drive/Sheets and return it as a DataFrame."""
    url = build_download_url(file_id, is_sheets)
    log.info(f"    Downloading: {url}")

    session = requests.Session()
    response = session.get(url, stream=True, timeout=120)

    # Google Drive shows a virus-scan warning for large files —
    # detect the confirm token cookie and re-fetch.
    if "Content-Disposition" not in response.headers and not is_sheets:
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                confirm_url = url + f"&confirm={value}"
                log.info("    Large file — re-fetching with confirm token …")
                response = session.get(confirm_url, stream=True, timeout=120)
                break

    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    content = response.content

    # If Drive returned HTML (e.g. virus-scan page), fall back to Sheets export URL
    if not is_sheets and "text/html" in content_type and b"<html" in content[:200].lower():
        sheets_url = SHEETS_EXPORT_URL.format(file_id=file_id)
        log.info(f"    HTML detected — retrying as Google Sheet: {sheets_url}")
        response = session.get(sheets_url, timeout=120)
        response.raise_for_status()
        content = response.content

    df = pd.read_csv(io.BytesIO(content), encoding="utf-8", low_memory=False)
    log.info(f"    Fetched {len(df):,} rows, {len(df.columns)} columns.")
    return df


def ingest_drive_file(
    table_name: str,
    file_id: str,
    is_sheets: bool,
    dest_engine,
) -> None:
    """Download a Google Drive/Sheets CSV and load it into SQL Server bronze schema."""
    log.info(f"  ↳ Ingesting: '{table_name}' (ID={file_id}, is_sheet={is_sheets})")
    start = time.time()

    if not file_id:
        log.error(f"    No FILE_ID configured for '{table_name}' — skipping.")
        return

    # ── 1. Download CSV ─────────────────────────────────────────────────────
    df = download_csv(file_id, table_name, is_sheets)

    if df.empty:
        log.warning(f"    '{table_name}' returned 0 rows — skipping write.")
        return

    # ── 2. Add ingestion audit columns ─────────────────────────────────────
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "google_drive"
    df["_drive_file_id"] = file_id

    # ── 3. Write to SQL Server ──────────────────────────────────────────────
    # SQL Server ODBC limit: 2100 parameters per statement.
    # safe_chunk = floor(2000 / num_columns) avoids the limit.
    num_cols = len(df.columns)
    safe_chunk = max(1, 2000 // num_cols)
    log.info(f"    Writing to [BI_AI].[{BRONZE_SCHEMA}].[{table_name}] (chunksize={safe_chunk}) …")

    with dest_engine.begin() as conn:
        conn.execute(
            text(
                f"IF OBJECT_ID('{BRONZE_SCHEMA}.{table_name}', 'U') IS NOT NULL "
                f"DROP TABLE [{BRONZE_SCHEMA}].[{table_name}]"
            )
        )

    df.to_sql(
        name=table_name,
        schema=BRONZE_SCHEMA,
        con=dest_engine,
        if_exists="replace",
        index=False,
        chunksize=safe_chunk,
        method=None,  # SQLAlchemy executemany — avoids 2100-param limit
    )

    elapsed = time.time() - start
    log.info(f"    ✓ Done — {len(df):,} rows loaded in {elapsed:.1f}s")


def run() -> None:
    log.info("=" * 60)
    log.info("Bronze Ingestion – Google Drive → SQL Server")
    log.info("=" * 60)

    dest_engine = get_dest_engine()
    ensure_bronze_schema(dest_engine)

    errors = []
    for table_name, (file_id, is_sheets) in DRIVE_FILES.items():
        try:
            ingest_drive_file(table_name, file_id, is_sheets, dest_engine)
        except Exception as exc:
            log.error(f"  ✗ FAILED for '{table_name}': {exc}")
            errors.append((table_name, str(exc)))

    log.info("=" * 60)
    if errors:
        log.error(f"Ingestion completed WITH ERRORS ({len(errors)} file(s) failed):")
        for tbl, err in errors:
            log.error(f"  - {tbl}: {err}")
        sys.exit(1)
    else:
        log.info(f"All {len(DRIVE_FILES)} Drive files ingested successfully.")


if __name__ == "__main__":
    run()
