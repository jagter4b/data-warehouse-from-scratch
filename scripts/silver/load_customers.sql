/* ============================================================
   load_customers.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for customers table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_customers
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_customers ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.customers', 'U') IS NOT NULL
            DROP TABLE silver.customers;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY customer_id
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.customers
        )
        SELECT
            -- Keys
            LTRIM(RTRIM(customer_id))                                        AS customer_id,
            LTRIM(RTRIM(customer_unique_id))                                 AS customer_unique_id,

            -- Zip: numeric → CHAR(5) with leading-zero padding
            -- 1151 → '01151' | 9790 → '09790' | 14409 → '14409'
            RIGHT('00000' + CAST(customer_zip_code_prefix AS VARCHAR(5)), 5) AS customer_zip_code_prefix,

            -- City / State: uppercase + trim
            UPPER(LTRIM(RTRIM(customer_city)))                               AS customer_city,
            UPPER(LTRIM(RTRIM(customer_state)))                              AS customer_state,

            -- Metadata
            _ingested_at,
            _source,
            GETDATE()                                                        AS _processed_at

        INTO silver.customers
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.customers loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_customers: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
