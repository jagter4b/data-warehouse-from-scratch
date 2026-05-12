/* ============================================================
   load_order_reviews.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Full-reload Bronze → Silver for order_reviews table
   Strategy : DROP + SELECT INTO (idempotent full-load)
   Note     : One row per order_id — most recent review wins
              (an order can have multiple review attempts)
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE silver.load_order_reviews
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting silver.load_order_reviews ...';

        -- ── 1. Drop existing silver table ─────────────────────────────────
        IF OBJECT_ID('silver.order_reviews', 'U') IS NOT NULL
            DROP TABLE silver.order_reviews;

        -- ── 2. Load: deduplicate + clean ──────────────────────────────────
        -- Source PK is (order_id, review_id).
        -- We collapse to one row per order_id keeping the most recently answered review.
        WITH deduped AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY TRY_CAST(review_answer_timestamp AS DATE) DESC,
                             _ingested_at DESC   -- tie-break: re-ingestion duplicates
                ) AS rn
            FROM bronze.order_reviews
        )
        SELECT
            LTRIM(RTRIM(review_id))                                             AS review_id,
            LTRIM(RTRIM(order_id))                                              AS order_id,

            -- Score: numeric 1–5
            CAST(review_score AS TINYINT)                                       AS review_score,

            -- Free-text fields: NULL → sentinel string
            ISNULL(LTRIM(RTRIM(review_comment_title)),   'No Title')            AS review_comment_title,
            ISNULL(LTRIM(RTRIM(review_comment_message)), 'No Message')          AS review_comment_message,

            -- Dates: varchar → DATE, NULL → '1900-01-01'
            ISNULL(TRY_CAST(review_creation_date    AS DATE), '1900-01-01')     AS review_creation_date,
            ISNULL(TRY_CAST(review_answer_timestamp AS DATE), '1900-01-01')     AS review_answer_date,

            -- Metadata
            _ingested_at,
            _source,
            GETDATE()                                                           AS _processed_at

        INTO silver.order_reviews
        FROM deduped
        WHERE rn = 1;

        -- ── 3. Log ────────────────────────────────────────────────────────
        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] silver.order_reviews loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in silver.load_order_reviews: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
