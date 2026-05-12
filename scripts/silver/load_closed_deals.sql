/* ============================================================
   load_closed_deals.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for closed_deals table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_closed_deals
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_closed_deals ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.closed_deals', 'U') IS NOT NULL
            DROP TABLE silver.closed_deals;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY mql_id        -- one deal per lead
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.closed_deals
        )
        SELECT
            -- Keys
            LTRIM(RTRIM(d.mql_id))                                              AS mql_id,
            LTRIM(RTRIM(d.seller_id))                                           AS seller_id,   -- bridge to e-commerce

            -- Internal Olist employee IDs (no dimension table for these)
            ISNULL(LTRIM(RTRIM(d.sdr_id)), 'UNKNOWN')                           AS sdr_id,
            ISNULL(LTRIM(RTRIM(d.sr_id)),  'UNKNOWN')                           AS sr_id,

            -- Won date: varchar datetime → DATE, NULL → '1900-01-01'
            ISNULL(TRY_CAST(d.won_date AS DATE), '1900-01-01')                  AS won_date,

            -- Business segment: snake_case → Title Case via CROSS APPLY (see below)
            ISNULL(seg.segment_title_case, 'Not Specified')                     AS business_segment,

            -- Lead type: controlled vocabulary
            CASE LOWER(LTRIM(RTRIM(d.lead_type)))
                WHEN 'online_big'    THEN 'Online Big'
                WHEN 'online_medium' THEN 'Online Medium'
                WHEN 'online_small'  THEN 'Online Small'
                WHEN 'industry'      THEN 'Industry'
                WHEN 'offline'       THEN 'Offline'
                ELSE                      'Not Specified'
            END                                                                 AS lead_type,

            -- Behavioural archetype: controlled vocabulary
            CASE LOWER(LTRIM(RTRIM(d.lead_behaviour_profile)))
                WHEN 'cat'   THEN 'Cat'
                WHEN 'eagle' THEN 'Eagle'
                WHEN 'wolf'  THEN 'Wolf'
                WHEN 'shark' THEN 'Shark'
                ELSE              'Not Specified'   -- catches NULLs + unexpected values
            END                                                                 AS lead_behaviour_profile,

            -- Bit flags: NULL → 0 (not declared = treat as false)
            ISNULL(CAST(d.has_company AS TINYINT), 0)                           AS has_company,
            ISNULL(CAST(d.has_gtin    AS TINYINT), 0)                           AS has_gtin,

            -- Average stock: varchar range ("100-500") — not a number, keep as text
            ISNULL(LTRIM(RTRIM(d.average_stock)), 'Not Specified')              AS average_stock,

            -- Business type: controlled vocabulary
            CASE LOWER(LTRIM(RTRIM(d.business_type)))
                WHEN 'reseller'     THEN 'Reseller'
                WHEN 'manufacturer' THEN 'Manufacturer'
                WHEN 'others'       THEN 'Other'
                ELSE                     'Not Specified'
            END                                                                 AS business_type,

            -- Self-reported numbers: float → DECIMAL(10,2), NULL → 0.00
            ISNULL(CAST(d.declared_product_catalog_size AS DECIMAL(10,2)), 0.00) AS declared_product_catalog_size,
            ISNULL(CAST(d.declared_monthly_revenue      AS DECIMAL(10,2)), 0.00) AS declared_monthly_revenue,

            -- Metadata (_drive_file_id dropped — bronze ingestion artifact)
            d._ingested_at,
            d._source,
            GETDATE()                                                           AS _processed_at

        INTO silver.closed_deals

        FROM deduped d

        -- Business segment: snake_case → Title Case
        -- Requires SQL Server 2022+ for STRING_SPLIT with ordinal
        CROSS APPLY (
            SELECT
                NULLIF(
                    STRING_AGG(
                        UPPER(LEFT(value, 1)) + LOWER(SUBSTRING(value, 2, LEN(value))),
                        ' '
                    ) WITHIN GROUP (ORDER BY ordinal),
                '') AS segment_title_case
            FROM STRING_SPLIT(
                LOWER(REPLACE(ISNULL(LTRIM(RTRIM(d.business_segment)), ''), '_', ' ')),
                ' ', 1
            )
            WHERE LTRIM(value) <> ''
        ) AS seg

        WHERE d.rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.closed_deals loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_closed_deals: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
