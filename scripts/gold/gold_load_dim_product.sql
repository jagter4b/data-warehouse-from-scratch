/* ============================================================
   gold_load_dim_product.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver.products → gold.dim_product
   Strategy : MERGE (upsert / SCD Type 1 — overwrite)
   Grain    : One row per product_id

   UNKNOWN MEMBER:
     silver.order_items uses ISNULL(product_id, 'UNKNOWN').
     An SK = -1 row with product_id_bk = 'UNKNOWN' must exist
     before fact_order_items is loaded.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_dim_product
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_dim_product ...';

        -- ── Ensure Unknown Member (SK = -1) ──────────────────────────────────
        SET IDENTITY_INSERT gold.dim_product ON;

        MERGE gold.dim_product AS tgt
        USING (SELECT -1 AS product_sk, 'UNKNOWN' AS product_id_bk) AS src
            ON tgt.product_sk = src.product_sk
        WHEN NOT MATCHED THEN
            INSERT (product_sk, product_id_bk, product_category_name)
            VALUES (-1, 'UNKNOWN', 'Not Specified');

        SET IDENTITY_INSERT gold.dim_product OFF;

        -- ── MERGE: silver.products → gold.dim_product ─────────────────────────
        MERGE gold.dim_product AS tgt
        USING (
            SELECT
                product_id                  AS product_id_bk,
                product_category_name,
                product_name_length,
                product_description_length,
                product_photos_qty,
                product_weight_g,
                product_length_cm,
                product_height_cm,
                product_width_cm
            FROM silver.products
        ) AS src
            ON tgt.product_id_bk = src.product_id_bk

        -- SCD Type 1: overwrite all descriptive attributes on change
        WHEN MATCHED AND (
            tgt.product_category_name      <> src.product_category_name   OR
            ISNULL(tgt.product_name_length,       -1) <> ISNULL(src.product_name_length,       -1) OR
            ISNULL(tgt.product_description_length,-1) <> ISNULL(src.product_description_length,-1) OR
            ISNULL(tgt.product_photos_qty,        -1) <> ISNULL(src.product_photos_qty,        -1) OR
            ISNULL(tgt.product_weight_g,          -1) <> ISNULL(src.product_weight_g,          -1) OR
            ISNULL(tgt.product_length_cm,         -1) <> ISNULL(src.product_length_cm,         -1) OR
            ISNULL(tgt.product_height_cm,         -1) <> ISNULL(src.product_height_cm,         -1) OR
            ISNULL(tgt.product_width_cm,          -1) <> ISNULL(src.product_width_cm,          -1)
        ) THEN UPDATE SET
            tgt.product_category_name      = src.product_category_name,
            tgt.product_name_length        = src.product_name_length,
            tgt.product_description_length = src.product_description_length,
            tgt.product_photos_qty         = src.product_photos_qty,
            tgt.product_weight_g           = src.product_weight_g,
            tgt.product_length_cm          = src.product_length_cm,
            tgt.product_height_cm          = src.product_height_cm,
            tgt.product_width_cm           = src.product_width_cm,
            tgt.load_timestamp             = GETDATE()

        WHEN NOT MATCHED BY TARGET THEN
            INSERT (
                product_id_bk,
                product_category_name,
                product_name_length,
                product_description_length,
                product_photos_qty,
                product_weight_g,
                product_length_cm,
                product_height_cm,
                product_width_cm
            )
            VALUES (
                src.product_id_bk,
                src.product_category_name,
                src.product_name_length,
                src.product_description_length,
                src.product_photos_qty,
                src.product_weight_g,
                src.product_length_cm,
                src.product_height_cm,
                src.product_width_cm
            );

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.dim_product loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows affected in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_dim_product: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
