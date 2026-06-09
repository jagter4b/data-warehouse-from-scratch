"""
database.py — SQL Server Connection & Query Execution
──────────────────────────────────────────────────────
Manages connection lifecycle, verifies connectivity,
and runs validated SQL queries against SQL Server.
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any

import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ── Connection builder ───────────────────────────────────────────────────────

def build_connection_string(
    config: Dict[str, Any],
    driver: str = "ODBC Driver 17 for SQL Server",
) -> str:
    """
    Build a SQLAlchemy connection string for SQL Server.

    Supports:
        - Windows Authentication  (trusted_connection=yes)
        - SQL Server Authentication (username + password)
        - Optional instance name  (SERVER\\INSTANCE)
    """
    server = config["server"].strip()
    instance = config.get("instance", "").strip()
    database = config["database"].strip()
    auth_type = config.get("auth_type", "windows")

    # Only append \instance if explicitly provided
    host = f"{server}\\{instance}" if instance else server
    driver_str = driver.replace(" ", "+")

    if auth_type == "windows":
        conn_str = (
            f"mssql+pyodbc://{host}/{database}"
            f"?driver={driver_str}"
            "&trusted_connection=yes"
            "&TrustServerCertificate=yes"
        )
    else:
        username = config["username"]
        password = config["password"]
        conn_str = (
            f"mssql+pyodbc://{username}:{password}@{host}/{database}"
            f"?driver={driver_str}"
            "&TrustServerCertificate=yes"
        )

    logger.debug("Connection string built for driver: %s, host: %s", driver, host)
    return conn_str


def _get_available_drivers() -> list:
    """Return all SQL Server ODBC drivers installed on this machine."""
    try:
        import pyodbc
        return [d for d in pyodbc.drivers() if "SQL Server" in d]
    except Exception:
        return []


def create_db_engine(config: Dict[str, Any]) -> Tuple[Optional[Engine], Optional[str]]:
    """
    Create a SQLAlchemy engine and verify connectivity.
    Automatically tries all available ODBC SQL Server drivers.

    Returns:
        (engine, None)          on success
        (None, error_message)   on failure
    """
    available = _get_available_drivers()

    if not available:
        return None, (
            "❌ **No SQL Server ODBC driver found.**\n\n"
            "Install **ODBC Driver 17 for SQL Server** from:\n"
            "https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server"
        )

    # Try preferred drivers first
    preferred = ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"]
    drivers_to_try = [d for d in preferred if d in available]
    drivers_to_try += [d for d in available if d not in drivers_to_try]

    last_error = ""
    for driver in drivers_to_try:
        try:
            conn_str = build_connection_string(config, driver=driver)
            engine = create_engine(
                conn_str,
                pool_pre_ping=True,
                pool_recycle=1800,
                connect_args={"timeout": 10},
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected successfully using driver: %s", driver)
            return engine, None

        except sqlalchemy.exc.OperationalError as e:
            last_error = str(e.orig) if e.orig else str(e)
            logger.warning("Driver %s failed: %s", driver, last_error)
        except sqlalchemy.exc.InterfaceError as e:
            last_error = str(e.orig) if e.orig else str(e)
            logger.warning("Driver %s interface error: %s", driver, last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning("Driver %s unexpected error: %s", driver, e)

    # All drivers failed — return helpful diagnostic message
    server = config.get("server", "")
    instance = config.get("instance", "")
    host_display = f"{server}\\{instance}" if instance else server
    auth = config.get("auth_type", "windows")

    hint = (
        f"**Could not connect to `{host_display}` / `{config.get('database','')}`**\n\n"
        f"Auth mode: {'Windows Authentication' if auth == 'windows' else 'SQL Authentication'}  \n"
        f"Drivers tried: `{'`, `'.join(drivers_to_try)}`\n\n"
        "**Checklist:**\n"
        "- ✅ Server Name must be exactly as shown in SSMS (e.g. `DESKTOP-UCKMQTL`)\n"
        "- ✅ Leave **Instance** blank unless you use a named instance (e.g. `SQLEXPRESS`)\n"
        "- ✅ SQL Server service must be running\n"
        "- ✅ TCP/IP must be enabled in SQL Server Configuration Manager\n"
        "- ✅ SQL Server Browser service should be running\n\n"
        f"Last error: `{last_error}`"
    )
    return None, hint


# ── Query execution ──────────────────────────────────────────────────────────

def run_query(
    engine: Engine,
    sql: str,
    timeout: int = 60,
) -> Tuple[Optional[pd.DataFrame], float, Optional[str]]:
    """
    Execute a validated SQL query and return the results.

    Returns:
        (DataFrame, elapsed_seconds, None)          on success
        (None,      elapsed_seconds, error_message) on failure
    """
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text(f"SET QUERY_GOVERNOR_COST_LIMIT {timeout * 1000}"))
            df = pd.read_sql(text(sql), conn)
        elapsed = time.perf_counter() - start
        logger.info("Query executed in %.3fs — %d rows returned.", elapsed, len(df))
        return df, elapsed, None

    except sqlalchemy.exc.OperationalError as e:
        elapsed = time.perf_counter() - start
        msg = str(e.orig) if e.orig else str(e)
        logger.error("Query operational error: %s", msg)
        return None, elapsed, f"SQL Server error: {msg}"
    except sqlalchemy.exc.ProgrammingError as e:
        elapsed = time.perf_counter() - start
        msg = str(e.orig) if e.orig else str(e)
        logger.error("Query programming error: %s", msg)
        return None, elapsed, f"SQL syntax/schema error: {msg}"
    except Exception as e:
        elapsed = time.perf_counter() - start
        logger.error("Unexpected query error: %s", e)
        return None, elapsed, f"Unexpected error: {e}"


def test_connection(engine: Engine) -> bool:
    """Quick connectivity check — returns True if database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
