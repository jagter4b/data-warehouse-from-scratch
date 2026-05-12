-- =============================================================================
-- FILE    : gold_ddl_facts.sql
-- LAYER   : Gold — Kimball Galaxy Schema
-- PURPOSE : DDL for all fact tables + FK constraints (run after dimensions)
-- SCHEMA  : gold
-- AUTHOR  : ITI Grad Project
-- DATE    : 2026-05-12
--
-- EXECUTION ORDER:
--   1. gold_ddl_dimensions.sql  (all dimensions must exist first)
--   2. This file                (fact tables + all FK constraints)
--
-- SURROGATE KEY CONVENTION : <table>_sk    (INT IDENTITY — DW-only key)
-- BUSINESS KEY CONVENTION  : <column>_bk   (natural key kept as degenerate dim)
-- DATE FK CONVENTION       : <role>_date_key INT → gold.dim_date.date_key (YYYYMMDD)
-- SENTINEL DATE KEYS       : 19000101 = unknown / missing past date
--                            99991231 = not yet occurred / open future date
-- =============================================================================

-- =============================================================================
-- FACT_ORDER_ITEMS  (Transactional Fact)
--
-- GRAIN     : One row per ORDER LINE ITEM.
--             Identified by the composite business key (order_id, order_item_id).
--             One order → one or more rows here (one per item purchased).
--
-- DIMENSIONS:
--   purchase_date_key      → dim_date   (order-level date; same for all items in order)
--   shipping_limit_date_key→ dim_date   (item-level shipping deadline — different per item)
--   customer_sk            → dim_customer
--   product_sk             → dim_product
--   seller_sk              → dim_seller
--
-- DEGENERATE DIMS (business keys stored directly — no separate dimension table):
--   order_id_bk            VARCHAR(32)  — the order identifier
--   order_item_id_bk       INT          — sequential position within the order (1,2,3…)
--
-- MEASURES (additive):
--   unit_price             — price of the single item
--   unit_freight_value     — freight cost allocated to this single item
--
-- DERIVED MEASURE:
--   line_total             — unit_price + unit_freight_value (persisted for convenience)
--
-- ETL JOIN PATH FOR customer_sk:
--   silver.order_items.order_id
--     → silver.orders.customer_id
--         → silver.customers.customer_unique_id
--             → gold.dim_customer.customer_unique_id_bk → customer_sk
-- =============================================================================
DROP TABLE IF EXISTS gold.fact_order_items;

CREATE TABLE gold.fact_order_items (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    order_item_sk           INT             NOT NULL IDENTITY(1,1),

    -- ── Date Foreign Keys (role-played aliases → dim_date.date_key) ──────────
    purchase_date_key       INT             NOT NULL,  -- order purchase timestamp (order-level)
    shipping_limit_date_key INT             NOT NULL,  -- item shipping deadline (item-level)
                                                       -- sentinel 19000101 if NULL in source

    -- ── Dimension Foreign Keys ────────────────────────────────────────────────
    customer_sk             INT             NOT NULL,  -- resolved via order_id → customer_unique_id
    product_sk              INT             NOT NULL,  -- -1 / Unknown row if product missing
    seller_sk               INT             NOT NULL,  -- -1 / Unknown row if seller missing

    -- ── Degenerate Dimensions (Business Keys) ─────────────────────────────────
    order_id_bk             VARCHAR(32)     NOT NULL,  -- order natural key
    order_item_id_bk        INT             NOT NULL,  -- sequential item position within order

    -- ── Measures (all additive) ───────────────────────────────────────────────
    unit_price              DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    unit_freight_value      DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,

    -- ── Derived Measure (persisted — avoid repeated expression in queries) ────
    line_total              AS (unit_price + unit_freight_value) PERSISTED,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2       NOT NULL DEFAULT GETDATE(),
    source_system           VARCHAR(20)     NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_fact_order_items PRIMARY KEY (order_item_sk)
);

-- Natural business key uniqueness (composite degenerate dim)
CREATE UNIQUE INDEX uix_fact_order_items_bk
    ON gold.fact_order_items (order_id_bk, order_item_id_bk);

-- Supporting indexes for common join patterns
CREATE INDEX ix_fact_order_items_customer    ON gold.fact_order_items (customer_sk);
CREATE INDEX ix_fact_order_items_product     ON gold.fact_order_items (product_sk);
CREATE INDEX ix_fact_order_items_seller      ON gold.fact_order_items (seller_sk);
CREATE INDEX ix_fact_order_items_purdate     ON gold.fact_order_items (purchase_date_key);

GO

-- =============================================================================
-- FACT_PAYMENTS  (Transactional Fact)
--
-- GRAIN     : One row per PAYMENT SEQUENCE LINE within an order.
--             A single order can have MULTIPLE rows here if paid by multiple
--             methods (e.g. Credit Card + Voucher = 2 rows for 1 order).
--             The composite business key is (order_id, payment_sequential).
--
-- EXAMPLE   :
--   order_id_bk = 'abc123',  payment_sequential_bk = 1, payment_type = 'Voucher',   value = 50.00
--   order_id_bk = 'abc123',  payment_sequential_bk = 2, payment_type = 'Credit Card', value = 120.00
--
-- DIMENSIONS:
--   purchase_date_key  → dim_date       (order-level purchase date)
--   customer_sk        → dim_customer
--   payment_type_sk    → dim_payment_type
--
-- CUSTOMER JOIN NOTE:
--   silver.order_payments has NO customer column.
--   ETL must resolve:  order_id_bk
--     → silver.orders.customer_id
--         → silver.customers.customer_unique_id
--             → gold.dim_customer.customer_unique_id_bk → customer_sk
--
-- DEGENERATE DIMS:
--   order_id_bk           — the order this payment belongs to
--   payment_sequential_bk — sequence number of this payment line (1,2,3…)
--
-- MEASURES:
--   payment_value        — amount paid in this payment sequence line
--   payment_installments — number of installments (credit card feature; others = 1)
-- =============================================================================
DROP TABLE IF EXISTS gold.fact_payments;

CREATE TABLE gold.fact_payments (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    payment_sk              INT             NOT NULL IDENTITY(1,1),

    -- ── Date Foreign Keys ─────────────────────────────────────────────────────
    purchase_date_key       INT             NOT NULL,  -- order-level purchase date

    -- ── Dimension Foreign Keys ────────────────────────────────────────────────
    customer_sk             INT             NOT NULL,  -- resolved via order_id (see ETL note)
    payment_type_sk         INT             NOT NULL,  -- Credit Card / Boleto / Voucher etc.

    -- ── Degenerate Dimensions (Business Keys) ─────────────────────────────────
    order_id_bk             VARCHAR(32)     NOT NULL,  -- order natural key
    payment_sequential_bk   INT             NOT NULL,  -- payment line sequence within order

    -- ── Measures ──────────────────────────────────────────────────────────────
    payment_value           DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    payment_installments    INT             NOT NULL DEFAULT 1,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp          DATETIME2       NOT NULL DEFAULT GETDATE(),
    source_system           VARCHAR(20)     NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_fact_payments PRIMARY KEY (payment_sk)
);

-- Natural business key (one payment line per sequence per order)
CREATE UNIQUE INDEX uix_fact_payments_bk
    ON gold.fact_payments (order_id_bk, payment_sequential_bk);

CREATE INDEX ix_fact_payments_customer     ON gold.fact_payments (customer_sk);
CREATE INDEX ix_fact_payments_purdate      ON gold.fact_payments (purchase_date_key);
CREATE INDEX ix_fact_payments_paytype      ON gold.fact_payments (payment_type_sk);

GO

-- =============================================================================
-- FACT_REVIEWS  (Transactional Fact)
--
-- GRAIN     : One row per ORDER REVIEW.
--             Silver already deduplicates to one review per order_id.
--             Each row represents a customer's satisfaction rating on their order.
--
-- DIMENSIONS:
--   review_creation_date_key → dim_date   (when the review survey was sent)
--   review_answer_date_key   → dim_date   (when the customer submitted the review)
--   customer_sk              → dim_customer
--
-- OUTRIGGER:
--   review_comments          → joined on review_sk (1:1)
--                              Contains free-text title + message.
--                              Separated to protect columnstore compression
--                              from large NVARCHAR columns.
--
-- DEGENERATE DIMS:
--   review_id_bk   — original review UUID from source
--   order_id_bk    — the order this review is for (bridge to fact_order_items)
--
-- MEASURE:
--   review_score   — 1–5 integer rating (TINYINT)
-- =============================================================================
DROP TABLE IF EXISTS gold.fact_reviews;

CREATE TABLE gold.fact_reviews (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    review_sk                   INT         NOT NULL IDENTITY(1,1),

    -- ── Date Foreign Keys ─────────────────────────────────────────────────────
    review_creation_date_key    INT         NOT NULL,  -- date survey was sent to customer
    review_answer_date_key      INT         NOT NULL,  -- date customer submitted response
                                                       -- sentinel 99991231 if not yet answered

    -- ── Dimension Foreign Keys ────────────────────────────────────────────────
    customer_sk                 INT         NOT NULL,  -- resolved via order_id → customer_unique_id

    -- ── Degenerate Dimensions (Business Keys) ─────────────────────────────────
    review_id_bk                VARCHAR(32) NOT NULL,  -- original review UUID
    order_id_bk                 VARCHAR(32) NOT NULL,  -- order this review belongs to

    -- ── Measure ───────────────────────────────────────────────────────────────
    review_score                TINYINT     NOT NULL,  -- 1–5 customer satisfaction score

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp              DATETIME2   NOT NULL DEFAULT GETDATE(),
    source_system               VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_fact_reviews PRIMARY KEY (review_sk)
);

CREATE UNIQUE INDEX uix_fact_reviews_bk
    ON gold.fact_reviews (order_id_bk);  -- one review per order (silver grain)

CREATE INDEX ix_fact_reviews_customer       ON gold.fact_reviews (customer_sk);
CREATE INDEX ix_fact_reviews_creation_date  ON gold.fact_reviews (review_creation_date_key);
CREATE INDEX ix_fact_reviews_answer_date    ON gold.fact_reviews (review_answer_date_key);

GO

-- =============================================================================
-- FACT_ORDER_LIFE_CYCLE  (Accumulating Snapshot Fact)
--
-- GRAIN     : One row per ORDER (not per item).
--             Row is INSERTED when an order is first seen and
--             UPDATED as each milestone date is reached.
--
-- DATE FKs  : Five date milestones, all role-playing dim_date.
--             Sentinel 99991231 is used for milestones not yet reached.
--             Sentinel 19000101 is used for data quality gaps.
--
-- DIMENSIONS:
--   purchase_date_key          → dim_date  (order placed)
--   approval_date_key          → dim_date  (order approved / payment confirmed)
--   carrier_date_key           → dim_date  (handed to carrier)
--   delivery_date_key          → dim_date  (delivered to customer)
--   estimated_delivery_date_key→ dim_date  (originally promised delivery date)
--   customer_sk                → dim_customer
--   order_status_sk            → dim_order_status  (current status snapshot)
--
-- DEGENERATE DIM:
--   order_id_bk    — order natural key (unique — one row per order)
--
-- MEASURES:
--   Lag measures (computed during ETL from date differences):
--     days_to_approve            — purchase → approval
--     days_to_ship               — approval → carrier handoff
--     days_to_deliver            — carrier  → customer delivery
--     days_purchase_to_delivery  — purchase → customer delivery (total span)
--     days_delivery_variance     — actual delivery − estimated delivery (negative = early)
--     is_delivered_on_time       — BIT flag (1 = delivered on or before estimated)
--
--   Summary measures (aggregated from child fact tables during ETL):
--     total_items                — COUNT of order_item_id rows for this order
--     total_distinct_products    — COUNT DISTINCT products
--     total_distinct_sellers     — COUNT DISTINCT sellers
--     total_order_value          — SUM of unit_price from fact_order_items
--     total_freight_value        — SUM of unit_freight_value from fact_order_items
--     total_payment_value        — SUM of payment_value from fact_payments
-- =============================================================================
DROP TABLE IF EXISTS gold.fact_order_life_cycle;

CREATE TABLE gold.fact_order_life_cycle (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    order_fulfillment_sk            INT             NOT NULL IDENTITY(1,1),

    -- ── Date Foreign Keys (role-playing dim_date) ─────────────────────────────
    purchase_date_key               INT             NOT NULL,  -- order placed
    approval_date_key               INT             NOT NULL,  -- payment approved
    carrier_date_key                INT             NOT NULL,  -- handed to carrier
    delivery_date_key               INT             NOT NULL,  -- delivered to customer
    estimated_delivery_date_key     INT             NOT NULL,  -- promised delivery date

    -- ── Dimension Foreign Keys ────────────────────────────────────────────────
    customer_sk                     INT             NOT NULL,
    order_status_sk                 INT             NOT NULL,  -- final/current order status

    -- ── Degenerate Dimension ──────────────────────────────────────────────────
    order_id_bk                     VARCHAR(32)     NOT NULL,  -- order natural key (unique here)

    -- ── Lag / Duration Measures ───────────────────────────────────────────────
    days_to_approve                 INT             NULL,  -- NULL if approval not yet occurred
    days_to_ship                    INT             NULL,  -- NULL if not yet shipped
    days_to_deliver                 INT             NULL,  -- NULL if not yet delivered
    days_purchase_to_delivery       INT             NULL,  -- NULL if not yet delivered
    days_delivery_variance          INT             NULL,  -- negative = early; positive = late
    is_delivered_on_time            BIT             NULL,  -- NULL if not yet delivered

    -- ── Summary Measures (aggregated from item/payment facts) ─────────────────
    total_items                     INT             NOT NULL DEFAULT 0,
    total_distinct_products         INT             NOT NULL DEFAULT 0,
    total_distinct_sellers          INT             NOT NULL DEFAULT 0,
    total_order_value               DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    total_freight_value             DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,
    total_payment_value             DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp                  DATETIME2       NOT NULL DEFAULT GETDATE(),
    source_system                   VARCHAR(20)     NOT NULL DEFAULT 'olist_ecommerce',

    CONSTRAINT pk_fact_order_life_cycle PRIMARY KEY (order_fulfillment_sk)
);

CREATE UNIQUE INDEX uix_fact_order_life_cycle_bk
    ON gold.fact_order_life_cycle (order_id_bk);  -- one row per order (snapshot grain)

CREATE INDEX ix_folc_customer          ON gold.fact_order_life_cycle (customer_sk);
CREATE INDEX ix_folc_status            ON gold.fact_order_life_cycle (order_status_sk);
CREATE INDEX ix_folc_purchase_date     ON gold.fact_order_life_cycle (purchase_date_key);
CREATE INDEX ix_folc_delivery_date     ON gold.fact_order_life_cycle (delivery_date_key);
CREATE INDEX ix_folc_est_delivery_date ON gold.fact_order_life_cycle (estimated_delivery_date_key);

GO

-- =============================================================================
-- FACT_MARKETING_FUNNEL  (Transactional Fact)
--
-- GRAIN     : One row per CLOSED DEAL (successfully converted MQL → Seller).
--             Only MQLs that appear in silver.closed_deals are here.
--
-- DIMENSIONS:
--   first_contact_date_key → dim_date              (when MQL first contacted Olist)
--   won_date_key           → dim_date              (when deal was closed / seller onboarded)
--   seller_sk              → dim_seller            (the seller who was onboarded)
--   mql_channel_sk         → dim_marketing_channel (the lead that was converted)
--
-- DEGENERATE DIMS:
--   mql_id_bk    — MQL natural key
--   sdr_id_bk    — Sales Dev Rep internal ID (no dimension; no descriptive attributes)
--   sr_id_bk     — Sales Rep internal ID    (no dimension; no descriptive attributes)
--
-- MEASURES:
--   days_to_close                  — first_contact_date → won_date duration
--   declared_monthly_revenue       — self-reported by the new seller (financial measure)
--   declared_product_catalog_size  — self-reported catalog count
-- =============================================================================
DROP TABLE IF EXISTS gold.fact_marketing_funnel;

CREATE TABLE gold.fact_marketing_funnel (
    -- ── Surrogate Key ─────────────────────────────────────────────────────────
    closed_deal_sk                  INT             NOT NULL IDENTITY(1,1),

    -- ── Date Foreign Keys (role-playing dim_date) ─────────────────────────────
    first_contact_date_key          INT             NOT NULL,  -- MQL first contact date
    won_date_key                    INT             NOT NULL,  -- deal closed / seller onboarded

    -- ── Dimension Foreign Keys ────────────────────────────────────────────────
    seller_sk                       INT             NOT NULL,  -- the seller that was onboarded
    mql_channel_sk                  INT             NOT NULL,  -- the lead's marketing channel

    -- ── Degenerate Dimensions (Business Keys) ─────────────────────────────────
    mql_id_bk                       VARCHAR(32)     NOT NULL,  -- MQL natural key (unique)
    sdr_id_bk                       VARCHAR(32)     NULL,      -- Sales Dev Rep ID (internal)
    sr_id_bk                        VARCHAR(32)     NULL,      -- Sales Rep ID (internal)

    -- ── Measures ──────────────────────────────────────────────────────────────
    days_to_close                   INT             NULL,      -- NULL if dates were missing
    declared_monthly_revenue        DECIMAL(15, 2)  NOT NULL DEFAULT 0.00,
    declared_product_catalog_size   DECIMAL(10, 2)  NOT NULL DEFAULT 0.00,

    -- ── Metadata ─────────────────────────────────────────────────────────────
    load_timestamp                  DATETIME2       NOT NULL DEFAULT GETDATE(),
    source_system                   VARCHAR(20)     NOT NULL DEFAULT 'olist_marketing',

    CONSTRAINT pk_fact_marketing_funnel PRIMARY KEY (closed_deal_sk)
);

CREATE UNIQUE INDEX uix_fact_marketing_funnel_bk
    ON gold.fact_marketing_funnel (mql_id_bk);  -- one deal per MQL

CREATE INDEX ix_fmf_seller         ON gold.fact_marketing_funnel (seller_sk);
CREATE INDEX ix_fmf_channel        ON gold.fact_marketing_funnel (mql_channel_sk);
CREATE INDEX ix_fmf_first_contact  ON gold.fact_marketing_funnel (first_contact_date_key);
CREATE INDEX ix_fmf_won_date       ON gold.fact_marketing_funnel (won_date_key);

GO

-- =============================================================================
-- FOREIGN KEY CONSTRAINTS
-- All FK constraints declared here (after all tables exist).
-- Pattern: fact table → dimension table  (NEVER dimension → fact)
-- =============================================================================

-- ── dim_date role-playing FKs ─────────────────────────────────────────────────

-- fact_order_items → dim_date
ALTER TABLE gold.fact_order_items
    ADD CONSTRAINT fk_foi_purchase_date
    FOREIGN KEY (purchase_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_order_items
    ADD CONSTRAINT fk_foi_shipping_limit_date
    FOREIGN KEY (shipping_limit_date_key) REFERENCES gold.dim_date (date_key);

-- fact_payments → dim_date
ALTER TABLE gold.fact_payments
    ADD CONSTRAINT fk_fp_purchase_date
    FOREIGN KEY (purchase_date_key) REFERENCES gold.dim_date (date_key);

-- fact_reviews → dim_date
ALTER TABLE gold.fact_reviews
    ADD CONSTRAINT fk_fr_creation_date
    FOREIGN KEY (review_creation_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_reviews
    ADD CONSTRAINT fk_fr_answer_date
    FOREIGN KEY (review_answer_date_key) REFERENCES gold.dim_date (date_key);

-- fact_order_life_cycle → dim_date (5 date roles)
ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_purchase_date
    FOREIGN KEY (purchase_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_approval_date
    FOREIGN KEY (approval_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_carrier_date
    FOREIGN KEY (carrier_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_delivery_date
    FOREIGN KEY (delivery_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_estimated_delivery_date
    FOREIGN KEY (estimated_delivery_date_key) REFERENCES gold.dim_date (date_key);

-- fact_marketing_funnel → dim_date (2 date roles)
ALTER TABLE gold.fact_marketing_funnel
    ADD CONSTRAINT fk_fmf_first_contact_date
    FOREIGN KEY (first_contact_date_key) REFERENCES gold.dim_date (date_key);

ALTER TABLE gold.fact_marketing_funnel
    ADD CONSTRAINT fk_fmf_won_date
    FOREIGN KEY (won_date_key) REFERENCES gold.dim_date (date_key);

GO

-- ── dim_customer FKs ──────────────────────────────────────────────────────────
ALTER TABLE gold.fact_order_items
    ADD CONSTRAINT fk_foi_customer
    FOREIGN KEY (customer_sk) REFERENCES gold.dim_customer (customer_sk);

ALTER TABLE gold.fact_payments
    ADD CONSTRAINT fk_fp_customer
    FOREIGN KEY (customer_sk) REFERENCES gold.dim_customer (customer_sk);

ALTER TABLE gold.fact_reviews
    ADD CONSTRAINT fk_fr_customer
    FOREIGN KEY (customer_sk) REFERENCES gold.dim_customer (customer_sk);

ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_customer
    FOREIGN KEY (customer_sk) REFERENCES gold.dim_customer (customer_sk);

GO

-- ── dim_product FK ────────────────────────────────────────────────────────────
ALTER TABLE gold.fact_order_items
    ADD CONSTRAINT fk_foi_product
    FOREIGN KEY (product_sk) REFERENCES gold.dim_product (product_sk);

GO

-- ── dim_seller FKs ────────────────────────────────────────────────────────────
ALTER TABLE gold.fact_order_items
    ADD CONSTRAINT fk_foi_seller
    FOREIGN KEY (seller_sk) REFERENCES gold.dim_seller (seller_sk);

ALTER TABLE gold.fact_marketing_funnel
    ADD CONSTRAINT fk_fmf_seller
    FOREIGN KEY (seller_sk) REFERENCES gold.dim_seller (seller_sk);

GO

-- ── dim_payment_type FK ───────────────────────────────────────────────────────
ALTER TABLE gold.fact_payments
    ADD CONSTRAINT fk_fp_payment_type
    FOREIGN KEY (payment_type_sk) REFERENCES gold.dim_payment_type (payment_type_sk);

GO

-- ── dim_order_status FK ───────────────────────────────────────────────────────
ALTER TABLE gold.fact_order_life_cycle
    ADD CONSTRAINT fk_folc_order_status
    FOREIGN KEY (order_status_sk) REFERENCES gold.dim_order_status (order_status_sk);

GO

-- ── dim_marketing_channel FK ──────────────────────────────────────────────────
ALTER TABLE gold.fact_marketing_funnel
    ADD CONSTRAINT fk_fmf_mql_channel
    FOREIGN KEY (mql_channel_sk) REFERENCES gold.dim_marketing_channel (mql_channel_sk);

GO

-- ── review_comments outrigger FK ─────────────────────────────────────────────
-- 1:1 relationship — review_comments.review_sk must exist in fact_reviews
ALTER TABLE gold.review_comments
    ADD CONSTRAINT fk_review_comments_fact
    FOREIGN KEY (review_sk) REFERENCES gold.fact_reviews (review_sk);

GO
