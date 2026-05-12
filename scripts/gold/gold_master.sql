/* ============================================================
   gold_master.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Master orchestrator — runs all Gold layer loads
              in strict dependency order.

   EXECUTION ORDER (dependency-safe):
   ─────────────────────────────────────────────────────────
   PRE-REQUISITES (run manually ONCE, before first execution):
     1. gold_ddl_dimensions.sql   → CREATE all dim tables + static seeds
     2. gold_generate_dim_date.sql → POPULATE gold.dim_date
     3. gold_ddl_facts.sql        → CREATE all fact tables + FK constraints

   DIMENSION LOADS (no cross-dim dependencies):
     4. gold.load_dim_customer
     5. gold.load_dim_product
     6. gold.load_dim_seller
     7. gold.load_dim_marketing_channel
     (dim_payment_type + dim_order_status are seeded in DDL — no load needed)

   FACT LOADS (after all dims are loaded):
     8. gold.load_fact_order_items       (needs dim_customer, dim_product, dim_seller, dim_date)
     9. gold.load_fact_payments          (needs dim_customer, dim_payment_type, dim_date)
    10. gold.load_fact_reviews           (needs dim_customer, dim_date — also loads review_comments)
    11. gold.load_fact_order_life_cycle  (needs dim_customer, dim_order_status, dim_date)
    12. gold.load_fact_marketing_funnel  (needs dim_seller, dim_marketing_channel, dim_date)
   ─────────────────────────────────────────────────────────

   IDEMPOTENT: Yes — each sub-procedure is safe to re-run.
   ERROR HANDLING: One failure stops the entire pipeline.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.gold_master
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @master_start DATETIME2 = GETDATE();

    PRINT '======================================================';
    PRINT '  Gold Layer Master Load';
    PRINT '  Started : ' + CONVERT(VARCHAR, GETDATE(), 120);
    PRINT '======================================================';

    -- ══════════════════════════════════════════════════════
    -- PHASE 1: DIMENSION LOADS
    -- ══════════════════════════════════════════════════════
    PRINT '';
    PRINT '-- PHASE 1: Dimensions --';

    -- 1. dim_customer
    BEGIN TRY
        EXEC gold.load_dim_customer;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_dim_customer failed. Halting.';
        THROW;
    END CATCH

    -- 2. dim_product
    BEGIN TRY
        EXEC gold.load_dim_product;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_dim_product failed. Halting.';
        THROW;
    END CATCH

    -- 3. dim_seller
    BEGIN TRY
        EXEC gold.load_dim_seller;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_dim_seller failed. Halting.';
        THROW;
    END CATCH

    -- 4. dim_marketing_channel (depends on silver.mql + silver.closed_deals)
    BEGIN TRY
        EXEC gold.load_dim_marketing_channel;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_dim_marketing_channel failed. Halting.';
        THROW;
    END CATCH

    -- ══════════════════════════════════════════════════════
    -- PHASE 2: FACT LOADS
    -- Must run AFTER all dimensions are populated.
    -- ══════════════════════════════════════════════════════
    PRINT '';
    PRINT '-- PHASE 2: Facts --';

    -- 5. fact_order_items
    BEGIN TRY
        EXEC gold.load_fact_order_items;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_fact_order_items failed. Halting.';
        THROW;
    END CATCH

    -- 6. fact_payments
    BEGIN TRY
        EXEC gold.load_fact_payments;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_fact_payments failed. Halting.';
        THROW;
    END CATCH

    -- 7. fact_reviews + review_comments (outrigger loaded inside same procedure)
    BEGIN TRY
        EXEC gold.load_fact_reviews;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_fact_reviews failed. Halting.';
        THROW;
    END CATCH

    -- 8. fact_order_life_cycle (accumulating snapshot)
    BEGIN TRY
        EXEC gold.load_fact_order_life_cycle;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_fact_order_life_cycle failed. Halting.';
        THROW;
    END CATCH

    -- 9. fact_marketing_funnel
    BEGIN TRY
        EXEC gold.load_fact_marketing_funnel;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: gold.load_fact_marketing_funnel failed. Halting.';
        THROW;
    END CATCH

    -- ══════════════════════════════════════════════════════
    -- SUMMARY
    -- ══════════════════════════════════════════════════════
    PRINT '';
    PRINT '======================================================';
    PRINT '  Gold Layer Master Load COMPLETE';
    PRINT '  Finished : ' + CONVERT(VARCHAR, GETDATE(), 120);
    PRINT '  Total    : ' + CAST(DATEDIFF(SECOND, @master_start, GETDATE()) AS VARCHAR(10)) + 's';
    PRINT '======================================================';

END;
GO

-- ── Quick-start row count verification ───────────────────────────────────────
-- Run this after EXEC gold.gold_master to confirm all tables loaded correctly.
/*
SELECT 'dim_date'                AS table_name, COUNT(*) AS row_count FROM gold.dim_date
UNION ALL SELECT 'dim_customer',               COUNT(*) FROM gold.dim_customer
UNION ALL SELECT 'dim_product',                COUNT(*) FROM gold.dim_product
UNION ALL SELECT 'dim_seller',                 COUNT(*) FROM gold.dim_seller
UNION ALL SELECT 'dim_payment_type',           COUNT(*) FROM gold.dim_payment_type
UNION ALL SELECT 'dim_order_status',           COUNT(*) FROM gold.dim_order_status
UNION ALL SELECT 'dim_marketing_channel',      COUNT(*) FROM gold.dim_marketing_channel
UNION ALL SELECT 'review_comments',            COUNT(*) FROM gold.review_comments
UNION ALL SELECT 'fact_order_items',           COUNT(*) FROM gold.fact_order_items
UNION ALL SELECT 'fact_payments',              COUNT(*) FROM gold.fact_payments
UNION ALL SELECT 'fact_reviews',               COUNT(*) FROM gold.fact_reviews
UNION ALL SELECT 'fact_order_life_cycle',      COUNT(*) FROM gold.fact_order_life_cycle
UNION ALL SELECT 'fact_marketing_funnel',      COUNT(*) FROM gold.fact_marketing_funnel
ORDER BY table_name;
*/
