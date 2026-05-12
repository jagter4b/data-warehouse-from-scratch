/* ============================================================
   load_sellers.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for sellers table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_sellers
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_sellers ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.sellers', 'U') IS NOT NULL
            DROP TABLE silver.sellers;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY seller_id
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.sellers
        )
        SELECT
            -- PK
            LTRIM(RTRIM(seller_id))                                          AS seller_id,

            -- Zip: numeric → CHAR(5) with leading-zero padding
            -- 4195 → '04195' | 1529 → '01529' | 1222 → '01222'
            RIGHT('00000' + CAST(seller_zip_code_prefix AS VARCHAR(5)), 5)   AS seller_zip_code_prefix,

            -- City / State: UPPER + trim + NULL guard → 'Not Specified'
            ISNULL(UPPER(LTRIM(RTRIM(seller_city))),  'Not Specified')       AS seller_city,
            ISNULL(UPPER(LTRIM(RTRIM(seller_state))), 'Not Specified')       AS seller_state,

            -- Metadata
            _ingested_at,
            _source,
            GETDATE()                                                        AS _processed_at

        INTO silver.sellers
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.sellers loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_sellers: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
