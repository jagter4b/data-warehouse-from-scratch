/* ============================================================
   gold_load_fact_order_life_cycle.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver → gold.fact_order_life_cycle
   Strategy : TRUNCATE + INSERT (idempotent full reload)

   GRAIN: One row per ORDER (accumulating snapshot).
     Each row captures all lifecycle milestones for an order
     in a single wide row, updated as milestones are reached.

   FIVE DATE MILESTONES (all role-play dim_date):
     purchase_date_key           → order placed
     approval_date_key           → payment approved
     carrier_date_key            → handed to carrier
     delivery_date_key           → delivered to customer
     estimated_delivery_date_key → originally promised delivery date

   SENTINEL LOGIC (inherited from silver.orders):
     '1900-01-01' = data quality gap    → date_key 19000101
     '9999-12-31' = not yet occurred    → date_key 99991231
     These sentinel strings were set during silver transformation.

   LAG MEASURES:
     Only computed when BOTH boundary dates are real calendar dates
     (not sentinels). Otherwise NULL.

   SUMMARY MEASURES (aggregated from silver):
     total_items, total_distinct_products, total_distinct_sellers
       → COUNT from silver.order_items
     total_order_value, total_freight_value
       → SUM from silver.order_items
     total_payment_value
       → SUM from silver.order_payments
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_fact_order_life_cycle
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_fact_order_life_cycle ...';

        TRUNCATE TABLE gold.fact_order_life_cycle;

        -- ── Pre-aggregate silver.order_items per order ────────────────────────
        -- Done in a CTE to keep the main INSERT clean.
        ;WITH item_agg AS (
            SELECT
                order_id,
                COUNT(*)                        AS total_items,
                COUNT(DISTINCT product_id)      AS total_distinct_products,
                COUNT(DISTINCT seller_id)       AS total_distinct_sellers,
                SUM(unit_price)                 AS total_order_value,
                SUM(unit_freight_value)         AS total_freight_value
            FROM silver.order_items
            GROUP BY order_id
        ),

        -- ── Pre-aggregate silver.order_payments per order ─────────────────────
        payment_agg AS (
            SELECT
                order_id,
                SUM(payment_value)              AS total_payment_value
            FROM silver.order_payments
            GROUP BY order_id
        )

        INSERT INTO gold.fact_order_life_cycle (
            purchase_date_key,
            approval_date_key,
            carrier_date_key,
            delivery_date_key,
            estimated_delivery_date_key,
            customer_sk,
            order_status_sk,
            order_id_bk,
            days_to_approve,
            days_to_ship,
            days_to_deliver,
            days_purchase_to_delivery,
            days_delivery_variance,
            is_delivered_on_time,
            total_items,
            total_distinct_products,
            total_distinct_sellers,
            total_order_value,
            total_freight_value,
            total_payment_value
        )
        SELECT
            -- ── Date Keys (YYYYMMDD) ──────────────────────────────────────────
            -- Silver already encodes sentinels as '1900-01-01' and '9999-12-31'
            CAST(CONVERT(VARCHAR(8), o.order_purchase_date,            112) AS INT) AS purchase_date_key,
            CAST(CONVERT(VARCHAR(8), o.order_approved_date,            112) AS INT) AS approval_date_key,
            CAST(CONVERT(VARCHAR(8), o.order_delivered_carrier_date,   112) AS INT) AS carrier_date_key,
            CAST(CONVERT(VARCHAR(8), o.order_delivered_customer_date,  112) AS INT) AS delivery_date_key,
            CAST(CONVERT(VARCHAR(8), o.order_estimated_delivery_date,  112) AS INT) AS estimated_delivery_date_key,

            -- ── Dimension Lookups ─────────────────────────────────────────────
            ISNULL(dc.customer_sk, -1)      AS customer_sk,
            ISNULL(ds.order_status_sk, 1)   AS order_status_sk,  -- fallback to first status

            -- ── Degenerate Dimension ──────────────────────────────────────────
            o.order_id                      AS order_id_bk,

            -- ── Lag Measures ──────────────────────────────────────────────────
            -- Rule: NULL if either boundary date is a sentinel (1900 or 9999).
            -- This preserves analytical integrity — do not compute
            -- meaningless durations for incomplete lifecycle stages.

            -- days_to_approve: purchase → approval
            CASE
                WHEN o.order_purchase_date NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_approved_date NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, o.order_purchase_date, o.order_approved_date)
            END                             AS days_to_approve,

            -- days_to_ship: approval → carrier handoff
            CASE
                WHEN o.order_approved_date          NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_delivered_carrier_date  NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, o.order_approved_date, o.order_delivered_carrier_date)
            END                             AS days_to_ship,

            -- days_to_deliver: carrier handoff → customer delivery
            CASE
                WHEN o.order_delivered_carrier_date   NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_delivered_customer_date  NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, o.order_delivered_carrier_date, o.order_delivered_customer_date)
            END                             AS days_to_deliver,

            -- days_purchase_to_delivery: total order span
            CASE
                WHEN o.order_purchase_date           NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_delivered_customer_date NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, o.order_purchase_date, o.order_delivered_customer_date)
            END                             AS days_purchase_to_delivery,

            -- days_delivery_variance: actual − estimated  (negative = early, positive = late)
            CASE
                WHEN o.order_estimated_delivery_date  NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_delivered_customer_date  NOT IN ('1900-01-01','9999-12-31')
                THEN DATEDIFF(DAY, o.order_estimated_delivery_date, o.order_delivered_customer_date)
            END                             AS days_delivery_variance,

            -- is_delivered_on_time: 1 = on time or early, 0 = late, NULL = not yet delivered
            CASE
                WHEN o.order_delivered_customer_date NOT IN ('1900-01-01','9999-12-31')
                 AND o.order_estimated_delivery_date NOT IN ('1900-01-01','9999-12-31')
                THEN CASE
                    WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                    THEN CAST(1 AS BIT)
                    ELSE CAST(0 AS BIT)
                END
            END                             AS is_delivered_on_time,

            -- ── Summary Measures (from pre-aggregated CTEs) ───────────────────
            ISNULL(ia.total_items,              0)  AS total_items,
            ISNULL(ia.total_distinct_products,  0)  AS total_distinct_products,
            ISNULL(ia.total_distinct_sellers,   0)  AS total_distinct_sellers,
            ISNULL(ia.total_order_value,     0.00)  AS total_order_value,
            ISNULL(ia.total_freight_value,   0.00)  AS total_freight_value,
            ISNULL(pa.total_payment_value,   0.00)  AS total_payment_value

        FROM silver.orders AS o

        -- ── Join: customer_id → customer_unique_id ────────────────────────────
        INNER JOIN silver.customers AS c
            ON o.customer_id = c.customer_id

        -- ── Lookup: customer_unique_id → customer_sk ─────────────────────────
        LEFT JOIN gold.dim_customer AS dc
            ON c.customer_unique_id = dc.customer_unique_id_bk

        -- ── Lookup: order_status text → order_status_sk ──────────────────────
        LEFT JOIN gold.dim_order_status AS ds
            ON o.order_status = ds.order_status

        -- ── Aggregate joins ───────────────────────────────────────────────────
        LEFT JOIN item_agg    AS ia ON o.order_id = ia.order_id
        LEFT JOIN payment_agg AS pa ON o.order_id = pa.order_id;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.fact_order_life_cycle loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_fact_order_life_cycle: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
