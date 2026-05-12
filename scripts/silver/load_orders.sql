/* ============================================================
   load_orders.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for orders table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_orders
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_orders ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.orders', 'U') IS NOT NULL
            DROP TABLE silver.orders;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.orders
        ),
        cleaned AS (
            SELECT
                LTRIM(RTRIM(order_id))              AS order_id,
                LTRIM(RTRIM(customer_id))           AS customer_id,

                -- Status: lowercase + trim for consistent downstream filtering
                LOWER(LTRIM(RTRIM(order_status)))   AS order_status,

                -- Purchase & approval: NULL = data quality gap → sentinel '1900-01-01'
                ISNULL(TRY_CAST(order_purchase_timestamp AS DATE), '1900-01-01')
                                                    AS order_purchase_date,
                ISNULL(TRY_CAST(order_approved_at AS DATE), '1900-01-01')
                                                    AS order_approved_date,

                -- Carrier handoff:
                --   NULL + canceled/unavailable  → '1900-01-01' (never shipped)
                --   NULL + other status          → '9999-12-31' (in-progress/pending)
                CASE
                    WHEN order_delivered_carrier_date IS NOT NULL
                        THEN TRY_CAST(order_delivered_carrier_date AS DATE)
                    WHEN LOWER(LTRIM(RTRIM(order_status))) IN ('canceled','unavailable')
                        THEN CAST('1900-01-01' AS DATE)
                    ELSE CAST('9999-12-31' AS DATE)
                END                                 AS order_delivered_carrier_date,

                -- Delivered to customer (same sentinel logic)
                CASE
                    WHEN order_delivered_customer_date IS NOT NULL
                        THEN TRY_CAST(order_delivered_customer_date AS DATE)
                    WHEN LOWER(LTRIM(RTRIM(order_status))) IN ('canceled','unavailable')
                        THEN CAST('1900-01-01' AS DATE)
                    ELSE CAST('9999-12-31' AS DATE)
                END                                 AS order_delivered_customer_date,

                -- Estimated delivery: always set at purchase
                ISNULL(TRY_CAST(order_estimated_delivery_date AS DATE), '1900-01-01')
                                                    AS order_estimated_delivery_date,

                -- Metadata
                _ingested_at,
                _source,
                GETDATE()                           AS _processed_at

            FROM deduped
            WHERE rn = 1
        )
        SELECT * INTO silver.orders FROM cleaned;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.orders loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_orders: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
