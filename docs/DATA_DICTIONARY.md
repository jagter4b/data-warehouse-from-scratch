# 📖 Data Dictionary

## Overview

This document describes every table in the `gold` schema — the analytics-ready layer of the Olist Data Warehouse. All tables follow Kimball dimensional modeling conventions.

---

## Naming Conventions

| Convention | Pattern | Example |
|------------|---------|---------|
| Surrogate Key | `<table>_sk` (INT IDENTITY) | `customer_sk` |
| Business Key | `<column>_bk` (natural key) | `customer_unique_id_bk` |
| Date FK | `<role>_date_key` INT → `dim_date.date_key` | `purchase_date_key` |
| Sentinel — unknown/past | `19000101` | Missing/canceled date |
| Sentinel — future/open | `99991231` | Not yet occurred |
| Unknown Member | SK = `-1` | Unresolvable FK |

---

## Dimension Tables

### `gold.dim_date`

**Purpose:** Conformed date dimension.  
**Grain:** One row per calendar day.  
**Key:** `date_key` = YYYYMMDD integer.  
**Range:** 2016-01-01 → 2020-12-31 + 2 sentinel rows.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `date_key` | INT | NOT NULL | YYYYMMDD — primary key, no IDENTITY needed |
| `full_date` | DATE | NOT NULL | Actual calendar date |
| `day_of_week_num` | TINYINT | NOT NULL | ISO: 1=Monday … 7=Sunday |
| `day_of_week_name` | VARCHAR(10) | NOT NULL | 'Monday', 'Tuesday', etc. |
| `day_of_month` | TINYINT | NOT NULL | 1–31 |
| `day_of_year` | SMALLINT | NOT NULL | 1–366 |
| `week_of_year` | TINYINT | NOT NULL | ISO week 1–53 |
| `month_num` | TINYINT | NOT NULL | 1–12 |
| `month_name` | VARCHAR(10) | NOT NULL | 'January' … 'December' |
| `quarter_num` | TINYINT | NOT NULL | 1–4 |
| `quarter_name` | CHAR(2) | NOT NULL | 'Q1'–'Q4' |
| `year` | SMALLINT | NOT NULL | e.g. 2017 |
| `year_month` | CHAR(7) | NOT NULL | 'YYYY-MM' for month slicing |
| `is_weekend` | BIT | NOT NULL | 1 = Saturday or Sunday |
| `is_holiday` | BIT | NOT NULL | Placeholder, default 0 |

**Special rows:**
| date_key | full_date | Meaning |
|----------|-----------|---------|
| `19000101` | 1900-01-01 | Unknown / data quality gap |
| `99991231` | 9999-12-31 | Not yet occurred / open milestone |

---

### `gold.dim_customer`

**Purpose:** One row per unique customer (person).  
**Source:** `silver.customers`  
**Load Strategy:** MERGE (SCD Type 1 upsert)

> **Key design note:** `customer_id` is a per-order transient ID stored only in fact tables as a degenerate dimension. The stable person identifier is `customer_unique_id_bk`. ETL resolve path: `orders.customer_id → customers.customer_unique_id → dim_customer.customer_sk`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `customer_sk` | INT IDENTITY | NOT NULL | Surrogate key (PK) |
| `customer_unique_id_bk` | VARCHAR(32) | NOT NULL | Stable person identifier (BK) |
| `customer_zip_code_prefix` | CHAR(5) | NOT NULL | Zero-padded (e.g. '01151') |
| `customer_city` | VARCHAR(50) | NOT NULL | Uppercased city name |
| `customer_state` | CHAR(2) | NOT NULL | State abbreviation (e.g. 'SP') |
| `load_timestamp` | DATETIME2 | NOT NULL | Last MERGE timestamp |
| `source_system` | VARCHAR(20) | NOT NULL | 'olist_ecommerce' |

**Unknown member:** `customer_sk = -1`, `customer_unique_id_bk = 'UNKNOWN'`

---

### `gold.dim_product`

**Purpose:** One row per product.  
**Source:** `silver.products`  
**Load Strategy:** MERGE (SCD Type 1 upsert)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `product_sk` | INT IDENTITY | NOT NULL | Surrogate key (PK) |
| `product_id_bk` | VARCHAR(32) | NOT NULL | Hashed UUID from source (BK) |
| `product_category_name` | VARCHAR(100) | NULL | English Title Case category |
| `product_name_length` | INT | NULL | Character count of product name |
| `product_description_length` | INT | NULL | Character count of description |
| `product_photos_qty` | INT | NULL | Number of product photos |
| `product_weight_g` | INT | NULL | Weight in grams |
| `product_length_cm` | INT | NULL | Length in cm |
| `product_height_cm` | INT | NULL | Height in cm |
| `product_width_cm` | INT | NULL | Width in cm |

**Unknown member:** `product_sk = -1`, `product_id_bk = 'UNKNOWN'`

---

### `gold.dim_seller` *(Shared Dimension)*

**Purpose:** One row per seller — bridges both e-commerce and marketing subject areas.  
**Source:** `silver.sellers`  
**Load Strategy:** MERGE (SCD Type 1 upsert)

> **Shared dimension:** Referenced by both `fact_order_items` (e-commerce) and `fact_marketing_funnel` (marketing). The `seller_id_bk` is the cross-domain linking key.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `seller_sk` | INT IDENTITY | NOT NULL | Surrogate key (PK) |
| `seller_id_bk` | VARCHAR(32) | NOT NULL | Hashed UUID from source (BK) |
| `seller_zip_code_prefix` | CHAR(5) | NOT NULL | Zero-padded zip |
| `seller_city` | VARCHAR(50) | NOT NULL | Uppercased city name |
| `seller_state` | CHAR(2) | NOT NULL | State abbreviation |

**Unknown member:** `seller_sk = -1`, `seller_id_bk = 'UNKNOWN'`

---

### `gold.dim_payment_type`

**Purpose:** Static lookup for payment methods.  
**Load:** Seeded in DDL — no load SP needed.

| payment_type_sk | payment_type |
|-----------------|-------------|
| 1 | Credit Card |
| 2 | Debit Card |
| 3 | Boleto |
| 4 | Voucher |
| 5 | Not Specified |

---

### `gold.dim_order_status`

**Purpose:** Static lookup for order lifecycle statuses.  
**Load:** Seeded in DDL.

Values: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable`

---

### `gold.dim_marketing_channel`

**Purpose:** One row per Marketing Qualified Lead (MQL). Stores channel + behavioral metadata.  
**Sources:** `silver.marketing_qualified_leads` LEFT JOIN `silver.closed_deals`  
**Load Strategy:** MERGE (SCD Type 1 upsert)

> Unconverted MQLs (those that didn't become sellers) get NULL for all closed-deal columns. Financial measures stay in `fact_marketing_funnel` — dimensions must not contain facts.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `mql_channel_sk` | INT IDENTITY | NOT NULL | Surrogate key (PK) |
| `mql_id_bk` | VARCHAR(32) | NOT NULL | MQL hashed UUID (BK) |
| `origin` | VARCHAR(30) | NOT NULL | 'Organic Search', 'Paid Search', 'Social', etc. |
| `landing_page_id` | VARCHAR(32) | NULL | Opaque hash; NULL if not captured |
| `business_segment` | VARCHAR(60) | NULL | e.g. 'Pet Shop' — NULL if not converted |
| `lead_type` | VARCHAR(20) | NULL | 'Online Big', 'Offline', etc. |
| `lead_behaviour_profile` | VARCHAR(20) | NULL | 'Cat', 'Eagle', 'Wolf', 'Shark' |
| `business_type` | VARCHAR(20) | NULL | 'Reseller', 'Manufacturer', 'Other' |
| `average_stock` | VARCHAR(20) | NULL | Text range e.g. '100-500' |
| `has_company` | TINYINT | NOT NULL | Boolean flag 0/1 |
| `has_gtin` | TINYINT | NOT NULL | Boolean flag 0/1 (GTIN = barcode) |

---

## Fact Tables

### `gold.fact_order_items`

**Purpose:** One row per order line item (transactional grain).  
**Strategy:** TRUNCATE + INSERT  
**~Rows:** 112,650

| Column | Type | FK | Description |
|--------|------|----|-------------|
| `order_item_sk` | INT IDENTITY | PK | Surrogate key |
| `purchase_date_key` | INT | → dim_date | Order-level purchase date |
| `shipping_limit_date_key` | INT | → dim_date | Item-level shipping deadline |
| `customer_sk` | INT | → dim_customer | Resolved: order→customer→dim_customer |
| `product_sk` | INT | → dim_product | -1 if product unknown |
| `seller_sk` | INT | → dim_seller | -1 if seller unknown |
| `order_id_bk` | VARCHAR(32) | — | Degenerate dim (order natural key) |
| `order_item_id_bk` | INT | — | Sequential item position (1, 2, 3…) |
| `unit_price` | DECIMAL(10,2) | — | Price of single item |
| `unit_freight_value` | DECIMAL(10,2) | — | Freight for single item |
| `line_total` | DECIMAL(10,2) **computed** | — | unit_price + unit_freight_value (persisted) |

**ETL customer join path:**  
`order_items.order_id → orders.customer_id → customers.customer_unique_id → dim_customer.customer_sk`

---

### `gold.fact_payments`

**Purpose:** One row per payment sequence within an order (split payments = multiple rows).  
**Strategy:** TRUNCATE + INSERT  
**~Rows:** 103,886

| Column | Type | FK | Description |
|--------|------|----|-------------|
| `payment_sk` | INT IDENTITY | PK | Surrogate key |
| `purchase_date_key` | INT | → dim_date | Order purchase date |
| `customer_sk` | INT | → dim_customer | Resolved via order path |
| `payment_type_sk` | INT | → dim_payment_type | Credit Card / Boleto / etc. |
| `order_id_bk` | VARCHAR(32) | — | Degenerate dim |
| `payment_sequential_bk` | INT | — | Sequence number within order |
| `payment_value` | DECIMAL(10,2) | — | Amount for this payment line |
| `payment_installments` | INT | — | Number of installments |

> A single order paid by Voucher + Credit Card = **2 rows** in this fact.

---

### `gold.fact_reviews`

**Purpose:** One row per order review (silver already deduped to one review per order_id).  
**Strategy:** TRUNCATE + INSERT (with FK drop/recreate for outrigger)  
**~Rows:** 99,441

| Column | Type | FK | Description |
|--------|------|----|-------------|
| `review_sk` | INT IDENTITY | PK | Surrogate key; also FK from review_comments |
| `review_creation_date_key` | INT | → dim_date | When satisfaction survey was sent |
| `review_answer_date_key` | INT | → dim_date | When customer replied; 99991231 if unanswered |
| `customer_sk` | INT | → dim_customer | Resolved via order path |
| `review_id_bk` | VARCHAR(32) | — | Review UUID degenerate dim |
| `order_id_bk` | VARCHAR(32) | — | Order degenerate dim |
| `review_score` | TINYINT | — | 1–5 satisfaction score |

---

### `gold.fact_order_life_cycle` *(Accumulating Snapshot)*

**Purpose:** One row per order — tracks all lifecycle milestones in a single wide row. Updated as new stages complete.  
**Strategy:** TRUNCATE + INSERT  
**~Rows:** 99,441

| Column | Type | FK | Description |
|--------|------|----|-------------|
| `order_fulfillment_sk` | INT IDENTITY | PK | Surrogate key |
| `purchase_date_key` | INT | → dim_date | Order placed |
| `approval_date_key` | INT | → dim_date | Payment approved |
| `carrier_date_key` | INT | → dim_date | Handed to carrier |
| `delivery_date_key` | INT | → dim_date | Delivered to customer |
| `estimated_delivery_date_key` | INT | → dim_date | Originally promised date |
| `customer_sk` | INT | → dim_customer | |
| `order_status_sk` | INT | → dim_order_status | Current/final status |
| `order_id_bk` | VARCHAR(32) | — | Degenerate dim (unique) |
| `days_to_approve` | INT | — | purchase → approval lag |
| `days_to_ship` | INT | — | approval → carrier handoff lag |
| `days_to_deliver` | INT | — | carrier → customer delivery lag |
| `days_purchase_to_delivery` | INT | — | Total order span |
| `days_delivery_variance` | INT | — | actual − estimated (negative = early) |
| `is_delivered_on_time` | BIT | — | 1 = on time or early |
| `total_items` | INT | — | COUNT of line items |
| `total_distinct_products` | INT | — | COUNT DISTINCT products |
| `total_distinct_sellers` | INT | — | COUNT DISTINCT sellers |
| `total_order_value` | DECIMAL(10,2) | — | SUM unit_price from order_items |
| `total_freight_value` | DECIMAL(10,2) | — | SUM freight from order_items |
| `total_payment_value` | DECIMAL(10,2) | — | SUM payment_value from payments |

> Lag measures are NULL when either boundary date is a sentinel — prevents computing meaningless durations for incomplete stages.

---

### `gold.fact_marketing_funnel`

**Purpose:** One row per closed deal (only converted MQLs). Unconverted MQLs live in dim_marketing_channel only.  
**Strategy:** TRUNCATE + INSERT  
**~Rows:** 842

| Column | Type | FK | Description |
|--------|------|----|-------------|
| `closed_deal_sk` | INT IDENTITY | PK | Surrogate key |
| `first_contact_date_key` | INT | → dim_date | MQL first contact |
| `won_date_key` | INT | → dim_date | Deal closed / seller onboarded |
| `seller_sk` | INT | → dim_seller | Onboarded seller |
| `mql_channel_sk` | INT | → dim_marketing_channel | Lead's channel |
| `mql_id_bk` | VARCHAR(32) | — | MQL natural key |
| `sdr_id_bk` | VARCHAR(32) | — | Sales Dev Rep internal ID |
| `sr_id_bk` | VARCHAR(32) | — | Sales Rep internal ID |
| `days_to_close` | INT | — | first_contact → won_date |
| `declared_monthly_revenue` | DECIMAL(15,2) | — | Self-reported by new seller |
| `declared_product_catalog_size` | DECIMAL(10,2) | — | Self-reported catalog count |

---

## Outrigger

### `gold.review_comments`

**Purpose:** Stores large NVARCHAR text columns separately from `fact_reviews` to preserve Clustered Columnstore Index compression efficiency.  
**Relationship:** 1:1 with `fact_reviews` on `review_sk`.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `review_sk` | INT | NOT NULL | PK + FK → fact_reviews.review_sk |
| `review_comment_title` | NVARCHAR(200) | NULL | NULL if customer left no title |
| `review_comment_message` | NVARCHAR(1000) | NULL | NULL if customer left no message |

> Silver sentinels (`'No Title'`, `'No message'`) are converted back to NULL here via `NULLIF()` for cleaner storage.

---

## Complete Foreign Key Map

| Fact Table | FK Column | References |
|------------|-----------|-----------|
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
| `fact_order_life_cycle` | `purchase_date_key` | `dim_date.date_key` |
| `fact_order_life_cycle` | `approval_date_key` | `dim_date.date_key` |
| `fact_order_life_cycle` | `carrier_date_key` | `dim_date.date_key` |
| `fact_order_life_cycle` | `delivery_date_key` | `dim_date.date_key` |
| `fact_order_life_cycle` | `estimated_delivery_date_key` | `dim_date.date_key` |
| `fact_order_life_cycle` | `customer_sk` | `dim_customer.customer_sk` |
| `fact_order_life_cycle` | `order_status_sk` | `dim_order_status.order_status_sk` |
| `fact_marketing_funnel` | `first_contact_date_key` | `dim_date.date_key` |
| `fact_marketing_funnel` | `won_date_key` | `dim_date.date_key` |
| `fact_marketing_funnel` | `seller_sk` | `dim_seller.seller_sk` |
| `fact_marketing_funnel` | `mql_channel_sk` | `dim_marketing_channel.mql_channel_sk` |
| `review_comments` | `review_sk` | `fact_reviews.review_sk` |
