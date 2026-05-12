/* ============================================================
   gold_load_fact_order_items.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver → gold.fact_order_items
   Strategy : TRUNCATE + INSERT (idempotent full reload)
   Grain    : One row per ORDER LINE ITEM (order_id + order_item_id)

   SOURCE TABLES:
     silver.order_items   → item-level data (unit_price, freight, product, seller)
     silver.orders        → purchase_date + customer_id  (order-level)
     silver.customers     → customer_unique_id           (resolve per-order customer_id → person)

   DIMENSION LOOKUPS:
     dim_customer (customer_unique_id_bk → customer_sk)
     dim_product  (product_id_bk         → product_sk)   default: -1 if 'UNKNOWN'
     dim_seller   (seller_id_bk          → seller_sk)    default: -1 if 'UNKNOWN'
     dim_date     (YYYYMMDD integer)                      default: 19000101 if NULL

   DATE KEY FORMULA:
     CAST(CONVERT(VARCHAR(8), date_col, 112) AS INT)
     → converts DATE '2017-03-15' → integer 20170315
   ============================================================ */

USE [BI_AI];
GO

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

CREATE OR ALTER PROCEDURE gold.load_fact_order_items
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_fact_order_items ...';

        -- ── Full reload: truncate then insert ─────────────────────────────────
        TRUNCATE TABLE gold.fact_order_items;

        INSERT INTO gold.fact_order_items (
            purchase_date_key,
            shipping_limit_date_key,
            customer_sk,
            product_sk,
            seller_sk,
            order_id_bk,
            order_item_id_bk,
            unit_price,
            unit_freight_value
        )
        SELECT
            -- ── Date Keys (YYYYMMDD integer) ──────────────────────────────────
            -- purchase_date is order-level: comes from silver.orders
            ISNULL(
                CAST(CONVERT(VARCHAR(8), o.order_purchase_date, 112) AS INT),
                19000101
            )                               AS purchase_date_key,

            -- shipping_limit_date is item-level: comes from silver.order_items
            ISNULL(
                CAST(CONVERT(VARCHAR(8), oi.shipping_limit_date, 112) AS INT),
                19000101
            )                               AS shipping_limit_date_key,

            -- ── Dimension Lookups ─────────────────────────────────────────────

            -- customer_sk: resolve order-level customer_id → customer_unique_id → SK
            -- Join path: order_items → orders (customer_id) → customers (customer_unique_id)
            --            → dim_customer (customer_unique_id_bk)
            ISNULL(dc.customer_sk, -1)      AS customer_sk,

            -- product_sk: 'UNKNOWN' in silver maps to SK = -1 (Unknown member)
            ISNULL(dp.product_sk, -1)       AS product_sk,

            -- seller_sk: 'UNKNOWN' in silver maps to SK = -1 (Unknown member)
            ISNULL(ds.seller_sk, -1)        AS seller_sk,

            -- ── Degenerate Dimensions (Business Keys) ─────────────────────────
            oi.order_id                     AS order_id_bk,
            oi.order_item_id                AS order_item_id_bk,

            -- ── Measures ──────────────────────────────────────────────────────
            oi.unit_price,
            oi.unit_freight_value

        FROM silver.order_items AS oi

        -- ── Join 1: order_items → orders (get purchase_date + customer_id) ───
        INNER JOIN silver.orders AS o
            ON oi.order_id = o.order_id

        -- ── Join 2: orders.customer_id → customers.customer_unique_id ────────
        INNER JOIN silver.customers AS c
            ON o.customer_id = c.customer_id

        -- ── Dim Lookup: customer_unique_id → customer_sk ─────────────────────
        LEFT JOIN gold.dim_customer AS dc
            ON c.customer_unique_id = dc.customer_unique_id_bk

        -- ── Dim Lookup: product_id → product_sk ──────────────────────────────
        LEFT JOIN gold.dim_product AS dp
            ON oi.product_id = dp.product_id_bk

        -- ── Dim Lookup: seller_id → seller_sk ────────────────────────────────
        LEFT JOIN gold.dim_seller AS ds
            ON oi.seller_id = ds.seller_id_bk;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.fact_order_items loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_fact_order_items: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
