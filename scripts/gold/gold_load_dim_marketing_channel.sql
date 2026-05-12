/* ============================================================
   gold_load_dim_marketing_channel.sql
   Database : BI_AI  |  Schema : gold
   Purpose  : Load combined MQL + closed deal data →
              gold.dim_marketing_channel
   Strategy : MERGE (upsert / SCD Type 1)
   Grain    : One row per mql_id

   SOURCE TABLES:
     silver.marketing_qualified_leads  →  origin, landing_page_id
     silver.closed_deals               →  business attributes
                                          (LEFT JOIN — unconverted MQLs
                                          get NULLs for closed_deal cols)

   NOTE: declared_monthly_revenue and declared_product_catalog_size
         are MEASURES → they stay in fact_marketing_funnel only.
         Dimensions must not contain facts.
   ============================================================ */

USE [BI_AI];
GO

CREATE OR ALTER PROCEDURE gold.load_dim_marketing_channel
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @start  DATETIME2 = GETDATE();
    DECLARE @rows   INT;

    BEGIN TRY
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] Starting gold.load_dim_marketing_channel ...';

        -- ── MERGE: combined silver source → gold.dim_marketing_channel ────────
        MERGE gold.dim_marketing_channel AS tgt
        USING (
            -- Every MQL gets a row; only converted MQLs have closed_deal columns
            SELECT
                mql.mql_id              AS mql_id_bk,
                mql.origin,
                mql.landing_page_id,

                -- Closed deal attributes (NULL if MQL did not convert)
                cd.business_segment,
                cd.lead_type,
                cd.lead_behaviour_profile,
                cd.business_type,
                cd.average_stock,
                ISNULL(cd.has_company, 0) AS has_company,
                ISNULL(cd.has_gtin,    0) AS has_gtin

            FROM silver.marketing_qualified_leads AS mql
            LEFT JOIN silver.closed_deals AS cd
                ON mql.mql_id = cd.mql_id
        ) AS src
            ON tgt.mql_id_bk = src.mql_id_bk

        -- SCD Type 1: overwrite on any attribute change
        WHEN MATCHED AND (
            tgt.origin                                   <> src.origin                                    OR
            ISNULL(tgt.landing_page_id,      '')         <> ISNULL(src.landing_page_id,      '')          OR
            ISNULL(tgt.business_segment,     '')         <> ISNULL(src.business_segment,     '')          OR
            ISNULL(tgt.lead_type,            '')         <> ISNULL(src.lead_type,            '')          OR
            ISNULL(tgt.lead_behaviour_profile,'')        <> ISNULL(src.lead_behaviour_profile,'')         OR
            ISNULL(tgt.business_type,        '')         <> ISNULL(src.business_type,        '')          OR
            ISNULL(tgt.average_stock,        '')         <> ISNULL(src.average_stock,        '')          OR
            tgt.has_company                              <> src.has_company                               OR
            tgt.has_gtin                                 <> src.has_gtin
        ) THEN UPDATE SET
            tgt.origin                  = src.origin,
            tgt.landing_page_id         = src.landing_page_id,
            tgt.business_segment        = src.business_segment,
            tgt.lead_type               = src.lead_type,
            tgt.lead_behaviour_profile  = src.lead_behaviour_profile,
            tgt.business_type           = src.business_type,
            tgt.average_stock           = src.average_stock,
            tgt.has_company             = src.has_company,
            tgt.has_gtin                = src.has_gtin,
            tgt.load_timestamp          = GETDATE()

        WHEN NOT MATCHED BY TARGET THEN
            INSERT (
                mql_id_bk,
                origin,
                landing_page_id,
                business_segment,
                lead_type,
                lead_behaviour_profile,
                business_type,
                average_stock,
                has_company,
                has_gtin
            )
            VALUES (
                src.mql_id_bk,
                src.origin,
                src.landing_page_id,
                src.business_segment,
                src.lead_type,
                src.lead_behaviour_profile,
                src.business_type,
                src.average_stock,
                src.has_company,
                src.has_gtin
            );

        SET @rows = @@ROWCOUNT;
        PRINT '>> [' + CONVERT(VARCHAR, GETDATE(), 120) + '] gold.dim_marketing_channel loaded: '
            + CAST(@rows AS VARCHAR(10)) + ' rows affected in '
            + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR(10)) + 's';

    END TRY
    BEGIN CATCH
        PRINT '>> ERROR in gold.load_dim_marketing_channel: ' + ERROR_MESSAGE();
        THROW;
    END CATCH
END;
GO
