"""
schema.py — Automatic Schema Discovery (gold schema only)
───────────────────────────────────────────────────────────
Reads all tables, views, columns, primary keys, and foreign keys
from the 'gold' schema of the connected SQL Server database and
builds a rich schema context for the AI service.
"""

import logging
from typing import Dict, List, Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ── Target schema ─────────────────────────────────────────────────────────────
TARGET_SCHEMA = "gold"

# ── SQL fragments (filtered to gold schema) ───────────────────────────────────

_TABLES_SQL = f"""
SELECT
    t.TABLE_SCHEMA   AS schema_name,
    t.TABLE_NAME     AS table_name,
    t.TABLE_TYPE     AS table_type
FROM INFORMATION_SCHEMA.TABLES t
WHERE t.TABLE_SCHEMA = '{TARGET_SCHEMA}'
ORDER BY t.TABLE_NAME;
"""

_COLUMNS_SQL = f"""
SELECT
    c.TABLE_SCHEMA        AS schema_name,
    c.TABLE_NAME          AS table_name,
    c.COLUMN_NAME         AS column_name,
    c.DATA_TYPE           AS data_type,
    c.CHARACTER_MAXIMUM_LENGTH AS max_length,
    c.IS_NULLABLE         AS is_nullable,
    c.COLUMN_DEFAULT      AS default_value,
    c.ORDINAL_POSITION    AS ordinal
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_SCHEMA = '{TARGET_SCHEMA}'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
"""

_PK_SQL = f"""
SELECT
    tc.TABLE_SCHEMA  AS schema_name,
    tc.TABLE_NAME    AS table_name,
    kcu.COLUMN_NAME  AS column_name
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
   AND tc.TABLE_SCHEMA    = kcu.TABLE_SCHEMA
WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
  AND tc.TABLE_SCHEMA = '{TARGET_SCHEMA}'
ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION;
"""

_FK_SQL = f"""
SELECT
    fk.name                                                    AS fk_name,
    OBJECT_SCHEMA_NAME(fk.parent_object_id)                    AS from_schema,
    OBJECT_NAME(fk.parent_object_id)                           AS from_table,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id)      AS from_column,
    OBJECT_SCHEMA_NAME(fk.referenced_object_id)                AS to_schema,
    OBJECT_NAME(fk.referenced_object_id)                       AS to_table,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS to_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc
    ON fk.object_id = fkc.constraint_object_id
WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = '{TARGET_SCHEMA}'
ORDER BY from_table;
"""

_ROW_COUNTS_SQL = f"""
SELECT
    s.name   AS schema_name,
    t.name   AS table_name,
    p.rows   AS row_count
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id
WHERE s.name = '{TARGET_SCHEMA}'
  AND p.index_id IN (0, 1)
ORDER BY t.name;
"""


# ── Discovery ─────────────────────────────────────────────────────────────────

def discover_schema(engine: Engine) -> Dict[str, Any]:
    """
    Run all discovery queries against the gold schema and return a
    unified schema dict.

    Structure:
    {
      "tables":    [ {schema_name, table_name, table_type, row_count}, ... ],
      "columns":   { "gold.table": [ {column_name, data_type, ...}, ... ] },
      "pk":        { "gold.table": [ col, ... ] },
      "fk":        [ {from_schema, from_table, from_col, to_schema, ...}, ... ],
    }
    """
    schema: Dict[str, Any] = {
        "tables": [],
        "columns": {},
        "pk": {},
        "fk": [],
        "target_schema": TARGET_SCHEMA,
    }

    try:
        with engine.connect() as conn:
            # Tables & views
            tables_df = pd.read_sql(text(_TABLES_SQL), conn)
            schema["tables"] = tables_df.to_dict(orient="records")

            # Columns
            cols_df = pd.read_sql(text(_COLUMNS_SQL), conn)
            for (sch, tbl), grp in cols_df.groupby(["schema_name", "table_name"]):
                key = f"{sch}.{tbl}"
                schema["columns"][key] = grp[
                    ["column_name", "data_type", "max_length", "is_nullable", "default_value"]
                ].to_dict(orient="records")

            # Primary keys
            pk_df = pd.read_sql(text(_PK_SQL), conn)
            for (sch, tbl), grp in pk_df.groupby(["schema_name", "table_name"]):
                key = f"{sch}.{tbl}"
                schema["pk"][key] = grp["column_name"].tolist()

            # Foreign keys
            try:
                fk_df = pd.read_sql(text(_FK_SQL), conn)
                schema["fk"] = fk_df.to_dict(orient="records")
            except Exception as e:
                logger.warning("FK discovery failed (non-critical): %s", e)
                schema["fk"] = []

            # Row counts (best effort)
            try:
                rc_df = pd.read_sql(text(_ROW_COUNTS_SQL), conn)
                rc_map = {
                    f"{r.schema_name}.{r.table_name}": r.row_count
                    for r in rc_df.itertuples()
                }
                for tbl in schema["tables"]:
                    key = f"{tbl['schema_name']}.{tbl['table_name']}"
                    tbl["row_count"] = rc_map.get(key)
            except Exception as e:
                logger.warning("Row count discovery failed (non-critical): %s", e)

        logger.info(
            "Gold schema discovered: %d objects, %d FK relationships.",
            len(schema["tables"]),
            len(schema["fk"]),
        )
        return schema

    except Exception as e:
        logger.error("Schema discovery failed: %s", e)
        raise


def build_schema_context(schema: Dict[str, Any]) -> str:
    """
    Convert the gold schema dict into a compact text block
    that is injected into the AI system prompt.
    """
    lines: List[str] = []
    lines.append(f"=== GOLD SCHEMA (gold.*) ===\n")
    lines.append("NOTE: Always prefix table names with 'gold.' in every query.\n")

    pk_map = schema.get("pk", {})
    cols_map = schema.get("columns", {})

    for tbl in schema.get("tables", []):
        sch = tbl["schema_name"]
        name = tbl["table_name"]
        ttype = tbl["table_type"]
        row_count = tbl.get("row_count")

        header = f"[{ttype}] gold.{name}"
        if row_count is not None:
            header += f"  ({row_count:,} rows)"
        lines.append(header)

        key = f"{sch}.{name}"
        pks = pk_map.get(key, [])
        cols = cols_map.get(key, [])

        for col in cols:
            col_name = col["column_name"]
            dtype = col["data_type"]
            nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
            pk_marker = " [PK]" if col_name in pks else ""
            lines.append(f"    {col_name}  {dtype}  {nullable}{pk_marker}")

        lines.append("")  # blank separator

    # Foreign key relationships
    fk_list = schema.get("fk", [])
    if fk_list:
        lines.append("=== RELATIONSHIPS ===")
        for fk in fk_list:
            lines.append(
                f"  gold.{fk['from_table']}.{fk['from_column']}"
                f"  →  gold.{fk['to_table']}.{fk['to_column']}"
            )

    return "\n".join(lines)
