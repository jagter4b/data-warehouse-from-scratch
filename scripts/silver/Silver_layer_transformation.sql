-- customers table cleaning 
WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.customers
)
SELECT
    -- Keys (trim any stray whitespace from source)
    LTRIM(RTRIM(customer_id))                                        AS customer_id,
    LTRIM(RTRIM(customer_unique_id))                                 AS customer_unique_id,

    -- Zip: bigint → CHAR(5) with leading-zero padding
    -- 1151 → '01151',  9790 → '09790',  14409 → '14409'
    RIGHT('00000' + CAST(customer_zip_code_prefix AS VARCHAR(5)), 5) AS customer_zip_code_prefix,

    -- City: uppercase for consistent standardization
    UPPER(LTRIM(RTRIM(customer_city)))                               AS customer_city,

    -- State: already UPPER in source, enforce defensively
    UPPER(LTRIM(RTRIM(customer_state)))                              AS customer_state,

    -- Metadata
    _ingested_at,
    _source,
    GETDATE()                                                        AS _processed_at

FROM deduped
WHERE rn = 1;



-- orders table cleaning 

WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.orders
),
cleaned AS (
    SELECT
        LTRIM(RTRIM(order_id))              AS order_id,
        LTRIM(RTRIM(customer_id))           AS customer_id,
        LOWER(LTRIM(RTRIM(order_status)))   AS order_status,

        -- Purchase & approval: if NULL here it's a data quality gap → '1900-01-01'
        ISNULL(TRY_CAST(order_purchase_timestamp AS DATE), '1900-01-01')
                                            AS order_purchase_date,
        ISNULL(TRY_CAST(order_approved_at AS DATE), '1900-01-01')
                                            AS order_approved_date,

        -- Carrier handoff
        CASE
            WHEN order_delivered_carrier_date IS NOT NULL
                THEN TRY_CAST(order_delivered_carrier_date AS DATE)
            WHEN LOWER(LTRIM(RTRIM(order_status))) IN ('canceled','unavailable')
                THEN CAST('1900-01-01' AS DATE)
            ELSE CAST('9999-12-31' AS DATE)
        END                                 AS order_delivered_carrier_date,

        -- Delivered to customer
        CASE
            WHEN order_delivered_customer_date IS NOT NULL
                THEN TRY_CAST(order_delivered_customer_date AS DATE)
            WHEN LOWER(LTRIM(RTRIM(order_status))) IN ('canceled','unavailable')
                THEN CAST('1900-01-01' AS DATE)
            ELSE CAST('9999-12-31' AS DATE)
        END                                 AS order_delivered_customer_date,

        -- Estimated delivery: always set at purchase, treat gap as data quality issue
        ISNULL(TRY_CAST(order_estimated_delivery_date AS DATE), '1900-01-01')
                                            AS order_estimated_delivery_date,

        _ingested_at,
        _source,
        GETDATE()                           AS _processed_at

    FROM deduped
    WHERE rn = 1
)
SELECT * FROM cleaned;



-- silver.order_items

WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_item_id   -- composite PK
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.order_items
)
SELECT
    -- Composite PK
    LTRIM(RTRIM(order_id))                                          AS order_id,
    order_item_id,                                                  -- sequential: 1,2,3...

    -- FK columns: NULL → 'UNKNOWN' (will map to Unknown dim member in Gold)
    ISNULL(LTRIM(RTRIM(product_id)), 'UNKNOWN')                     AS product_id,
    ISNULL(LTRIM(RTRIM(seller_id)),  'UNKNOWN')                     AS seller_id,

    -- Shipping deadline: varchar → DATE
    -- NULL = data quality gap → 1900-01-01 (no "pending" concept for a deadline)
    ISNULL(TRY_CAST(shipping_limit_date AS DATE), '1900-01-01')     AS shipping_limit_date,

    -- Financials: float → DECIMAL(10,2) for precision, NULL → 0.00
    ISNULL(CAST(price         AS DECIMAL(10, 2)), 0.00)             AS unit_price,
    ISNULL(CAST(freight_value AS DECIMAL(10, 2)), 0.00)             AS unit_freight_value,

    -- Metadata
    _ingested_at,
    _source,
    GETDATE()                                                       AS _processed_at

FROM deduped
WHERE rn = 1;

-- order payments 

WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, payment_sequential  -- composite PK
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.order_payments
)
SELECT
    -- Composite PK
    LTRIM(RTRIM(order_id))      AS order_id,
    payment_sequential,         -- 1, 2, 3... within each order

    -- Payment type: standardize casing, no semantic remapping
    CASE LOWER(LTRIM(RTRIM(payment_type)))
        WHEN 'credit_card'  THEN 'Credit Card'
        WHEN 'debit_card'   THEN 'Debit Card'
        WHEN 'boleto'       THEN 'Boleto'        -- Brazilian bank slip, NOT cash
        WHEN 'voucher'      THEN 'Voucher'
        WHEN 'not_defined'  THEN 'Not Specified'
        ELSE                     'Not Specified' -- NULL or any unexpected value
    END                         AS payment_type,

    -- Installments: meaningful for Credit/Debit Card only
    -- Boleto/Voucher will always be 1 in practice
    -- NULL → 0 (global numeric null rule)
    ISNULL(CAST(payment_installments AS INT), 0)        AS payment_installments,

    -- Payment value: float → DECIMAL(10,2), NULL → 0.00
    ISNULL(CAST(payment_value AS DECIMAL(10, 2)), 0.00) AS payment_value,

    -- Metadata
    _ingested_at,
    _source,
    GETDATE()                                           AS _processed_at

FROM deduped
WHERE rn = 1;


-- sellers transformation silver 
WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY seller_id
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.sellers
)
SELECT
    -- PK
    LTRIM(RTRIM(seller_id))                                          AS seller_id,

    -- Zip: bigint → CHAR(5) with leading-zero padding
    -- 4195 → '04195' | 1529 → '01529' | 1222 → '01222' | 5138 → '05138'
    RIGHT('00000' + CAST(seller_zip_code_prefix AS VARCHAR(5)), 5)   AS seller_zip_code_prefix,

    -- City/State: UPPER + trim + NULL guard
    ISNULL(UPPER(LTRIM(RTRIM(seller_city))),  'Not Specified')       AS seller_city,
    ISNULL(UPPER(LTRIM(RTRIM(seller_state))), 'Not Specified')       AS seller_state,

    -- Metadata
    _ingested_at,
    _source,
    GETDATE()                                                        AS _processed_at

FROM deduped
WHERE rn = 1;




--- produts silver transformation 


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

    -- snake_case → Title Case
    -- bed_bath_table   → Bed Bath Table
    -- cool_stuff       → Cool Stuff
    -- NULL/empty       → Not Specified
    ISNULL(tc.category_title_case, 'Not Specified')     AS product_category_name,

    -- Typo fix + float → INT (counts)
    ISNULL(CAST(p.product_name_lenght        AS INT), 0) AS product_name_length,
    ISNULL(CAST(p.product_description_lenght AS INT), 0) AS product_description_length,
    ISNULL(CAST(p.product_photos_qty         AS INT), 0) AS product_photos_qty,

    -- Physical measurements: float → INT
    ISNULL(CAST(p.product_weight_g           AS INT), 0) AS product_weight_g,
    ISNULL(CAST(p.product_length_cm          AS INT), 0) AS product_length_cm,
    ISNULL(CAST(p.product_height_cm          AS INT), 0) AS product_height_cm,
    ISNULL(CAST(p.product_width_cm           AS INT), 0) AS product_width_cm,

    p._ingested_at,
    p._source,
    GETDATE()                                            AS _processed_at

FROM deduped_products p
LEFT JOIN deduped_translation t
    ON LTRIM(RTRIM(p.product_category_name)) = LTRIM(RTRIM(t.product_category_name))
    AND t.rn = 1

-- Title Case via word-by-word capitalization (order preserved via ordinal)
CROSS APPLY (
    SELECT
        NULLIF(
            STRING_AGG(
                UPPER(LEFT(value, 1)) + LOWER(SUBSTRING(value, 2, LEN(value))),
                ' '
            ) WITHIN GROUP (ORDER BY ordinal),
        '') AS category_title_case
    FROM STRING_SPLIT(
        -- 1. Resolve: English → Portuguese fallback → empty string (never NULL)
        LOWER(REPLACE(
            ISNULL(
                LTRIM(RTRIM(t.product_category_name_english)),
                ISNULL(LTRIM(RTRIM(p.product_category_name)), '')
            ),
        '_', ' ')),   -- 2. Replace underscores with spaces
        ' ', 1        -- 3. Split with ordinal to preserve word order
    )
    WHERE LTRIM(value) <> ''  -- filter empty tokens from double spaces
) AS tc

WHERE p.rn = 1;


-- reviews  silver  transformation 


WITH deduped AS (
    SELECT
        *,
        -- Source PK is (order_id, review_id)
        -- We intentionally collapse to one row per order_id
        -- keeping the review the customer answered most recently
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY TRY_CAST(review_answer_timestamp AS DATE) DESC,
                     _ingested_at DESC   -- tie-break: re-ingestion duplicates
        ) AS rn
    FROM bronze.order_reviews
)
SELECT
    LTRIM(RTRIM(review_id))                                             AS review_id,
    LTRIM(RTRIM(order_id))                                             AS order_id,  -- silver PK

    CAST(review_score AS TINYINT)                                       AS review_score,

    ISNULL(LTRIM(RTRIM(review_comment_title)),   'No Title')       AS review_comment_title,
    ISNULL(LTRIM(RTRIM(review_comment_message)), 'No message')       AS review_comment_message,

    ISNULL(TRY_CAST(review_creation_date    AS DATE), '1900-01-01')    AS review_creation_date,
    ISNULL(TRY_CAST(review_answer_timestamp AS DATE), '1900-01-01')    AS review_answer_date,

    _ingested_at,
    _source,
    GETDATE()                                                           AS _processed_at

FROM deduped
WHERE rn = 1;



-- Silver marketing_qualified_leads; 


WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY mql_id
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.marketing_qualified_leads
)
SELECT
    -- PK
    LTRIM(RTRIM(mql_id))                                        AS mql_id,

    -- Date: already DATE in source, cast defensively
    ISNULL(TRY_CAST(first_contact_date AS DATE), '1900-01-01') AS first_contact_date,

    -- Landing page: opaque hash ID, trim only
    ISNULL(LTRIM(RTRIM(landing_page_id)), 'UNKNOWN')           AS landing_page_id,

    -- Origin: controlled vocabulary → Title Case + unknown/NULL → 'Not Specified'
    CASE LOWER(LTRIM(RTRIM(origin)))
        WHEN 'organic_search'    THEN 'Organic Search'
        WHEN 'paid_search'       THEN 'Paid Search'
        WHEN 'social'            THEN 'Social'
        WHEN 'email'             THEN 'Email'
        WHEN 'referral'          THEN 'Referral'
        WHEN 'display'           THEN 'Display'
        WHEN 'direct_traffic'    THEN 'Direct Traffic'
        ELSE                          'Other'   -- covers: other, other_publicities, unknown, NULL
    END                                                        AS origin,

    -- Metadata: _drive_file_id dropped (bronze ingestion artifact)
    _ingested_at,
    _source,
    GETDATE()                                                  AS _processed_at

FROM deduped
WHERE rn = 1;


--Silver Transformation — silver.closed_deals
WITH deduped AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY mql_id        -- one deal per lead
            ORDER BY _ingested_at DESC
        ) AS rn
    FROM bronze.closed_deals
)
SELECT
    -- Keys
    LTRIM(RTRIM(mql_id))                                            AS mql_id,
    LTRIM(RTRIM(seller_id))                                         AS seller_id,  -- bridge to e-commerce

    -- Internal Olist employee IDs (no dimension table for these)
    ISNULL(LTRIM(RTRIM(sdr_id)), 'UNKNOWN')                         AS sdr_id,
    ISNULL(LTRIM(RTRIM(sr_id)),  'UNKNOWN')                         AS sr_id,

    -- Won date: varchar datetime → DATE
    ISNULL(TRY_CAST(won_date AS DATE), '1900-01-01')                AS won_date,

    -- Business segment: snake_case → Title Case (CROSS APPLY, same as products)
    ISNULL(seg.segment_title_case, 'Not Specified')                 AS business_segment,

    -- Lead type: controlled vocabulary
    CASE LOWER(LTRIM(RTRIM(lead_type)))
        WHEN 'online_big'    THEN 'Online Big'
        WHEN 'online_medium' THEN 'Online Medium'
        WHEN 'online_small'  THEN 'Online Small'
        WHEN 'industry'      THEN 'Industry'
        WHEN 'offline'       THEN 'Offline'
        ELSE                      'Not Specified'
    END                                                             AS lead_type,

    -- Behavioural archetype: controlled vocabulary
    CASE LOWER(LTRIM(RTRIM(lead_behaviour_profile)))
        WHEN 'cat'   THEN 'Cat'
        WHEN 'eagle' THEN 'Eagle'
        WHEN 'wolf'  THEN 'Wolf'
        WHEN 'shark' THEN 'Shark'
        ELSE              'Not Specified'    -- catches NULLs + unexpected values
    END                                                             AS lead_behaviour_profile,

    -- Bit flags: NULL → 0 (not declared = treat as false)
    ISNULL(CAST(has_company AS TINYINT), 0)                         AS has_company,
    ISNULL(CAST(has_gtin    AS TINYINT), 0)                         AS has_gtin,

    -- Average stock: varchar range ("100-500"), not a number → keep as text
    ISNULL(LTRIM(RTRIM(average_stock)), 'Not Specified')            AS average_stock,

    -- Business type: controlled vocabulary
    CASE LOWER(LTRIM(RTRIM(business_type)))
        WHEN 'reseller'     THEN 'Reseller'
        WHEN 'manufacturer' THEN 'Manufacturer'
        WHEN 'others'       THEN 'Other'
        ELSE                     'Not Specified'
    END                                                             AS business_type,

    -- Self-reported numbers: float → DECIMAL(10,2), NULL → 0.00
    ISNULL(CAST(declared_product_catalog_size AS DECIMAL(10,2)), 0.00) AS declared_product_catalog_size,
    ISNULL(CAST(declared_monthly_revenue      AS DECIMAL(10,2)), 0.00) AS declared_monthly_revenue,

    -- Metadata: _drive_file_id dropped
    _ingested_at,
    _source,
    GETDATE()                                                       AS _processed_at

FROM deduped d
-- Business segment: snake_case → Title Case
CROSS APPLY (
    SELECT
        NULLIF(
            STRING_AGG(
                UPPER(LEFT(value, 1)) + LOWER(SUBSTRING(value, 2, LEN(value))),
                ' '
            ) WITHIN GROUP (ORDER BY ordinal),
        '') AS segment_title_case
    FROM STRING_SPLIT(
        LOWER(REPLACE(ISNULL(LTRIM(RTRIM(d.business_segment)), ''), '_', ' ')),
        ' ', 1
    )
    WHERE LTRIM(value) <> ''
) AS seg

WHERE d.rn = 1;
