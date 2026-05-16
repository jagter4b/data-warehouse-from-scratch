# Gold Layer — Kimball Galaxy Schema Documentation

**Database:** `BI_AI` | **Schema:** `gold`  
**Pattern:** Kimball Dimensional Modeling (Galaxy Schema)  
**Execution:** `EXEC gold.gold_master;`

---

## Architecture Overview

The Gold layer is the analytics-ready tier of the Medallion Architecture. It integrates **Olist e-commerce** and **marketing funnel** data into a shared dimensional model (Galaxy Schema) with conformed dimensions spanning two subject areas.

```
silver.customers  ──────────────────────────────────┐
silver.orders     ──┬──► fact_order_items           │
silver.order_items ─┘    fact_payments              ├──► dim_customer
silver.order_payments ──► fact_reviews              │    dim_product
silver.order_reviews ───► fact_order_life_cycle     │    dim_seller (shared)
                                                    │    dim_date (conformed)
silver.marketing_qualified_leads ──► dim_marketing_channel
silver.closed_deals ─────────────► fact_marketing_funnel ──► dim_seller (shared)
```

---

## Naming Conventions

| Convention | Pattern | Example |
|---|---|---|
| Surrogate Key | `<table>_sk` (INT IDENTITY) | `customer_sk` |
| Business Key | `<column>_bk` (natural key) | `customer_unique_id_bk` |
| Date FK | `<role>_date_key` INT → `dim_date.date_key` | `purchase_date_key` |
| Sentinel — unknown/past | `19000101` | Missing/canceled date |
| Sentinel — future/open | `99991231` | Not yet occurred |
| Unknown Member | SK = `-1` | Unresolvable FK |

---

## Dimensions

### 1. `gold.dim_date` — Conformed Date Dimension

**Grain:** One row per calendar day. **Key:** `date_key` = YYYYMMDD integer (e.g. `20170315`).  
**Range:** 2016-01-01 → 2020-12-31 + 2 sentinel rows. **Load:** Generated once via recursive CTE.

| Column | Type | Description |
|--------|------|-------------|
| `date_key` | INT PK | YYYYMMDD — also the natural key; no IDENTITY needed |
| `full_date` | DATE | Actual calendar date |
| `day_of_week_num` | TINYINT | ISO: 1=Monday … 7=Sunday |
| `day_of_week_name` | VARCHAR(10) | `'Monday'`, `'Tuesday'` … |
| `day_of_month` | TINYINT | 1–31 |
| `day_of_year` | SMALLINT | 1–366 |
| `week_of_year` | TINYINT | ISO week 1–53 |
| `month_num` | TINYINT | 1–12 |
| `month_name` | VARCHAR(10) | `'January'` … |
| `quarter_num` | TINYINT | 1–4 |
| `quarter_name` | CHAR(2) | `'Q1'`–`'Q4'` |
| `year` | SMALLINT | e.g. `2017` |
| `year_month` | CHAR(7) | `'YYYY-MM'` for month slicing |
| `is_weekend` | BIT | 1 = Saturday or Sunday |
| `is_holiday` | BIT | Placeholder (default 0) |

**Sentinel rows:**

| date_key | Meaning |
|---|---|
| `19000101` | Unknown / data quality gap |
| `99991231` | Not yet occurred / open milestone |

---

### 2. `gold.dim_customer` — SCD Type 1

**Source:** `silver.customers` | **Grain:** One row per unique person (`customer_unique_id`).  
**Strategy:** MERGE upsert. **Load SP:** `gold.load_dim_customer`.

> **Key design note:** `customer_id` is a per-order transient ID stored only in fact tables as a degenerate dim. The true person key is `customer_unique_id_bk`. ETL resolve path: `orders.customer_id → customers.customer_unique_id → dim_customer.customer_sk`.

| Column | Type | Description |
|--------|------|-------------|
| `customer_sk` | INT IDENTITY PK | Surrogate key |
| `customer_unique_id_bk` | VARCHAR(32) | Stable person identifier (BK) |
| `customer_zip_code_prefix` | CHAR(5) | Zero-padded (e.g. `'01151'`) |
| `customer_city` | VARCHAR(50) | Uppercased city name |
| `customer_state` | CHAR(2) | State abbreviation |
| `load_timestamp` | DATETIME2 | Last MERGE timestamp |
| `source_system` | VARCHAR(20) | `'olist_ecommerce'` |

**Unknown member:** `customer_sk = -1`, `customer_unique_id_bk = 'UNKNOWN'`

---

### 3. `gold.dim_product` — SCD Type 1

**Source:** `silver.products` | **Grain:** One row per product.  
**Strategy:** MERGE upsert. **Load SP:** `gold.load_dim_product`.

| Column | Type | Description |
|--------|------|-------------|
| `product_sk` | INT IDENTITY PK | Surrogate key |
| `product_id_bk` | VARCHAR(32) | Hashed UUID from source (BK) |
| `product_category_name` | VARCHAR(100) | English Title Case (from silver) |
| `product_name_length` | INT NULL | Char count; NULL if not provided |
| `product_description_length` | INT NULL | Char count; NULL if not provided |
| `product_photos_qty` | INT NULL | Number of product photos |
| `product_weight_g` | INT NULL | Weight in grams |
| `product_length_cm` | INT NULL | Length in cm |
| `product_height_cm` | INT NULL | Height in cm |
| `product_width_cm` | INT NULL | Width in cm |

**Unknown member:** `product_sk = -1`, `product_id_bk = 'UNKNOWN'`

---

### 4. `gold.dim_seller` — SCD Type 1 *(Shared Dimension)*

**Source:** `silver.sellers` | **Grain:** One row per seller.  
**Strategy:** MERGE upsert. **Load SP:** `gold.load_dim_seller`.

> **Shared dimension:** `dim_seller` bridges both subject areas — it is referenced by `fact_order_items` (e-commerce) and `fact_marketing_funnel` (marketing). `seller_id_bk` is the cross-domain link.

| Column | Type | Description |
|--------|------|-------------|
| `seller_sk` | INT IDENTITY PK | Surrogate key |
| `seller_id_bk` | VARCHAR(32) | Hashed UUID from source (BK) |
| `seller_zip_code_prefix` | CHAR(5) | Zero-padded zip |
| `seller_city` | VARCHAR(50) | Uppercased city |
| `seller_state` | CHAR(2) | State abbreviation |

**Unknown member:** `seller_sk = -1`, `seller_id_bk = 'UNKNOWN'`

---

### 5. `gold.dim_payment_type` — Static Lookup

**Grain:** One row per payment method. **Load:** Seeded in DDL (no load SP needed).

| payment_type_sk | payment_type |
|---|---|
| 1 | Credit Card |
| 2 | Debit Card |
| 3 | Boleto |
| 4 | Voucher |
| 5 | Not Specified |

---

### 6. `gold.dim_order_status` — Static Lookup

**Grain:** One row per order status. **Load:** Seeded in DDL (no load SP needed).

Values: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable`

---

### 7. `gold.dim_marketing_channel` — SCD Type 1

**Sources:** `silver.marketing_qualified_leads` LEFT JOIN `silver.closed_deals`  
**Grain:** One row per MQL (Marketing Qualified Lead). **Load SP:** `gold.load_dim_marketing_channel`.

> Unconverted MQLs get NULL for all closed-deal columns. Financial measures (`declared_monthly_revenue`, `declared_product_catalog_size`) are kept in `fact_marketing_funnel` — dimensions must not contain facts.

| Column | Type | Description |
|--------|------|-------------|
| `mql_channel_sk` | INT IDENTITY PK | Surrogate key |
| `mql_id_bk` | VARCHAR(32) | MQL hashed UUID (BK) |
| `origin` | VARCHAR(30) | `'Organic Search'`, `'Paid Search'`, etc. |
| `landing_page_id` | VARCHAR(32) NULL | Opaque hash; NULL if not captured |
| `business_segment` | VARCHAR(60) NULL | e.g. `'Pet Shop'` — NULL if not converted |
| `lead_type` | VARCHAR(20) NULL | `'Online Big'`, `'Offline'`, etc. |
| `lead_behaviour_profile` | VARCHAR(20) NULL | `'Cat'`, `'Eagle'`, `'Wolf'`, `'Shark'` |
| `business_type` | VARCHAR(20) NULL | `'Reseller'`, `'Manufacturer'`, `'Other'` |
| `average_stock` | VARCHAR(20) NULL | Text range, e.g. `'100-500'` |
| `has_company` | TINYINT | Boolean flag 0/1 |
| `has_gtin` | TINYINT | Boolean flag 0/1 (GTIN = barcode) |

---

## Fact Tables

### 1. `gold.fact_order_items` — Transactional

**Grain:** One row per order line item. **Strategy:** TRUNCATE + INSERT. **Load SP:** `gold.load_fact_order_items`.

| Column | Type | Role |
|--------|------|------|
| `order_item_sk` | INT IDENTITY PK | Surrogate key |
| `purchase_date_key` | INT → `dim_date` | Order-level purchase date |
| `shipping_limit_date_key` | INT → `dim_date` | Item-level shipping deadline |
| `customer_sk` | INT → `dim_customer` | Resolved via order→customer path |
| `product_sk` | INT → `dim_product` | -1 if product unknown |
| `seller_sk` | INT → `dim_seller` | -1 if seller unknown |
| `order_id_bk` | VARCHAR(32) | Degenerate dim |
| `order_item_id_bk` | INT | Sequential item position (1,2,3…) |
| `unit_price` | DECIMAL(10,2) | Price of single item |
| `unit_freight_value` | DECIMAL(10,2) | Freight for single item |
| `line_total` | DECIMAL(10,2) **computed** | `unit_price + unit_freight_value` (persisted) |

**ETL customer join path:**  
`order_items.order_id → orders.customer_id → customers.customer_unique_id → dim_customer.customer_sk`

---

### 2. `gold.fact_payments` — Transactional

**Grain:** One row per payment sequence within an order (split payments = multiple rows). **Load SP:** `gold.load_fact_payments`.

| Column | Type | Role |
|--------|------|------|
| `payment_sk` | INT IDENTITY PK | Surrogate key |
| `purchase_date_key` | INT → `dim_date` | Order purchase date |
| `customer_sk` | INT → `dim_customer` | Resolved via order path |
| `payment_type_sk` | INT → `dim_payment_type` | Credit Card / Boleto / etc. |
| `order_id_bk` | VARCHAR(32) | Degenerate dim |
| `payment_sequential_bk` | INT | Sequence number within order |
| `payment_value` | DECIMAL(10,2) | Amount for this payment line |
| `payment_installments` | INT | Number of installments |

> A single order paid by Voucher + Credit Card = **2 rows** in this fact.

---

### 3. `gold.fact_reviews` — Transactional

**Grain:** One row per order review (silver already deduped to one review per `order_id`). **Load SP:** `gold.load_fact_reviews`.

| Column | Type | Role |
|--------|------|------|
| `review_sk` | INT IDENTITY PK | Surrogate key; also FK from `review_comments` |
| `review_creation_date_key` | INT → `dim_date` | When survey was sent |
| `review_answer_date_key` | INT → `dim_date` | When customer replied; `99991231` if unanswered |
| `customer_sk` | INT → `dim_customer` | Resolved via order path |
| `review_id_bk` | VARCHAR(32) | Review UUID degenerate dim |
| `order_id_bk` | VARCHAR(32) | Order degenerate dim |
| `review_score` | TINYINT | 1–5 satisfaction score |

**Outrigger:** `gold.review_comments` (1:1 on `review_sk`) stores free-text title and message separately to protect columnstore compression.

---

### 4. `gold.fact_order_life_cycle` — Accumulating Snapshot

**Grain:** One row per order — tracks all lifecycle milestones in a single wide row. **Load SP:** `gold.load_fact_order_life_cycle`.

| Column | Type | Role |
|--------|------|------|
| `order_fulfillment_sk` | INT IDENTITY PK | Surrogate key |
| `purchase_date_key` | INT → `dim_date` | Order placed |
| `approval_date_key` | INT → `dim_date` | Payment approved |
| `carrier_date_key` | INT → `dim_date` | Handed to carrier |
| `delivery_date_key` | INT → `dim_date` | Delivered to customer |
| `estimated_delivery_date_key` | INT → `dim_date` | Originally promised date |
| `customer_sk` | INT → `dim_customer` | |
| `order_status_sk` | INT → `dim_order_status` | Current/final status |
| `order_id_bk` | VARCHAR(32) | Degenerate dim (unique) |
| `days_to_approve` | INT NULL | purchase → approval |
| `days_to_ship` | INT NULL | approval → carrier handoff |
| `days_to_deliver` | INT NULL | carrier → customer delivery |
| `days_purchase_to_delivery` | INT NULL | Total order span |
| `days_delivery_variance` | INT NULL | actual − estimated (negative = early) |
| `is_delivered_on_time` | BIT NULL | 1 = on time or early |
| `total_items` | INT | COUNT of order items |
| `total_distinct_products` | INT | COUNT DISTINCT products |
| `total_distinct_sellers` | INT | COUNT DISTINCT sellers |
| `total_order_value` | DECIMAL(10,2) | SUM unit_price from order_items |
| `total_freight_value` | DECIMAL(10,2) | SUM freight from order_items |
| `total_payment_value` | DECIMAL(10,2) | SUM payment_value from payments |

> **Lag measures** are NULL when either boundary date is a sentinel — no meaningless duration computed for incomplete stages.

---

### 5. `gold.fact_marketing_funnel` — Transactional

**Grain:** One row per closed deal (only converted MQLs). **Load SP:** `gold.load_fact_marketing_funnel`.  
Unconverted MQLs live in `dim_marketing_channel` only.

| Column | Type | Role |
|--------|------|------|
| `closed_deal_sk` | INT IDENTITY PK | Surrogate key |
| `first_contact_date_key` | INT → `dim_date` | MQL first contact |
| `won_date_key` | INT → `dim_date` | Deal closed / seller onboarded |
| `seller_sk` | INT → `dim_seller` | Onboarded seller |
| `mql_channel_sk` | INT → `dim_marketing_channel` | Lead's channel |
| `mql_id_bk` | VARCHAR(32) | MQL natural key |
| `sdr_id_bk` | VARCHAR(32) NULL | Sales Dev Rep internal ID |
| `sr_id_bk` | VARCHAR(32) NULL | Sales Rep internal ID |
| `days_to_close` | INT NULL | first_contact → won_date |
| `declared_monthly_revenue` | DECIMAL(15,2) | Self-reported by new seller |
| `declared_product_catalog_size` | DECIMAL(10,2) | Self-reported catalog count |

---

## Outrigger

### `gold.review_comments`

**Purpose:** Stores large NVARCHAR text columns separately from `fact_reviews` to preserve Clustered Columnstore Index compression efficiency.  
**Relationship:** 1:1 with `fact_reviews` on `review_sk`.

| Column | Type | Description |
|--------|------|-------------|
| `review_sk` | INT PK + FK | Mirrors `fact_reviews.review_sk` |
| `review_comment_title` | NVARCHAR(200) NULL | NULL if customer left no title |
| `review_comment_message` | NVARCHAR(1000) NULL | NULL if customer left no message |

> Silver sentinels (`'No Title'`, `'No message'`) are converted back to NULL here via `NULLIF()` for cleaner storage.

---

## Foreign Key Map

| Fact Table | FK Column | References |
|---|---|---|
| `fact_order_items` | `purchase_date_key` | `dim_date.date_key` |
| `fact_order_items` | `shipping_limit_date_key` | `dim_date.date_key` |
| `fact_order_items` | `customer_sk` | `dim_customer.customer_sk` |
| `fact_order_items` | `product_sk` | `dim_product.product_sk` |
| `fact_order_items` | `seller_sk` | `dim_seller.seller_sk` |
| `fact_payments` | `purchase_date_key` | `dim_date.date_key` |
| `fact_payments` | `customer_sk` | `dim_customer.customer_sk` |
| `fact_payments` | `payment_type_sk` | `dim_payment_type.payment_type_sk` |
| `fact_reviews` | `review_creation_date_key` | `dim_date.date_key` |
| `fact_reviews` | `review_answer_date_key` | `dim_date.date_key` |
| `fact_reviews` | `customer_sk` | `dim_customer.customer_sk` |
| `fact_order_life_cycle` | ×5 date keys | `dim_date.date_key` |
| `fact_order_life_cycle` | `customer_sk` | `dim_customer.customer_sk` |
| `fact_order_life_cycle` | `order_status_sk` | `dim_order_status.order_status_sk` |
| `fact_marketing_funnel` | `first_contact_date_key` | `dim_date.date_key` |
| `fact_marketing_funnel` | `won_date_key` | `dim_date.date_key` |
| `fact_marketing_funnel` | `seller_sk` | `dim_seller.seller_sk` |
| `fact_marketing_funnel` | `mql_channel_sk` | `dim_marketing_channel.mql_channel_sk` |
| `review_comments` | `review_sk` | `fact_reviews.review_sk` |

---

## ETL Load Strategies

| Object Type | Strategy | Idempotent? |
|---|---|---|
| `dim_customer`, `dim_product`, `dim_seller`, `dim_marketing_channel` | `MERGE` (SCD Type 1 upsert) | ✅ Yes |
| `dim_payment_type`, `dim_order_status` | INSERT seeds in DDL | ✅ Yes (WHERE NOT EXISTS) |
| `dim_date` | Recursive CTE, INSERT WHERE NOT EXISTS | ✅ Yes |
| All fact tables | `TRUNCATE + INSERT` | ✅ Yes |
| `fact_reviews` + `review_comments` | Drop FK → TRUNCATE both → Recreate FK → INSERT | ✅ Yes |

---

## Execution Order

```sql
-- ── PRE-REQUISITES (run ONCE on first setup) ─────────────────────────────────
-- 1. Create all dimension tables + static seeds
-- 2. Populate the date spine
-- 3. Create all fact tables + FK constraints

-- Step 1
-- Execute: gold_ddl_dimensions.sql

-- Step 2
-- Execute: gold_generate_dim_date.sql

-- Step 3
-- Execute: gold_ddl_facts.sql

-- ── ONGOING REFRESH (runs the full pipeline) ─────────────────────────────────
USE [BI_AI];
EXEC gold.gold_master;
```

**`gold_master` execution order:**

| # | Procedure | Object |
|---|---|---|
| 1 | `gold.load_dim_customer` | `dim_customer` |
| 2 | `gold.load_dim_product` | `dim_product` |
| 3 | `gold.load_dim_seller` | `dim_seller` |
| 4 | `gold.load_dim_marketing_channel` | `dim_marketing_channel` |
| 5 | `gold.load_fact_order_items` | `fact_order_items` |
| 6 | `gold.load_fact_payments` | `fact_payments` |
| 7 | `gold.load_fact_reviews` | `fact_reviews` + `review_comments` |
| 8 | `gold.load_fact_order_life_cycle` | `fact_order_life_cycle` |
| 9 | `gold.load_fact_marketing_funnel` | `fact_marketing_funnel` |

> Dimensions always load before facts. One failure halts the entire pipeline (`THROW` on each `BEGIN CATCH`).

---

## Post-Load Verification

```sql
-- Run after EXEC gold.gold_master to verify all tables loaded:
SELECT 'dim_date'               AS table_name, COUNT(*) AS row_count FROM gold.dim_date
UNION ALL SELECT 'dim_customer',               COUNT(*) FROM gold.dim_customer
UNION ALL SELECT 'dim_product',                COUNT(*) FROM gold.dim_product
UNION ALL SELECT 'dim_seller',                 COUNT(*) FROM gold.dim_seller
UNION ALL SELECT 'dim_payment_type',           COUNT(*) FROM gold.dim_payment_type
UNION ALL SELECT 'dim_order_status',           COUNT(*) FROM gold.dim_order_status
UNION ALL SELECT 'dim_marketing_channel',      COUNT(*) FROM gold.dim_marketing_channel
UNION ALL SELECT 'review_comments',            COUNT(*) FROM gold.review_comments
UNION ALL SELECT 'fact_order_items',           COUNT(*) FROM gold.fact_order_items
UNION ALL SELECT 'fact_payments',              COUNT(*) FROM gold.fact_payments
UNION ALL SELECT 'fact_reviews',               COUNT(*) FROM gold.fact_reviews
UNION ALL SELECT 'fact_order_life_cycle',      COUNT(*) FROM gold.fact_order_life_cycle
UNION ALL SELECT 'fact_marketing_funnel',      COUNT(*) FROM gold.fact_marketing_funnel
ORDER BY table_name;
```

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `gold_ddl_dimensions.sql` | DDL: CREATE all dimension tables + static seeds |
| `gold_ddl_facts.sql` | DDL: CREATE all fact tables + all FK constraints |
| `gold_generate_dim_date.sql` | Populates `dim_date` (run once after DDL) |
| `gold_load_dim_customer.sql` | SP: silver → `dim_customer` (MERGE) |
| `gold_load_dim_product.sql` | SP: silver → `dim_product` (MERGE) |
| `gold_load_dim_seller.sql` | SP: silver → `dim_seller` (MERGE) |
| `gold_load_dim_marketing_channel.sql` | SP: silver MQL + closed deals → `dim_marketing_channel` (MERGE) |
| `gold_load_fact_order_items.sql` | SP: silver → `fact_order_items` (TRUNCATE + INSERT) |
| `gold_load_fact_payments.sql` | SP: silver → `fact_payments` (TRUNCATE + INSERT) |
| `gold_load_fact_reviews.sql` | SP: silver → `fact_reviews` + `review_comments` |
| `gold_load_fact_order_life_cycle.sql` | SP: silver → `fact_order_life_cycle` (TRUNCATE + INSERT) |
| `gold_load_fact_marketing_funnel.sql` | SP: silver → `fact_marketing_funnel` (TRUNCATE + INSERT) |
| `gold_master.sql` | Master orchestrator — runs all 9 load SPs in order |
