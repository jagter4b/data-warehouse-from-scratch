"""
ingest_neon_postgres.py
-----------------------
ELT Bronze Layer – Ingest all 7 tables from Neon PostgreSQL
into the local SQL Server [bronze] schema AS-IS (no transformation).

Tables ingested:
  customers | orders | order_items | order_payments
  sellers   | products | product_category_name_translation
"""

import os
import sys
import time
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text

# ── Make parent dir importable when running as a script ──────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.db_connections import get_source_engine, get_dest_engine, ensure_bronze_schema

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
BRONZE_SCHEMA = "bronze"
# SQL Server ODBC caps at 2100 parameters per statement.
# Safe chunksize = floor(2100 / num_columns) — computed per-table at runtime.

# All 7 Neon tables to ingest (source name → destination table name)
TABLES = [
    "customers",
    "orders",
    "order_items",
    "order_payments",
    "sellers",
    "products",
    "product_category_name_translation",
]


def ingest_table(
    table_name: str,
    src_engine,
    dest_engine,
) -> None:
    """Pull a full table from Neon and load it into SQL Server bronze schema."""
    dest_table = f"{BRONZE_SCHEMA}.{table_name}"
    log.info(f"  ↳ Ingesting table: {table_name} → [{dest_table}]")

    start = time.time()

    # ── 1. Read from Neon Postgres ──────────────────────────────────────────
    log.info(f"    Reading from Neon PostgreSQL …")
    df = pd.read_sql_table(table_name, con=src_engine)
    row_count = len(df)
    log.info(f"    Fetched {row_count:,} rows, {len(df.columns)} columns.")

    if df.empty:
        log.warning(f"    Table '{table_name}' returned 0 rows – skipping write.")
        return

    # ── 2. Add ingestion audit columns ─────────────────────────────────────
    df["_ingested_at"] = datetime.utcnow()
    df["_source"] = "neon_postgres"

    # ── 3. Write to SQL Server (full replace – ELT bronze = raw snapshot) ──
    # SQL Server ODBC limit: 2100 parameters per batch.
    # Compute a safe chunksize so rows × cols < 2100.
    num_cols = len(df.columns)
    safe_chunk = max(1, 2000 // num_cols)
    log.info(f"    Writing to SQL Server [BI_AI].[{dest_table}] (chunksize={safe_chunk}) …")
    with dest_engine.begin() as conn:
        # Drop and recreate the table for idempotent full-loads
        conn.execute(text(f"IF OBJECT_ID('{dest_table}', 'U') IS NOT NULL DROP TABLE [{BRONZE_SCHEMA}].[{table_name}]"))

    df.to_sql(
        name=table_name,
        schema=BRONZE_SCHEMA,
        con=dest_engine,
        if_exists="replace",
        index=False,
        chunksize=safe_chunk,
        method=None,  # Use SQLAlchemy row-by-row executemany – avoids 2100-param limit
    )

    elapsed = time.time() - start
    log.info(f"    ✓ Done – {row_count:,} rows loaded in {elapsed:.1f}s")


def run() -> None:
    log.info("=" * 60)
    log.info("Bronze Ingestion – Neon PostgreSQL → SQL Server")
    log.info("=" * 60)

    src_engine = get_source_engine()
    dest_engine = get_dest_engine()

    # Ensure bronze schema exists
    ensure_bronze_schema(dest_engine)

    errors = []
    for table in TABLES:
        try:
            ingest_table(table, src_engine, dest_engine)
        except Exception as exc:
            log.error(f"  ✗ FAILED for table '{table}': {exc}")
            errors.append((table, str(exc)))

    log.info("=" * 60)
    if errors:
        log.error(f"Ingestion completed WITH ERRORS ({len(errors)} table(s) failed):")
        for tbl, err in errors:
            log.error(f"  - {tbl}: {err}")
        sys.exit(1)
    else:
        log.info(f"All {len(TABLES)} tables ingested successfully.")


if __name__ == "__main__":
    run()
