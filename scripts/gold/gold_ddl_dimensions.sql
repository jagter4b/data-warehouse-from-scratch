-- =============================================================================
-- FILE    : gold_ddl_dimensions.sql
-- LAYER   : Gold — Kimball Galaxy Schema
-- PURPOSE : DDL for all dimension tables (run before fact tables)
-- SCHEMA  : gold
-- AUTHOR  : ITI Grad Project
-- DATE    : 2026-05-12
--
-- EXECUTION ORDER (dependencies):
--   1. This file  →  all dimensions
--   2. gold_ddl_facts.sql  →  all fact tables + FK constraints
--
-- SURROGATE KEY CONVENTION : <table_name>_sk   (INT IDENTITY — never exposed to source)
-- BUSINESS KEY CONVENTION  : <column_name>_bk  (natural key from source system, degenerate)
-- DATE KEY CONVENTION      : <role_name>_date_key  INT → FK to dim_date.date_key (YYYYMMDD)
-- SENTINEL DATE KEYS       : 19000101 = unknown / missing / past placeholder
--                            99991231 = not yet occurred / open / future placeholder
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'gold')
    EXEC('CREATE SCHEMA gold');
GO

-- =============================================================================
-- DIM_DATE  (Conformed Date Dimension — Role-Playing)
--
-- GRAIN     : One row per calendar day.
-- KEY       : date_key = YYYYMMDD integer (e.g. 20170115 for 2017-01-15).
--             This IS the surrogate key — no IDENTITY needed; the integer IS
--             the semantic key and joins trivially to any date column.
-- SENTINEL  : Row 19000101 = "Unknown / Not Available"
--             Row 99991231 = "Not Yet Occurred / Open"
-- LOAD      : Generated programmatically via a T-SQL date-spine script;
--             never loaded from source.
-- ROLE-PLAY : Each date FK in fact tables has a descriptive alias
--             e.g. purchase_date_key, approval_date_key, won_date_key etc.
--             They all physically reference this single table.
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_date;

CREATE TABLE gold.dim_date (
    -- ── Key ──────────────────────────────────────────────────────────────────
    date_key            INT         NOT NULL,   -- YYYYMMDD integer — PK & natural key
    full_date           DATE        NOT NULL,   -- Actual calendar date

    -- ── Day attributes ───────────────────────────────────────────────────────
    day_of_week_num     TINYINT     NOT NULL,   -- 1=Monday … 7=Sunday (ISO)
    day_of_week_name    VARCHAR(10) NOT NULL,   -- 'Monday', 'Tuesday' …
    day_of_week_name_short CHAR(3)  NOT NULL,   -- 'Mon', 'Tue' …
    day_of_month        TINYINT     NOT NULL,   -- 1–31
    day_of_year         SMALLINT    NOT NULL,   -- 1–366

    -- ── Week attributes ──────────────────────────────────────────────────────
    week_of_year        TINYINT     NOT NULL,   -- ISO week number 1–53

    -- ── Month attributes ─────────────────────────────────────────────────────
    month_num           TINYINT     NOT NULL,   -- 1–12
    month_name          VARCHAR(10) NOT NULL,   -- 'January' …
    month_name_short    CHAR(3)     NOT NULL,   -- 'Jan' …

    -- ── Quarter attributes ───────────────────────────────────────────────────
    quarter_num         TINYINT     NOT NULL,   -- 1–4
    quarter_name        CHAR(2)     NOT NULL,   -- 'Q1'–'Q4'

    -- ── Year attributes ──────────────────────────────────────────────────────
    [year]              SMALLINT    NOT NULL,   -- e.g. 2017
    year_month          CHAR(7)     NOT NULL,   -- 'YYYY-MM' for month-level slicing

    -- ── Flags ────────────────────────────────────────────────────────────────
    is_weekend          BIT         NOT NULL,   -- 1 = Saturday or Sunday
    is_holiday          BIT         NOT NULL DEFAULT 0,  -- placeholder; update for BR holidays

    CONSTRAINT pk_dim_date PRIMARY KEY (date_key)
);

-- Unique constraint on the calendar date itself (used during ETL lookups)
CREATE UNIQUE INDEX uix_dim_date_full_date ON gold.dim_date (full_date);

GO

-- =============================================================================
-- DIM_CUSTOMER
--
-- GRAIN     : One row per UNIQUE customer (customer_unique_id).
-- SCD TYPE  : 1 (overwrite — no history needed for this project).
-- KEY NOTES :
--   • customer_unique_id_bk = the TRUE person identifier (the BK modeled on).
--   • customer_id            = a per-ORDER transient ID that lives only in the
--                              orders table; it is NOT stored here.
--   • ETL join path for fact tables:
--       silver.orders.customer_id
--           → silver.customers.customer_unique_id
--               → gold.dim_customer.customer_unique_id_bk
--               → gold.dim_customer.customer_sk   (FK stored in fact)
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_customer;

CREATE TABLE gold.dim_customer (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    customer_sk             INT         NOT NULL IDENTITY(1,1),

    -- ── Business Key (degenerate dim / natural key) ───────────────────────────
    customer_unique_id_bk   VARCHAR(32) NOT NULL,  -- hashed UUID from source

    -- ── Descriptive Attributes ───────────────────────────────────────────────
    customer_zip_code_prefix CHAR(5)    NOT NULL,
    customer_city           VARCHAR(50) NOT NULL,
    customer_state          CHAR(2)     NOT NULL,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2   NOT NULL DEFAULT GETDATE(),
    source_system           VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_sk)
);

CREATE UNIQUE INDEX uix_dim_customer_bk ON gold.dim_customer (customer_unique_id_bk);

GO

-- =============================================================================
-- DIM_PRODUCT
--
-- GRAIN     : One row per product.
-- SCD TYPE  : 1 (overwrite).
-- NOTES     : Physical dimensions are INT (silver already cast float → INT).
--             Category name is English title-case from silver transformation.
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_product;

CREATE TABLE gold.dim_product (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    product_sk                  INT         NOT NULL IDENTITY(1,1),

    -- ── Business Key ─────────────────────────────────────────────────────────
    product_id_bk               VARCHAR(32) NOT NULL,  -- hashed UUID from source

    -- ── Descriptive Attributes ───────────────────────────────────────────────
    product_category_name       VARCHAR(100) NOT NULL DEFAULT 'Not Specified',
    product_name_length         INT          NULL,     -- char count; NULL = not provided
    product_description_length  INT          NULL,
    product_photos_qty          INT          NULL,

    -- Physical measurements (stored as INT per silver transformation)
    product_weight_g            INT          NULL,
    product_length_cm           INT          NULL,
    product_height_cm           INT          NULL,
    product_width_cm            INT          NULL,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp              DATETIME2    NOT NULL DEFAULT GETDATE(),
    source_system               VARCHAR(20)  NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_dim_product PRIMARY KEY (product_sk)
);

CREATE UNIQUE INDEX uix_dim_product_bk ON gold.dim_product (product_id_bk);

GO

-- =============================================================================
-- DIM_SELLER
--
-- GRAIN     : One row per seller.
-- SCD TYPE  : 1 (overwrite).
-- NOTE      : dim_seller is shared between e-commerce (fact_order_items)
--             and marketing funnel (fact_marketing_funnel). The seller_id_bk
--             is the bridge between the two subject areas.
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_seller;

CREATE TABLE gold.dim_seller (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    seller_sk               INT         NOT NULL IDENTITY(1,1),

    -- ── Business Key ─────────────────────────────────────────────────────────
    seller_id_bk            VARCHAR(32) NOT NULL,  -- hashed UUID from source

    -- ── Descriptive Attributes ───────────────────────────────────────────────
    seller_zip_code_prefix  CHAR(5)     NOT NULL,
    seller_city             VARCHAR(50) NOT NULL,
    seller_state            CHAR(2)     NOT NULL,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2   NOT NULL DEFAULT GETDATE(),
    source_system           VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_dim_seller PRIMARY KEY (seller_sk)
);

CREATE UNIQUE INDEX uix_dim_seller_bk ON gold.dim_seller (seller_id_bk);

GO

-- =============================================================================
-- DIM_PAYMENT_TYPE  (Static Lookup)
--
-- GRAIN     : One row per payment method.
-- SCD TYPE  : Static — values never change; loaded once via INSERT seeds.
-- SEED DATA :
--   1 = 'Credit Card'
--   2 = 'Debit Card'
--   3 = 'Boleto'
--   4 = 'Voucher'
--   5 = 'Not Specified'
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_payment_type;

CREATE TABLE gold.dim_payment_type (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    payment_type_sk     INT         NOT NULL IDENTITY(1,1),

    -- ── Business Key / Descriptive Value ─────────────────────────────────────
    payment_type        VARCHAR(20) NOT NULL,  -- 'Credit Card', 'Boleto', etc.

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp      DATETIME2   NOT NULL DEFAULT GETDATE(),
    source_system       VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_dim_payment_type PRIMARY KEY (payment_type_sk)
);

CREATE UNIQUE INDEX uix_dim_payment_type ON gold.dim_payment_type (payment_type);

GO

-- Seed static values (idempotent — only inserts if not present)
INSERT INTO gold.dim_payment_type (payment_type)
SELECT v.payment_type
FROM (VALUES
    ('Credit Card'),
    ('Debit Card'),
    ('Boleto'),
    ('Voucher'),
    ('Not Specified')
) AS v(payment_type)
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_payment_type WHERE payment_type = v.payment_type
);

GO

-- =============================================================================
-- DIM_ORDER_STATUS  (Static Lookup)
--
-- GRAIN     : One row per order status value.
-- SCD TYPE  : Static — values never change; loaded once via INSERT seeds.
-- SEED DATA :
--   Values from silver: created, approved, invoiced, processing,
--                       shipped, delivered, canceled, unavailable
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_order_status;

CREATE TABLE gold.dim_order_status (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    order_status_sk     INT         NOT NULL IDENTITY(1,1),

    -- ── Business Key / Descriptive Value ─────────────────────────────────────
    order_status        VARCHAR(20) NOT NULL,  -- lowercase as stored in silver

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp      DATETIME2   NOT NULL DEFAULT GETDATE(),
    source_system       VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_dim_order_status PRIMARY KEY (order_status_sk)
);

CREATE UNIQUE INDEX uix_dim_order_status ON gold.dim_order_status (order_status);

GO

-- Seed static values
INSERT INTO gold.dim_order_status (order_status)
SELECT v.order_status
FROM (VALUES
    ('created'),
    ('approved'),
    ('invoiced'),
    ('processing'),
    ('shipped'),
    ('delivered'),
    ('canceled'),
    ('unavailable')
) AS v(order_status)
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_order_status WHERE order_status = v.order_status
);

GO

-- =============================================================================
-- DIM_MARKETING_CHANNEL
--
-- GRAIN     : One row per Marketing Qualified Lead (MQL).
-- SCD TYPE  : 1 (overwrite).
-- SOURCE    : Merged from two silver tables:
--               • silver.marketing_qualified_leads  → origin, landing_page_id
--               • silver.closed_deals               → all business/lead attributes
--             Only MQLs that converted (have a closed_deal record) will have
--             full attribute population; unconverted MQLs get NULLs for the
--             closed_deals columns.
-- NOTE      : The declared financials (declared_monthly_revenue,
--             declared_product_catalog_size) are stored in fact_marketing_funnel
--             as measures, NOT here. Dimensions should not contain facts.
-- FK NOTE   : fact_marketing_funnel.mql_channel_sk → dim_marketing_channel.mql_channel_sk
-- =============================================================================
DROP TABLE IF EXISTS gold.dim_marketing_channel;

CREATE TABLE gold.dim_marketing_channel (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    mql_channel_sk          INT          NOT NULL IDENTITY(1,1),

    -- ── Business Key ─────────────────────────────────────────────────────────
    mql_id_bk               VARCHAR(32)  NOT NULL,  -- hashed UUID from source

    -- ── MQL Attributes (from silver.marketing_qualified_leads) ───────────────
    origin                  VARCHAR(30)  NOT NULL,  -- 'Organic Search', 'Paid Search', etc.
    landing_page_id         VARCHAR(32)  NULL,      -- opaque hash; NULL if not captured

    -- ── Closed Deal Attributes (from silver.closed_deals; NULL if not converted) ──
    business_segment        VARCHAR(60)  NULL,      -- e.g. 'Pet Shop', 'Construction'
    lead_type               VARCHAR(20)  NULL,      -- 'Online Big', 'Offline', etc.
    lead_behaviour_profile  VARCHAR(20)  NULL,      -- 'Cat', 'Eagle', 'Wolf', 'Shark'
    business_type           VARCHAR(20)  NULL,      -- 'Reseller', 'Manufacturer', 'Other'
    average_stock           VARCHAR(20)  NULL,      -- text range, e.g. '100-500'
    has_company             TINYINT      NOT NULL DEFAULT 0,  -- 0/1 flag
    has_gtin                TINYINT      NOT NULL DEFAULT 0,  -- 0/1 flag (GTIN = barcode)

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2    NOT NULL DEFAULT GETDATE(),
    source_system           VARCHAR(20)  NOT NULL DEFAULT 'olist_marketing',

    CONSTRAINT pk_dim_marketing_channel PRIMARY KEY (mql_channel_sk)
);

CREATE UNIQUE INDEX uix_dim_marketing_channel_bk ON gold.dim_marketing_channel (mql_id_bk);

GO

-- =============================================================================
-- REVIEW_COMMENTS  (Outrigger Table — linked to fact_reviews)
--
-- GRAIN     : One row per review (same grain as fact_reviews).
-- PURPOSE   : Stores long free-text columns that would bloat the fact table
--             and harm columnstore compression. Separated as an outrigger.
-- PK / FK   : review_sk is BOTH the PK of this table AND a FK to
--             fact_reviews.review_sk — a 1:1 relationship.
-- NOTE      : NVARCHAR used for Portuguese Unicode text support.
-- =============================================================================
DROP TABLE IF EXISTS gold.review_comments;

CREATE TABLE gold.review_comments (
    -- ── Key (mirrors fact_reviews PK — no IDENTITY here) ─────────────────────
    review_sk               INT           NOT NULL,  -- FK to fact_reviews.review_sk

    -- ── Text Attributes ───────────────────────────────────────────────────────
    review_comment_title    NVARCHAR(200) NULL,      -- NULL if no title left by customer
    review_comment_message  NVARCHAR(1000) NULL,     -- NULL if no message left

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2     NOT NULL DEFAULT GETDATE(),

    CONSTRAINT pk_review_comments PRIMARY KEY (review_sk)
    -- FK to fact_reviews added in gold_ddl_facts.sql (fact created after this file)
);

GO
