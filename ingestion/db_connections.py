"""
db_connections.py
-----------------
Centralised connection helpers for:
  - Source : Neon PostgreSQL (serverless)
  - Destination: Local SQL Server (Windows Auth / Trusted Connection)
"""

import os
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy import text
import pyodbc

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()


# ── SOURCE: Neon PostgreSQL ───────────────────────────────────────────────────
def get_source_engine() -> sqlalchemy.Engine:
    """Return a SQLAlchemy engine connected to Neon PostgreSQL."""
    host = os.getenv("SOURCE_DB_HOST")
    port = os.getenv("SOURCE_DB_PORT", "5432")
    dbname = os.getenv("SOURCE_DB_NAME")
    user = os.getenv("SOURCE_DB_USER")
    password = os.getenv("SOURCE_DB_PASSWORD")
    ssl_mode = os.getenv("SOURCE_DB_SSL_MODE", "require")

    url = (
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
        f"?sslmode={ssl_mode}"
    )
    engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    return engine


# ── DESTINATION: Local SQL Server ─────────────────────────────────────────────
def get_dest_engine() -> sqlalchemy.Engine:
    """Return a SQLAlchemy engine connected to the local SQL Server instance.

    Uses Windows Authentication (Trusted Connection) – no password required.
    """
    server = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    dbname = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    trusted = os.getenv("DEST_DB_TRUSTED_CONNECTION", "yes").lower()

    # Build ODBC connection string
    if trusted == "yes":
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server},{port};"
            f"DATABASE={dbname};"
            f"Trusted_Connection=yes;"
        )
    else:
        user = os.getenv("DEST_DB_USER", "")
        password = os.getenv("DEST_DB_PASSWORD", "")
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server},{port};"
            f"DATABASE={dbname};"
            f"UID={user};PWD={password};"
        )

    connection_url = sqlalchemy.engine.URL.create(
        "mssql+pyodbc",
        query={"odbc_connect": conn_str},
    )
    engine = sqlalchemy.create_engine(connection_url, pool_pre_ping=True)
    return engine


def ensure_bronze_schema(dest_engine: sqlalchemy.Engine) -> None:
    """Create the [bronze] schema in the destination database if it doesn't exist."""
    with dest_engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.schemas WHERE name = 'bronze'
            )
            BEGIN
                EXEC('CREATE SCHEMA bronze')
            END
        """))
    print("[INFO] Schema 'bronze' is ready.")
