/* ============================================================
   gold_load_fact_marketing_funnel.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver → gold.fact_marketing_funnel
   Strategy : TRUNCATE + INSERT (idempotent full reload)
   Grain    : One row per CLOSED DEAL (converted MQL)

   SOURCE TABLES:
     silver.closed_deals             → primary source (one row per deal)
     silver.marketing_qualified_leads → first_contact_date for the date key

   DIMENSION LOOKUPS:
     dim_seller            (seller_id_bk → seller_sk)
     dim_marketing_channel (mql_id_bk    → mql_channel_sk)
     dim_date              (YYYYMMDD integer key)

   NOTE: This fact only contains CLOSED DEALS.
     MQLs that did not convert are in dim_marketing_channel only.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_fact_marketing_funnel
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_fact_marketing_funnel ...';

        TRUNCATE TABLE gold.fact_marketing_funnel;

        INSERT INTO gold.fact_marketing_funnel (
            first_contact_date_key,
            won_date_key,
            seller_sk,
            mql_channel_sk,
            mql_id_bk,
            sdr_id_bk,
            sr_id_bk,
            days_to_close,
            declared_monthly_revenue,
            declared_product_catalog_size
        )
        SELECT
            -- ── Date Keys ─────────────────────────────────────────────────────
            -- first_contact_date comes from silver.marketing_qualified_leads
            ISNULL(
                CAST(CONVERT(VARCHAR(8), mql.first_contact_date, 112) AS INT),
                19000101
            )                               AS first_contact_date_key,

            -- won_date comes from silver.closed_deals
            ISNULL(
                CAST(CONVERT(VARCHAR(8), cd.won_date, 112) AS INT),
                19000101
            )                               AS won_date_key,

            -- ── Dimension Lookups ─────────────────────────────────────────────
            ISNULL(ds.seller_sk, -1)        AS seller_sk,
            ISNULL(mc.mql_channel_sk, -1)   AS mql_channel_sk,

            -- ── Degenerate Dimensions (Business Keys) ─────────────────────────
            cd.mql_id                       AS mql_id_bk,

            -- sdr_id / sr_id are internal Olist employee IDs.
            -- Silver uses 'UNKNOWN' for missing values; keep as-is.
            NULLIF(cd.sdr_id, 'UNKNOWN')    AS sdr_id_bk,
            NULLIF(cd.sr_id,  'UNKNOWN')    AS sr_id_bk,

            -- ── Measures ──────────────────────────────────────────────────────
            -- days_to_close: first_contact_date → won_date
            -- NULL if either date is a sentinel
            CASE
                WHEN mql.first_contact_date NOT IN ('1900-01-01','9999-12-31')
                 AND cd.won_date            NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, mql.first_contact_date, cd.won_date)
            END                             AS days_to_close,

            -- Self-reported financials from silver (already DECIMAL(10,2))
            cd.declared_monthly_revenue,
            cd.declared_product_catalog_size

        FROM silver.closed_deals AS cd

        -- ── Join: get first_contact_date from MQL ────────────────────────────
        INNER JOIN silver.marketing_qualified_leads AS mql
            ON cd.mql_id = mql.mql_id

        -- ── Lookup: seller_id → seller_sk ────────────────────────────────────
        LEFT JOIN gold.dim_seller AS ds
            ON cd.seller_id = ds.seller_id_bk

        -- ── Lookup: mql_id → mql_channel_sk ──────────────────────────────────
        LEFT JOIN gold.dim_marketing_channel AS mc
            ON cd.mql_id = mc.mql_id_bk;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.fact_marketing_funnel loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_fact_marketing_funnel: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
