/* ============================================================
   silver_quality_checks.sql
   Database : BI_AI  |  Schema : silver
   Purpose  : Data quality audit of all Silver tables after
              silver.silver_master has been executed.

   Sections:
     1. Row counts (silver vs bronze — expect equal or fewer)
     2. Sample previews (TOP 5 each table)
     3. NULL / sentinel checks on key columns
     4. Transformation validation
        a. Zip code zero-padding
        b. Date casting (no raw strings)
        c. Title Case / categorical mapping
        d. Deduplication effectiveness
     5. Referential integrity (silver cross-table)
   ============================================================ */

USE [BI_AI];
GO

PRINT '============================================================';
PRINT '  Silver Layer Quality Checks';
PRINT '  Run at : ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '============================================================';

/* ============================================================
   1. ROW COUNTS — Silver vs Bronze
      Silver should be ≤ Bronze (deduplication removes dupes)
   ============================================================ */
PRINT '';
PRINT '-- Section 1: Row Counts (Silver vs Bronze) --';

SELECT
    'customers'                     AS table_name,
    (SELECT COUNT(*) FROM bronze.customers)                         AS bronze_rows,
    (SELECT COUNT(*) FROM silver.customers)                         AS silver_rows,
    (SELECT COUNT(*) FROM bronze.customers)
        - (SELECT COUNT(*) FROM silver.customers)                   AS dupes_removed

UNION ALL SELECT
    'orders',
    (SELECT COUNT(*) FROM bronze.orders),
    (SELECT COUNT(*) FROM silver.orders),
    (SELECT COUNT(*) FROM bronze.orders) - (SELECT COUNT(*) FROM silver.orders)

UNION ALL SELECT
    'order_items',
    (SELECT COUNT(*) FROM bronze.order_items),
    (SELECT COUNT(*) FROM silver.order_items),
    (SELECT COUNT(*) FROM bronze.order_items) - (SELECT COUNT(*) FROM silver.order_items)

UNION ALL SELECT
    'order_payments',
    (SELECT COUNT(*) FROM bronze.order_payments),
    (SELECT COUNT(*) FROM silver.order_payments),
    (SELECT COUNT(*) FROM bronze.order_payments) - (SELECT COUNT(*) FROM silver.order_payments)

UNION ALL SELECT
    'order_reviews',
    (SELECT COUNT(*) FROM bronze.order_reviews),
    (SELECT COUNT(*) FROM silver.order_reviews),
    (SELECT COUNT(*) FROM bronze.order_reviews) - (SELECT COUNT(*) FROM silver.order_reviews)

UNION ALL SELECT
    'sellers',
    (SELECT COUNT(*) FROM bronze.sellers),
    (SELECT COUNT(*) FROM silver.sellers),
    (SELECT COUNT(*) FROM bronze.sellers) - (SELECT COUNT(*) FROM silver.sellers)

UNION ALL SELECT
    'products',
    (SELECT COUNT(*) FROM bronze.products),
    (SELECT COUNT(*) FROM silver.products),
    (SELECT COUNT(*) FROM bronze.products) - (SELECT COUNT(*) FROM silver.products)

UNION ALL SELECT
    'marketing_qualified_leads',
    (SELECT COUNT(*) FROM bronze.marketing_qualified_leads),
    (SELECT COUNT(*) FROM silver.marketing_qualified_leads),
    (SELECT COUNT(*) FROM bronze.marketing_qualified_leads) - (SELECT COUNT(*) FROM silver.marketing_qualified_leads)

UNION ALL SELECT
    'closed_deals',
    (SELECT COUNT(*) FROM bronze.closed_deals),
    (SELECT COUNT(*) FROM silver.closed_deals),
    (SELECT COUNT(*) FROM bronze.closed_deals) - (SELECT COUNT(*) FROM silver.closed_deals)

ORDER BY table_name;

/* ============================================================
   2. SAMPLE PREVIEWS — TOP 5 per table
   ============================================================ */
PRINT '';
PRINT '-- Section 2: Sample Previews --';

SELECT TOP 5 * FROM silver.customers          ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.orders             ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.order_items        ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.order_payments     ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.order_reviews      ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.sellers            ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.products           ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.marketing_qualified_leads ORDER BY _processed_at DESC;
SELECT TOP 5 * FROM silver.closed_deals       ORDER BY _processed_at DESC;

/* ============================================================
   3. NULL / SENTINEL CHECKS
      After silver transformation NULLs should be replaced
      by sentinels ('UNKNOWN', '1900-01-01', 0, etc.)
   ============================================================ */
PRINT '';
PRINT '-- Section 3: Unexpected NULLs in Silver --';

-- customers
SELECT 'customers.customer_zip_code_prefix NULL'   AS check_name, COUNT(*) AS cnt FROM silver.customers WHERE customer_zip_code_prefix IS NULL
UNION ALL
SELECT 'customers.customer_city NULL',              COUNT(*) FROM silver.customers WHERE customer_city IS NULL
UNION ALL
-- orders
SELECT 'orders.order_purchase_date NULL',           COUNT(*) FROM silver.orders WHERE order_purchase_date IS NULL
UNION ALL
SELECT 'orders.order_status NULL',                  COUNT(*) FROM silver.orders WHERE order_status IS NULL OR order_status = ''
UNION ALL
-- order_items
SELECT 'order_items.product_id NULL',               COUNT(*) FROM silver.order_items WHERE product_id IS NULL
UNION ALL
SELECT 'order_items.seller_id NULL',                COUNT(*) FROM silver.order_items WHERE seller_id IS NULL
UNION ALL
SELECT 'order_items.unit_price NULL',               COUNT(*) FROM silver.order_items WHERE unit_price IS NULL
UNION ALL
-- order_payments
SELECT 'order_payments.payment_type NULL',          COUNT(*) FROM silver.order_payments WHERE payment_type IS NULL
UNION ALL
SELECT 'order_payments.payment_value NULL',         COUNT(*) FROM silver.order_payments WHERE payment_value IS NULL
UNION ALL
-- order_reviews
SELECT 'order_reviews.review_score NULL',           COUNT(*) FROM silver.order_reviews WHERE review_score IS NULL
UNION ALL
-- sellers
SELECT 'sellers.seller_city NULL',                  COUNT(*) FROM silver.sellers WHERE seller_city IS NULL
UNION ALL
-- products
SELECT 'products.product_category_name NULL',       COUNT(*) FROM silver.products WHERE product_category_name IS NULL
UNION ALL
-- mql
SELECT 'mql.first_contact_date NULL',               COUNT(*) FROM silver.marketing_qualified_leads WHERE first_contact_date IS NULL
UNION ALL
SELECT 'mql.origin NULL',                           COUNT(*) FROM silver.marketing_qualified_leads WHERE origin IS NULL
UNION ALL
-- closed_deals
SELECT 'closed_deals.won_date NULL',                COUNT(*) FROM silver.closed_deals WHERE won_date IS NULL
UNION ALL
SELECT 'closed_deals.business_segment NULL',        COUNT(*) FROM silver.closed_deals WHERE business_segment IS NULL

ORDER BY check_name;

/* ============================================================
   4. TRANSFORMATION VALIDATION
   ============================================================ */
PRINT '';
PRINT '-- Section 4a: Zip Code Zero-Padding (should be LEN = 5) --';

-- customers: any zip not exactly 5 chars?
SELECT 'customers' AS tbl, customer_zip_code_prefix, LEN(customer_zip_code_prefix) AS zip_len
FROM silver.customers
WHERE LEN(customer_zip_code_prefix) <> 5
ORDER BY zip_len;

-- sellers: same check
SELECT 'sellers' AS tbl, seller_zip_code_prefix, LEN(seller_zip_code_prefix) AS zip_len
FROM silver.sellers
WHERE LEN(seller_zip_code_prefix) <> 5
ORDER BY zip_len;

PRINT '';
PRINT '-- Section 4b: Date Columns Are Proper DATEs (not strings) --';

-- orders: date columns data type check (system catalog)
SELECT
    COLUMN_NAME,
    DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'silver'
  AND TABLE_NAME   = 'orders'
  AND COLUMN_NAME LIKE '%date%'
ORDER BY ORDINAL_POSITION;

-- Sentinel date usage — how many rows got the 1900 or 9999 sentinels
SELECT
    'orders: purchase_date = 1900-01-01'          AS sentinel_check, COUNT(*) AS cnt FROM silver.orders WHERE order_purchase_date = '1900-01-01'
UNION ALL SELECT 'orders: carrier_date = 9999-12-31 (in-progress)', COUNT(*) FROM silver.orders WHERE order_delivered_carrier_date  = '9999-12-31'
UNION ALL SELECT 'orders: customer_date = 9999-12-31 (in-progress)',COUNT(*) FROM silver.orders WHERE order_delivered_customer_date = '9999-12-31'
UNION ALL SELECT 'orders: carrier_date = 1900-01-01 (canceled)',    COUNT(*) FROM silver.orders WHERE order_delivered_carrier_date  = '1900-01-01'
UNION ALL SELECT 'reviews: creation_date = 1900-01-01',             COUNT(*) FROM silver.order_reviews WHERE review_creation_date   = '1900-01-01'
UNION ALL SELECT 'reviews: answer_date = 1900-01-01',               COUNT(*) FROM silver.order_reviews WHERE review_answer_date     = '1900-01-01'
UNION ALL SELECT 'closed_deals: won_date = 1900-01-01',             COUNT(*) FROM silver.closed_deals WHERE won_date                = '1900-01-01'
ORDER BY sentinel_check;

PRINT '';
PRINT '-- Section 4c: Categorical Mapping Validation --';

-- orders.order_status: should be lowercase only
SELECT order_status, COUNT(*) AS cnt
FROM silver.orders
GROUP BY order_status
ORDER BY cnt DESC;

-- order_payments.payment_type: should be human-readable labels
SELECT payment_type, COUNT(*) AS cnt
FROM silver.order_payments
GROUP BY payment_type
ORDER BY cnt DESC;

-- mql.origin: should be human-readable labels
SELECT origin, COUNT(*) AS cnt
FROM silver.marketing_qualified_leads
GROUP BY origin
ORDER BY cnt DESC;

-- closed_deals.lead_type
SELECT lead_type, COUNT(*) AS cnt
FROM silver.closed_deals
GROUP BY lead_type
ORDER BY cnt DESC;

-- closed_deals.business_type
SELECT business_type, COUNT(*) AS cnt
FROM silver.closed_deals
GROUP BY business_type
ORDER BY cnt DESC;

-- closed_deals.lead_behaviour_profile
SELECT lead_behaviour_profile, COUNT(*) AS cnt
FROM silver.closed_deals
GROUP BY lead_behaviour_profile
ORDER BY cnt DESC;

-- products.product_category_name: Title Case spot-check
-- Should NOT contain underscores or all-lowercase words
SELECT TOP 20 product_category_name, COUNT(*) AS cnt
FROM silver.products
WHERE product_category_name LIKE '%\_%' ESCAPE '\'   -- underscores still present → bug
   OR product_category_name = product_category_name COLLATE Latin1_General_CS_AS
      AND product_category_name = LOWER(product_category_name)  -- all lowercase → not title-cased
GROUP BY product_category_name
ORDER BY cnt DESC;

-- products: 'Not Specified' categories (no translation found)
SELECT 'products with No Category' AS label, COUNT(*) AS cnt
FROM silver.products
WHERE product_category_name = 'Not Specified';

PRINT '';
PRINT '-- Section 4d: Deduplication — No duplicate PKs in Silver --';

-- customers
SELECT 'customers' AS tbl, COUNT(*) - COUNT(DISTINCT customer_id) AS dup_pk_rows FROM silver.customers
UNION ALL
SELECT 'orders',     COUNT(*) - COUNT(DISTINCT order_id)          FROM silver.orders
UNION ALL
SELECT 'sellers',    COUNT(*) - COUNT(DISTINCT seller_id)         FROM silver.sellers
UNION ALL
SELECT 'products',   COUNT(*) - COUNT(DISTINCT product_id)        FROM silver.products
UNION ALL
SELECT 'mql',        COUNT(*) - COUNT(DISTINCT mql_id)            FROM silver.marketing_qualified_leads
UNION ALL
SELECT 'closed_deals',COUNT(*) - COUNT(DISTINCT mql_id)           FROM silver.closed_deals
UNION ALL
-- Composite PKs
SELECT 'order_items (composite)',
    COUNT(*) - COUNT(DISTINCT CONCAT(order_id,'|', CAST(order_item_id AS VARCHAR)))
FROM silver.order_items
UNION ALL
SELECT 'order_payments (composite)',
    COUNT(*) - COUNT(DISTINCT CONCAT(order_id,'|', CAST(payment_sequential AS VARCHAR)))
FROM silver.order_payments
UNION ALL
-- order_reviews: deduped to one per order_id
SELECT 'order_reviews (per order)',
    COUNT(*) - COUNT(DISTINCT order_id)
FROM silver.order_reviews

ORDER BY tbl;

/* ============================================================
   5. SILVER REFERENTIAL INTEGRITY
      FK chains within the silver layer
   ============================================================ */
PRINT '';
PRINT '-- Section 5: Silver Referential Integrity --';

-- silver orders → silver customers
SELECT
    'silver orders → customers' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.orders o
WHERE NOT EXISTS (
    SELECT 1 FROM silver.customers c WHERE c.customer_id = o.customer_id
);

-- silver order_items → silver orders
SELECT
    'silver order_items → orders' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.order_items oi
WHERE NOT EXISTS (
    SELECT 1 FROM silver.orders o WHERE o.order_id = oi.order_id
);

-- silver order_items.product_id → silver products (exclude UNKNOWN sentinel)
SELECT
    'silver order_items → products (excl UNKNOWN)' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.order_items oi
WHERE oi.product_id <> 'UNKNOWN'
  AND NOT EXISTS (
    SELECT 1 FROM silver.products p WHERE p.product_id = oi.product_id
);

-- silver order_items.seller_id → silver sellers (exclude UNKNOWN sentinel)
SELECT
    'silver order_items → sellers (excl UNKNOWN)' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.order_items oi
WHERE oi.seller_id <> 'UNKNOWN'
  AND NOT EXISTS (
    SELECT 1 FROM silver.sellers s WHERE s.seller_id = oi.seller_id
);

-- silver order_payments → silver orders
SELECT
    'silver order_payments → orders' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.order_payments op
WHERE NOT EXISTS (
    SELECT 1 FROM silver.orders o WHERE o.order_id = op.order_id
);

-- silver order_reviews → silver orders
SELECT
    'silver order_reviews → orders' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.order_reviews r
WHERE NOT EXISTS (
    SELECT 1 FROM silver.orders o WHERE o.order_id = r.order_id
);

-- silver closed_deals → silver mql
SELECT
    'silver closed_deals → mql' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.closed_deals cd
WHERE NOT EXISTS (
    SELECT 1 FROM silver.marketing_qualified_leads m WHERE m.mql_id = cd.mql_id
);

-- silver closed_deals.seller_id → silver sellers
SELECT
    'silver closed_deals → sellers' AS check_name,
    COUNT(*) AS orphan_rows
FROM silver.closed_deals cd
WHERE NOT EXISTS (
    SELECT 1 FROM silver.sellers s WHERE s.seller_id = cd.seller_id
);

PRINT '';
PRINT '============================================================';
PRINT '  Silver Quality Checks Complete';
PRINT '  Finished : ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '============================================================';
