/* ============================================================
   gold_load_fact_reviews.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver → gold.fact_reviews + gold.review_comments
   Strategy : TRUNCATE + INSERT (idempotent full reload)
   Grain    : One row per order review (silver already deduped
              to one review per order_id)

   OUTRIGGER:
     review_comments is loaded AFTER fact_reviews in the same
     procedure so the FK (review_comments.review_sk → fact_reviews)
     is always satisfied within the same transaction.

   CUSTOMER JOIN PATH:
     silver.order_reviews has order_id but no customer column.
     Resolution:
       order_reviews.order_id
         → orders.customer_id
             → customers.customer_unique_id
                 → dim_customer.customer_unique_id_bk → customer_sk
   ============================================================ */

USE [BI_AI];
GO

SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

CREATE OR ALTER PROCEDURE gold.load_fact_reviews
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_fact_reviews ...';

        -- ── Full reload: DROP FK → TRUNCATE → Recreate FK ──────────────────────────
        -- SQL Server unconditionally blocks TRUNCATE on any FK-referenced table.
        -- Neither dynamic SQL nor NOCHECK bypasses this. Standard DW pattern:
        -- drop the FK, truncate both tables, recreate the FK constraint.
        IF OBJECT_ID('gold.fk_review_comments_fact') IS NOT NULL
            ALTER TABLE gold.review_comments DROP CONSTRAINT fk_review_comments_fact;

        TRUNCATE TABLE gold.review_comments;  -- child
        TRUNCATE TABLE gold.fact_reviews;     -- parent

        -- Recreate FK after truncation
        ALTER TABLE gold.review_comments
            ADD CONSTRAINT fk_review_comments_fact
            FOREIGN KEY (review_sk) REFERENCES gold.fact_reviews (review_sk);

        -- ── Load fact_reviews ─────────────────────────────────────────────────
        INSERT INTO gold.fact_reviews (
            review_creation_date_key,
            review_answer_date_key,
            customer_sk,
            review_id_bk,
            order_id_bk,
            review_score
        )
        SELECT
            -- ── Date Keys ─────────────────────────────────────────────────────
            ISNULL(
                CAST(CONVERT(VARCHAR(8), r.review_creation_date, 112) AS INT),
                19000101
            )                               AS review_creation_date_key,

            -- If customer hasn't answered yet, silver stores '1900-01-01'
            -- Mapped to 99991231 (not yet occurred) not 19000101 (unknown)
            -- because the survey IS open, not a data gap.
            CASE
                WHEN r.review_answer_date = '1900-01-01'
                THEN 99991231
                ELSE CAST(CONVERT(VARCHAR(8), r.review_answer_date, 112) AS INT)
            END                             AS review_answer_date_key,

            -- ── Dimension Lookups ─────────────────────────────────────────────
            ISNULL(dc.customer_sk, -1)      AS customer_sk,

            -- ── Degenerate Dimensions ─────────────────────────────────────────
            r.review_id                     AS review_id_bk,
            r.order_id                      AS order_id_bk,

            -- ── Measure ───────────────────────────────────────────────────────
            r.review_score

        FROM silver.order_reviews AS r

        -- ── Join: resolve order_id → customer_id ─────────────────────────────
        INNER JOIN silver.orders AS o
            ON r.order_id = o.order_id

        -- ── Join: resolve customer_id → customer_unique_id ───────────────────
        INNER JOIN silver.customers AS c
            ON o.customer_id = c.customer_id

        -- ── Lookup: customer_unique_id → customer_sk ─────────────────────────
        LEFT JOIN gold.dim_customer AS dc
            ON c.customer_unique_id = dc.customer_unique_id_bk;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.fact_reviews loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows';

        -- ── Load review_comments (outrigger — same grain as fact_reviews) ─────
        -- Join back to gold.fact_reviews on order_id_bk to get the generated review_sk
        INSERT INTO gold.review_comments (
            review_sk,
            review_comment_title,
            review_comment_message
        )
        SELECT
            fr.review_sk,
            -- Silver uses 'No Title' / 'No message' sentinel strings.
            -- Convert those back to NULL for cleaner outrigger storage.
            NULLIF(r.review_comment_title,   'No Title')    AS review_comment_title,
            NULLIF(r.review_comment_message, 'No message')  AS review_comment_message

        FROM silver.order_reviews AS r

        -- Match the review to its fact row using the order-level BK
        INNER JOIN gold.fact_reviews AS fr
            ON r.order_id = fr.order_id_bk;

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.review_comments loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_fact_reviews: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
