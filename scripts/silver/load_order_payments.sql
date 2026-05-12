/* ============================================================
   load_order_payments.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for order_payments table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_order_payments
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_order_payments ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.order_payments', 'U') IS NOT NULL
            DROP TABLE silver.order_payments;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id, payment_sequential   -- composite PK
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.order_payments
        )
        SELECT
            -- Composite PK
            LTRIM(RTRIM(order_id))      AS order_id,
            payment_sequential,         -- 1, 2, 3 ... within each order

            -- Payment type: raw snake_case → human-readable label
            CASE LOWER(LTRIM(RTRIM(payment_type)))
                WHEN 'credit_card'  THEN 'Credit Card'
                WHEN 'debit_card'   THEN 'Debit Card'
                WHEN 'boleto'       THEN 'Boleto'           -- Brazilian bank slip
                WHEN 'voucher'      THEN 'Voucher'
                WHEN 'not_defined'  THEN 'Not Specified'
                ELSE                     'Not Specified'    -- NULL or unexpected
            END                         AS payment_type,

            -- Installments: meaningful for Credit/Debit Card only
            -- Boleto/Voucher always 1 in practice. NULL → 0
            ISNULL(CAST(payment_installments AS INT), 0)        AS payment_installments,

            -- Payment value: float → DECIMAL(10,2), NULL → 0.00
            ISNULL(CAST(payment_value AS DECIMAL(10, 2)), 0.00) AS payment_value,

            -- Metadata
            _ingested_at,
            _source,
            GETDATE()                                           AS _processed_at

        INTO silver.order_payments
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.order_payments loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_order_payments: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
