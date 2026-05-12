/* ============================================================
   silver_master.sql
   Database : BI_AI
   Purpose  : Master orchestrator — runs all Silver layer loads
              in dependency order. Each sub-procedure is wrapped
              in its own TRY/CATCH so one failure logs and stops.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.silver_master
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @master_start DATETIME2 = GETDATE();

    PRINT '======================================================';
    PRINT '  Silver Layer Master Load';
    PRINT '  Started : ' + CONVERT(VARCHAR, GETDATE(), 120);
    PRINT '======================================================';

    -- ── Ensure silver schema exists ───────────────────────────────────────
    IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'silver')
        EXEC('CREATE SCHEMA silver');

    -- ── 1. customers ─────────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_customers;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_customers failed. Halting.';
        THROW;
    END CATCH

    -- ── 2. sellers ───────────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_sellers;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_sellers failed. Halting.';
        THROW;
    END CATCH

    -- ── 3. products (joins bronze.product_category_name_translation) ──────
    BEGIN TRY
        EXEC silver.load_products;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_products failed. Halting.';
        THROW;
    END CATCH

    -- ── 4. orders ────────────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_orders;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_orders failed. Halting.';
        THROW;
    END CATCH

    -- ── 5. order_items ───────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_order_items;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_order_items failed. Halting.';
        THROW;
    END CATCH

    -- ── 6. order_payments ────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_order_payments;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_order_payments failed. Halting.';
        THROW;
    END CATCH

    -- ── 7. order_reviews ─────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_order_reviews;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_order_reviews failed. Halting.';
        THROW;
    END CATCH

    -- ── 8. marketing_qualified_leads ─────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_marketing_qualified_leads;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_marketing_qualified_leads failed. Halting.';
        THROW;
    END CATCH

    -- ── 9. closed_deals ──────────────────────────────────────────────────
    BEGIN TRY
        EXEC silver.load_closed_deals;
    END TRY
    BEGIN CATCH
        PRINT '>> FATAL: silver.load_closed_deals failed. Halting.';
        THROW;
    END CATCH

    -- ── Summary ──────────────────────────────────────────────────────────
    PRINT '======================================================';
    PRINT '  Silver Layer Master Load COMPLETE';
    PRINT '  Finished : ' + CONVERT(VARCHAR, GETDATE(), 120);
    PRINT '  Total    : ' + CAST(DATEDIFF(SECOND, @master_start, GETDATE()) AS VARCHAR(10)) + 's';
    PRINT '======================================================';

END;
GO
