-- =============================================================================
-- FILE    : gold_generate_dim_date.sql
-- LAYER   : Gold — Conformed Date Dimension
-- PURPOSE : Generates and populates gold.dim_date with a daily date spine
--           covering 2016-01-01 → 2020-12-31 plus sentinel rows.
-- AUTHOR  : ITI Grad Project
-- DATE    : 2026-05-12
--
-- EXECUTION: Run ONCE after gold_ddl_dimensions.sql.
--            Script is idempotent — TRUNCATE + INSERT.
--
-- SENTINEL ROWS (loaded first):
--   date_key = 19000101  →  '1900-01-01'  = "Unknown / Data Quality Gap"
--   date_key = 99991231  →  '9999-12-31'  = "Not Yet Occurred / Open"
--
-- DATE RANGE: 2016-01-01 to 2020-12-31
--   • Earliest Olist order data: ~2016-09
--   • Latest Olist order data:   ~2018-10
--   • Range includes 6-month margin on each end
--
-- HOW date_key WORKS:
--   date_key = YEAR * 10000 + MONTH * 100 + DAY
--   e.g. 2017-03-15  →  20170315
--   This makes it: (a) human-readable, (b) sortable as INT,
--                  (c) trivially derivable from any DATE column in ETL.
--
-- ETL USAGE — converting a source date to date_key:
--   ISNULL(
--       CAST(FORMAT(TRY_CAST(source_col AS DATE), 'yyyyMMdd') AS INT),
--       19000101   -- sentinel for NULL / unparseable dates
--   )
-- =============================================================================

-- Idempotent: insert only dates not already present.
-- NOTE: TRUNCATE cannot be used here because fact tables reference
--       dim_date via FK constraints. INSERT WHERE NOT EXISTS is safe
--       to run on a fresh table OR on a table already holding data.

-- ── Step 1: Insert sentinel rows ─────────────────────────────────────────────
-- These rows MUST be inserted first (before any fact row references them).
-- WHERE NOT EXISTS guard makes this safe to re-run.

INSERT INTO gold.dim_date (
    date_key, full_date,
    day_of_week_num, day_of_week_name, day_of_week_name_short,
    day_of_month, day_of_year,
    week_of_year,
    month_num, month_name, month_name_short,
    quarter_num, quarter_name,
    [year], year_month,
    is_weekend, is_holiday
)
SELECT v.*
FROM (VALUES
    -- Unknown / Data Quality Gap sentinel
    (19000101, CAST('1900-01-01' AS DATE),
     1, 'Unknown', 'Unk', 1, 1, 1,
     1, 'Unknown', 'Unk', 1, 'Q1',
     1900, '1900-01', 0, 0),
    -- Not Yet Occurred / Open sentinel
    (99991231, CAST('9999-12-31' AS DATE),
     1, 'Unknown', 'Unk', 31, 365, 52,
     12, 'Unknown', 'Unk', 4, 'Q4',
     9999, '9999-12', 0, 0)
) AS v (date_key, full_date,
        day_of_week_num, day_of_week_name, day_of_week_name_short,
        day_of_month, day_of_year, week_of_year,
        month_num, month_name, month_name_short,
        quarter_num, quarter_name,
        [year], year_month, is_weekend, is_holiday)
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_date dd WHERE dd.date_key = v.date_key
);

GO

-- ── Step 2: Generate the daily date spine 2016-01-01 → 2020-12-31 ────────────
-- Uses a recursive CTE to walk day by day through the range.
-- All date attributes are derived deterministically from full_date.

WITH date_spine AS (
    -- Anchor: first date in range
    SELECT CAST('2016-01-01' AS DATE) AS d
    UNION ALL
    -- Recursive: next day (stops at end of range)
    SELECT DATEADD(DAY, 1, d)
    FROM date_spine
    WHERE d < '2020-12-31'
)
INSERT INTO gold.dim_date (
    date_key,
    full_date,
    day_of_week_num,
    day_of_week_name,
    day_of_week_name_short,
    day_of_month,
    day_of_year,
    week_of_year,
    month_num,
    month_name,
    month_name_short,
    quarter_num,
    quarter_name,
    [year],
    year_month,
    is_weekend,
    is_holiday
)
SELECT
    -- date_key: YYYYMMDD integer
    CAST(FORMAT(d, 'yyyyMMdd') AS INT)              AS date_key,
    d                                               AS full_date,

    -- Day of week: ISO convention (1=Monday … 7=Sunday)
    -- DATEPART(dw) is session-dependent; use ISO-safe calculation:
    --   (DATEPART(weekday, d) + @@DATEFIRST - 2) % 7 + 1
    (DATEPART(weekday, d) + @@DATEFIRST - 2) % 7 + 1   AS day_of_week_num,
    DATENAME(weekday, d)                            AS day_of_week_name,
    LEFT(DATENAME(weekday, d), 3)                   AS day_of_week_name_short,

    DATEPART(day, d)                                AS day_of_month,
    DATEPART(dayofyear, d)                          AS day_of_year,

    -- ISO week number
    DATEPART(ISO_WEEK, d)                           AS week_of_year,

    DATEPART(month, d)                              AS month_num,
    DATENAME(month, d)                              AS month_name,
    LEFT(DATENAME(month, d), 3)                     AS month_name_short,

    DATEPART(quarter, d)                            AS quarter_num,
    'Q' + CAST(DATEPART(quarter, d) AS CHAR(1))    AS quarter_name,

    DATEPART(year, d)                               AS [year],
    FORMAT(d, 'yyyy-MM')                            AS year_month,

    -- Weekend flag: ISO day 6=Saturday, 7=Sunday
    CASE
        WHEN (DATEPART(weekday, d) + @@DATEFIRST - 2) % 7 + 1 IN (6, 7)
        THEN 1 ELSE 0
    END                                             AS is_weekend,

    -- Holiday flag: default 0; update separately for BR public holidays if needed
    0                                               AS is_holiday

FROM date_spine
-- Skip dates that are already present (idempotent re-run safety)
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_date dd
    WHERE dd.date_key = CAST(FORMAT(d, 'yyyyMMdd') AS INT)
)
OPTION (MAXRECURSION 5000);  -- 5 years * 366 = ~1830 rows

GO

-- ── Verification ──────────────────────────────────────────────────────────────
SELECT
    COUNT(*)            AS total_rows,
    MIN(full_date)      AS earliest_date,
    MAX(full_date)      AS latest_date,
    SUM(CASE WHEN date_key IN (19000101, 99991231) THEN 1 ELSE 0 END) AS sentinel_rows
FROM gold.dim_date;
GO
