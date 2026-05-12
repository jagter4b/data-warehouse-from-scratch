/* ============================================================
   gold_load_fact_payments.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver → gold.fact_payments
   Strategy : TRUNCATE + INSERT (idempotent full reload)

   GRAIN: One row per PAYMENT SEQUENCE within an order.
     Composite BK = (order_id, payment_sequential)
     One order may have MULTIPLE rows if paid with multiple methods.

   EXAMPLE:
     order_id = 'abc123', seq = 1, type = 'Voucher',      value = 50.00
     order_id = 'abc123', seq = 2, type = 'Credit Card',  value = 120.00
     → 2 rows in fact_payments for this one order

   CUSTOMER JOIN PATH:
     silver.order_payments has NO customer column.
     Resolution chain:
       order_payments.order_id
         → orders.customer_id
             → customers.customer_unique_id
                 → dim_customer.customer_unique_id_bk → customer_sk

   PAYMENT TYPE LOOKUP:
     payment_type text (e.g. 'Credit Card') → dim_payment_type.payment_type_sk
     silver already standardized the text values to match dim seeds.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_fact_payments
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_fact_payments ...';

        TRUNCATE TABLE gold.fact_payments;

        INSERT INTO gold.fact_payments (
            purchase_date_key,
            customer_sk,
            payment_type_sk,
            order_id_bk,
            payment_sequential_bk,
            payment_value,
            payment_installments
        )
        SELECT
            -- ── Date Key ─────────────────────────────────────────────────────
            -- purchase_date is order-level, from silver.orders
            ISNULL(
                CAST(CONVERT(VARCHAR(8), o.order_purchase_date, 112) AS INT),
                19000101
            )                               AS purchase_date_key,

            -- ── Dimension Lookups ─────────────────────────────────────────────
            -- customer_sk: payment has no customer column — resolve via orders + customers
            ISNULL(dc.customer_sk, -1)      AS customer_sk,

            -- payment_type_sk: match the standardized text from silver to the seeded dim
            ISNULL(pt.payment_type_sk, 5)   AS payment_type_sk,  -- 5 = 'Not Specified' fallback

            -- ── Degenerate Dimensions (Business Keys) ─────────────────────────
            op.order_id                     AS order_id_bk,
            op.payment_sequential           AS payment_sequential_bk,

            -- ── Measures ──────────────────────────────────────────────────────
            op.payment_value,
            op.payment_installments

        FROM silver.order_payments AS op

        -- ── Join: get purchase_date + customer_id from orders ─────────────────
        INNER JOIN silver.orders AS o
            ON op.order_id = o.order_id

        -- ── Join: resolve customer_id → customer_unique_id ───────────────────
        INNER JOIN silver.customers AS c
            ON o.customer_id = c.customer_id

        -- ── Lookup: customer_unique_id → customer_sk ─────────────────────────
        LEFT JOIN gold.dim_customer AS dc
            ON c.customer_unique_id = dc.customer_unique_id_bk

        -- ── Lookup: payment_type text → payment_type_sk ──────────────────────
        LEFT JOIN gold.dim_payment_type AS pt
            ON op.payment_type = pt.payment_type;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.fact_payments loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_fact_payments: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
