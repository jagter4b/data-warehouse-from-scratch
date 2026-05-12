/* ============================================================
   load_order_items.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for order_items table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_order_items
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_order_items ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.order_items', 'U') IS NOT NULL
            DROP TABLE silver.order_items;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id, order_item_id   -- composite PK
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.order_items
        )
        SELECT
            -- Composite PK
            LTRIM(RTRIM(order_id))                                          AS order_id,
            order_item_id,                                                  -- sequential INT: 1, 2, 3 ...

            -- FK columns: NULL → 'UNKNOWN' (maps to Unknown dim member in Gold)
            ISNULL(LTRIM(RTRIM(product_id)), 'UNKNOWN')                     AS product_id,
            ISNULL(LTRIM(RTRIM(seller_id)),  'UNKNOWN')                     AS seller_id,

            -- Shipping deadline: varchar → DATE, NULL = data quality gap → '1900-01-01'
            ISNULL(TRY_CAST(shipping_limit_date AS DATE), '1900-01-01')     AS shipping_limit_date,

            -- Financials: float → DECIMAL(10,2), NULL → 0.00
            ISNULL(CAST(price         AS DECIMAL(10, 2)), 0.00)             AS unit_price,
            ISNULL(CAST(freight_value AS DECIMAL(10, 2)), 0.00)             AS unit_freight_value,

            -- Metadata
            _ingested_at,
            _source,
            GETDATE()                                                       AS _processed_at

        INTO silver.order_items
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.order_items loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_order_items: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
