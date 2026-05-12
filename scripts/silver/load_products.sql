/* ============================================================
   load_products.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for products table
              Joins product_category_name_translation for English
              category names and converts snake_case → Title Case
   Strategy : DROP + SELECT INTO (idempotent full-load)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_products
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_products ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.products', 'U') IS NOT NULL
            DROP TABLE silver.products;

        -- ── 2. Load: deduplicate + join translation + title-case ──────────
        WITH deduped_products AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY product_id
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.products
        ),
        deduped_translation AS (
            SELECT
                product_category_name,
                product_category_name_english,
                ROW_NUMBER() OVER (
                    PARTITION BY product_category_name
                    ORDER BY _ingested_at DESC
                ) AS rn
            FROM bronze.product_category_name_translation
        )
        SELECT
            LTRIM(RTRIM(p.product_id))                          AS product_id,

            -- Category: English name preferred, Portuguese fallback, NULL → 'Not Specified'
            -- snake_case (bed_bath_table) → Title Case (Bed Bath Table)
            -- Requires SQL Server 2022+ for STRING_SPLIT with ordinal
            ISNULL(tc.category_title_case, 'Not Specified')     AS product_category_name,

            -- Fix source typos (lenght → length) + float → INT, NULL → 0
            ISNULL(CAST(p.product_name_lenght        AS INT), 0) AS product_name_length,
            ISNULL(CAST(p.product_description_lenght AS INT), 0) AS product_description_length,
            ISNULL(CAST(p.product_photos_qty         AS INT), 0) AS product_photos_qty,

            -- Physical measurements: float → INT, NULL → 0
            ISNULL(CAST(p.product_weight_g           AS INT), 0) AS product_weight_g,
            ISNULL(CAST(p.product_length_cm          AS INT), 0) AS product_length_cm,
            ISNULL(CAST(p.product_height_cm          AS INT), 0) AS product_height_cm,
            ISNULL(CAST(p.product_width_cm           AS INT), 0) AS product_width_cm,

            -- Metadata
            p._ingested_at,
            p._source,
            GETDATE()                                            AS _processed_at

        INTO silver.products

        FROM deduped_products p
        LEFT JOIN deduped_translation t
            ON LTRIM(RTRIM(p.product_category_name)) = LTRIM(RTRIM(t.product_category_name))
            AND t.rn = 1

        -- Title Case: split English name on spaces, capitalize each word, rejoin
        CROSS APPLY (
            SELECT
                NULLIF(
                    STRING_AGG(
                        UPPER(LEFT(value, 1)) + LOWER(SUBSTRING(value, 2, LEN(value))),
                        ' '
                    ) WITHIN GROUP (ORDER BY ordinal),
                '') AS category_title_case
            FROM STRING_SPLIT(
                -- 1. Resolve: English → Portuguese fallback → empty string
                LOWER(REPLACE(
                    ISNULL(
                        LTRIM(RTRIM(t.product_category_name_english)),
                        ISNULL(LTRIM(RTRIM(p.product_category_name)), '')
                    ),
                '_', ' ')),     -- 2. Replace underscores with spaces
                ' ', 1          -- 3. Split with ordinal (SQL Server 2022+)
            )
            WHERE LTRIM(value) <> ''    -- filter empty tokens from double spaces
        ) AS tc

        WHERE p.rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.products loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_products: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
