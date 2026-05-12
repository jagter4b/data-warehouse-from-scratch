/* ============================================================
   load_marketing_qualified_leads.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for marketing_qualified_leads
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_marketing_qualified_leads
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_marketing_qualified_leads ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.marketing_qualified_leads', 'U') IS NOT NULL
            DROP TABLE silver.marketing_qualified_leads;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY mql_id
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.marketing_qualified_leads
        )
        SELECT
            -- PK
            LTRIM(RTRIM(mql_id))                                        AS mql_id,

            -- Date: already DATE in source, cast defensively
            ISNULL(TRY_CAST(first_contact_date AS DATE), '1900-01-01') AS first_contact_date,

            -- Landing page: opaque hash ID, trim + NULL guard
            ISNULL(LTRIM(RTRIM(landing_page_id)), 'UNKNOWN')           AS landing_page_id,

            -- Origin: controlled vocabulary → human-readable label
            -- 'other', 'other_publicities', unknown values, NULL → 'Other'
            CASE LOWER(LTRIM(RTRIM(origin)))
                WHEN 'organic_search'    THEN 'Organic Search'
                WHEN 'paid_search'       THEN 'Paid Search'
                WHEN 'social'            THEN 'Social'
                WHEN 'email'             THEN 'Email'
                WHEN 'referral'          THEN 'Referral'
                WHEN 'display'           THEN 'Display'
                WHEN 'direct_traffic'    THEN 'Direct Traffic'
                ELSE                          'Other'
            END                                                        AS origin,

            -- Metadata (_drive_file_id dropped — bronze ingestion artifact)
            _ingested_at,
            _source,
            GETDATE()                                                  AS _processed_at

        INTO silver.marketing_qualified_leads
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.marketing_qualified_leads loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_marketing_qualified_leads: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
