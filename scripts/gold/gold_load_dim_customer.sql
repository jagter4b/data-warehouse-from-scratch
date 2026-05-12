/* ============================================================
   gold_load_dim_customer.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load silver.customers → gold.dim_customer
   Strategy : MERGE (upsert / SCD Type 1 — overwrite)
   Grain    : One row per customer_unique_id (the TRUE person key)

   SOURCE JOIN PATH (important — two IDs exist in source):
     customer_id        = per-order transient identifier (NOT the dimension key)
     customer_unique_id = the stable person identifier   (THIS is the dim key)
   Both live in silver.customers. Keyed on customer_unique_id.

   IDEMPOTENT: Yes — MERGE handles re-runs safely.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_dim_customer
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_dim_customer ...';

        -- ── Ensure Unknown Member exists (SK = -1) ───────────────────────────
        -- Required for any fact row where customer cannot be resolved.
        -- SET IDENTITY_INSERT allows us to force SK = -1.
        SET IDENTITY_INSERT gold.dim_customer ON;

        MERGE gold.dim_customer AS tgt
        USING (
            SELECT
                -1                  AS customer_sk,
                'UNKNOWN'           AS customer_unique_id_bk,
                '00000'             AS customer_zip_code_prefix,
                'UNKNOWN'           AS customer_city,
                'UN'                AS customer_state
        ) AS src ON tgt.customer_sk = src.customer_sk
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (customer_sk, customer_unique_id_bk, customer_zip_code_prefix,
                    customer_city, customer_state)
            VALUES (src.customer_sk, src.customer_unique_id_bk,
                    src.customer_zip_code_prefix, src.customer_city, src.customer_state);

        SET IDENTITY_INSERT gold.dim_customer OFF;

        -- ── MERGE: silver.customers → gold.dim_customer ───────────────────────
        -- SOURCE: Deduplicate on customer_unique_id to get one row per person.
        -- In silver, customer_id is the partition key (per-order), but
        -- customer_unique_id can appear multiple times across orders.
        -- Takes the most recent record by _processed_at.
        MERGE gold.dim_customer AS tgt
        USING (
            SELECT
                customer_unique_id              AS customer_unique_id_bk,
                customer_zip_code_prefix,
                customer_city,
                customer_state
            FROM (
                SELECT
                    customer_unique_id,
                    customer_zip_code_prefix,
                    customer_city,
                    customer_state,
                    ROW_NUMBER() OVER (
                        PARTITION BY customer_unique_id
                        ORDER BY _processed_at DESC
                    ) AS rn
                FROM silver.customers
            ) AS deduped
            WHERE rn = 1
        ) AS src
            ON tgt.customer_unique_id_bk = src.customer_unique_id_bk

        -- SCD Type 1: UPDATE any changed attributes
        WHEN MATCHED AND (
            tgt.customer_zip_code_prefix <> src.customer_zip_code_prefix OR
            tgt.customer_city            <> src.customer_city            OR
            tgt.customer_state           <> src.customer_state
        ) THEN UPDATE SET
            tgt.customer_zip_code_prefix = src.customer_zip_code_prefix,
            tgt.customer_city            = src.customer_city,
            tgt.customer_state           = src.customer_state,
            tgt.load_timestamp           = GETDATE()

        -- New customer: INSERT
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (
                customer_unique_id_bk,
                customer_zip_code_prefix,
                customer_city,
                customer_state
            )
            VALUES (
                src.customer_unique_id_bk,
                src.customer_zip_code_prefix,
                src.customer_city,
                src.customer_state
            );

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.dim_customer loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows affected in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_dim_customer: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
