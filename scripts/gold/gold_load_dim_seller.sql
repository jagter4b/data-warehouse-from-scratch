/* ============================================================
   gold_load_dim_seller.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver.sellers → gold.dim_seller
   Strategy : MERGE (upsert / SCD Type 1)
   Grain    : One row per seller_id

   UNKNOWN MEMBER:
     silver.order_items uses ISNULL(seller_id, 'UNKNOWN').
     SK = -1 / seller_id_bk = 'UNKNOWN' must exist before
     fact_order_items is loaded.

   SHARED DIMENSION:
     dim_seller is used by BOTH fact_order_items (e-commerce)
     AND fact_marketing_funnel (marketing). The seller_id_bk is
     the bridge between the two subject areas.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_dim_seller
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_dim_seller ...';

        -- ── Ensure Unknown Member (SK = -1) ──────────────────────────────────
        SET IDENTITY_INSERT gold.dim_seller ON;

        MERGE gold.dim_seller AS tgt
        USING (SELECT -1 AS seller_sk, 'UNKNOWN' AS seller_id_bk) AS src
            ON tgt.seller_sk = src.seller_sk
        WHEN NOT MATCHED THEN
            INSERT (seller_sk, seller_id_bk, seller_zip_code_prefix, seller_city, seller_state)
            VALUES (-1, 'UNKNOWN', '00000', 'UNKNOWN', 'UN');

        SET IDENTITY_INSERT gold.dim_seller OFF;

        -- ── MERGE: silver.sellers → gold.dim_seller ───────────────────────────
        MERGE gold.dim_seller AS tgt
        USING (
            SELECT
                seller_id               AS seller_id_bk,
                seller_zip_code_prefix,
                seller_city,
                seller_state
            FROM silver.sellers
        ) AS src
            ON tgt.seller_id_bk = src.seller_id_bk

        -- SCD Type 1: overwrite changed attributes
        WHEN MATCHED AND (
            tgt.seller_zip_code_prefix <> src.seller_zip_code_prefix OR
            tgt.seller_city            <> src.seller_city            OR
            tgt.seller_state           <> src.seller_state
        ) THEN UPDATE SET
            tgt.seller_zip_code_prefix = src.seller_zip_code_prefix,
            tgt.seller_city            = src.seller_city,
            tgt.seller_state           = src.seller_state,
            tgt.load_timestamp         = GETDATE()

        WHEN NOT MATCHED BY TARGET THEN
            INSERT (seller_id_bk, seller_zip_code_prefix, seller_city, seller_state)
            VALUES (src.seller_id_bk, src.seller_zip_code_prefix, src.seller_city, src.seller_state);

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.dim_seller loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows affected in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_dim_seller: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
