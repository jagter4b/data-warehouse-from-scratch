# Silver Layer — Transformation Documentation

**Database:** `BI_AI` | **Schema:** `silver`  
**Strategy:** DROP + SELECT INTO (idempotent full-load)  
**Execution:** `EXEC silver.silver_master;`  
**Last Successful Run:** 2026-05-12 10:21:57 → 10:22:12 (~15s total)

---

## Pipeline Execution Summary

| # | Procedure | Silver Table | Rows Loaded | Duration |
|---|-----------|--------------|-------------|----------|
| 1 | `silver.load_customers` | `silver.customers` | 99,441 | 10s |
| 2 | `silver.load_sellers` | `silver.sellers` | 3,095 | 1s |
| 3 | `silver.load_products` | `silver.products` | 32,951 | 0s |
| 4 | `silver.load_orders` | `silver.orders` | 99,441 | 1s |
| 5 | `silver.load_order_items` | `silver.order_items` | 112,650 | 1s |
| 6 | `silver.load_order_payments` | `silver.order_payments` | 103,886 | 1s |
| 7 | `silver.load_order_reviews` | `silver.order_reviews` | 99,441 | 1s |
| 8 | `silver.load_marketing_qualified_leads` | `silver.marketing_qualified_leads` | 8,000 | 0s |
| 9 | `silver.load_closed_deals` | `silver.closed_deals` | 842 | 0s |

> **Note:** `geolocation` table is intentionally excluded from the Silver layer as it will not be part of the Galaxy Schema in Gold.

---

## Table-by-Table Transformations

### 1. `silver.customers`

**Source:** `bronze.customers` → **99,441 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `customer_id` | `NVARCHAR`, may have whitespace | `LTRIM(RTRIM(...))` | Trim whitespace |
| `customer_unique_id` | `NVARCHAR`, may have whitespace | `LTRIM(RTRIM(...))` | Trim whitespace |
| `customer_zip_code_prefix` | `INT` (e.g. `1151`, `9790`) | `RIGHT('00000' + CAST(... AS VARCHAR(5)), 5)` → `NVARCHAR(5)` | Zero-pad to 5 chars: `1151` → `'01151'` |
| `customer_city` | Mixed case, may have whitespace | `UPPER(LTRIM(RTRIM(...)))` | Standardize to uppercase |
| `customer_state` | Mixed case | `UPPER(LTRIM(RTRIM(...)))` | Standardize to uppercase |
| `_ingested_at`, `_source` | Carried over | No transformation | Audit metadata preserved |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _ingested_at DESC)` — keeps the most recent ingestion.

**Bronze Notes:**
- `customer_id` is unique per row but `customer_unique_id` can map to multiple `customer_id`s (same customer, multiple orders)
- Zip codes were stored as integers — zero-padding applied in Silver

---

### 2. `silver.sellers`

**Source:** `bronze.sellers` → **3,095 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `seller_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `seller_zip_code_prefix` | `INT` | `RIGHT('00000' + CAST(... AS VARCHAR(5)), 5)` → `NVARCHAR(5)` | Zero-pad to 5 chars |
| `seller_city` | Mixed case | `ISNULL(UPPER(LTRIM(RTRIM(...))), 'Not Specified')` | Uppercase + NULL guard |
| `seller_state` | Mixed case | `ISNULL(UPPER(LTRIM(RTRIM(...))), 'Not Specified')` | Uppercase + NULL guard |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `PARTITION BY seller_id ORDER BY _ingested_at DESC`

**Bronze Notes:**
- Zip codes were integers — same zero-padding logic as customers applied
- City/state useful for seller geographic distribution analysis

---

### 3. `silver.products`

**Source:** `bronze.products` + `bronze.product_category_name_translation` → **32,951 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `product_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `product_category_name` | Portuguese snake_case (e.g. `cama_mesa_banho`) | LEFT JOIN translation table → English → `STRING_SPLIT` + `STRING_AGG` → Title Case (e.g. `Bed Bath Table`) | Human-readable English category names |
| `product_name_length` | `product_name_lenght` (typo), `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Fix source typo, cast to INT, NULL → 0 |
| `product_description_length` | `product_description_lenght` (typo), `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Fix source typo, cast to INT, NULL → 0 |
| `product_photos_qty` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `product_weight_g` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `product_length_cm` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `product_height_cm` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `product_width_cm` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `PARTITION BY product_id ORDER BY _ingested_at DESC`

**Title Case Logic (SQL Server 2022+):**
```
snake_case → spaces → split on ' ' → capitalize each token → rejoin with ' '
bed_bath_table → bed bath table → [bed, bath, table] → Bed Bath Table
```

**Bronze Notes:**
- ~1.85% of rows missing `product_category_name` → mapped to `'Not Specified'`
- ~0.006% (2 rows) missing physical dimensions → set to `0`
- Source data has typos `lenght` → renamed to `length` in Silver
- Category names joined with translation table; English name preferred, Portuguese fallback

---

### 4. `silver.orders`

**Source:** `bronze.orders` → **99,441 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `order_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `customer_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `order_status` | Mixed case string | `LOWER(LTRIM(RTRIM(...)))` | Standardize to lowercase |
| `order_purchase_date` | Datetime string | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE; NULL → sentinel |
| `order_approved_date` | Datetime string (~0.16% NULL) | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE; NULL → sentinel |
| `order_delivered_carrier_date` | Datetime string (~1.79% NULL) | NULL + canceled/unavailable → `'1900-01-01'`; NULL + other status → `'9999-12-31'`; else TRY_CAST | Context-aware sentinel: `9999-12-31` = still in transit |
| `order_delivered_customer_date` | Datetime string (~2.98% NULL) | Same logic as carrier date | Context-aware sentinel |
| `order_estimated_delivery_date` | Datetime string | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `PARTITION BY order_id ORDER BY _ingested_at DESC`

**Sentinel Strategy:**
- `'1900-01-01'` = data quality gap / canceled order
- `'9999-12-31'` = order still in progress (not yet delivered)

**Bronze Notes:**
- Delivery timestamps missing for canceled/undelivered orders — handled with context-aware sentinels
- `order_status` distribution should be inspected (delivered, shipped, canceled, invoiced, processing, approved, unavailable, created)

---

### 5. `silver.order_items`

**Source:** `bronze.order_items` → **112,650 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `order_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `order_item_id` | `INT` | No transformation | Sequential line-item number |
| `product_id` | `NVARCHAR`, may be NULL | `ISNULL(LTRIM(RTRIM(...)), 'UNKNOWN')` | NULL FK → `'UNKNOWN'` sentinel |
| `seller_id` | `NVARCHAR`, may be NULL | `ISNULL(LTRIM(RTRIM(...)), 'UNKNOWN')` | NULL FK → `'UNKNOWN'` sentinel |
| `shipping_limit_date` | Datetime string | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE |
| `unit_price` | `price` column, `FLOAT` | `ISNULL(CAST(... AS DECIMAL(10,2)), 0.00)` | Renamed + financial precision |
| `unit_freight_value` | `freight_value` column, `FLOAT` | `ISNULL(CAST(... AS DECIMAL(10,2)), 0.00)` | Renamed + financial precision |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `PARTITION BY order_id, order_item_id ORDER BY _ingested_at DESC`

**Bronze Notes:**
- Composite PK: `(order_id, order_item_id)`
- `price` and `freight_value` are doubles → cast to `DECIMAL(10,2)` for financial accuracy

---

### 6. `silver.order_payments`

**Source:** `bronze.order_payments` → **103,886 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `order_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `payment_sequential` | `INT` | No transformation | Ordering within an order |
| `payment_type` | Raw snake_case (`credit_card`, `boleto`, `not_defined`) | CASE → human-readable label | `'credit_card'` → `'Credit Card'`; unknown → `'Not Specified'` |
| `payment_installments` | `FLOAT` | `ISNULL(CAST(... AS INT), 0)` | Cast to INT, NULL → 0 |
| `payment_value` | `FLOAT` | `ISNULL(CAST(... AS DECIMAL(10,2)), 0.00)` | Financial precision, NULL → 0.00 |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Payment Type Mapping:**

| Bronze Value | Silver Value |
|---|---|
| `credit_card` | `Credit Card` |
| `debit_card` | `Debit Card` |
| `boleto` | `Boleto` |
| `voucher` | `Voucher` |
| `not_defined` / NULL / other | `Not Specified` |

**Deduplication:** `PARTITION BY order_id, payment_sequential ORDER BY _ingested_at DESC`

**Bronze Notes:**
- Multiple payment rows per order are valid (split payments)
- `payment_installments` important for installment analysis

---

### 7. `silver.order_reviews`

**Source:** `bronze.order_reviews` → **99,441 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `review_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `order_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `review_score` | Inferred as string in Bronze | `CAST(... AS TINYINT)` | Convert to numeric (1–5) |
| `review_comment_title` | ~88.48% NULL | `ISNULL(..., 'No Title')` | NULL → sentinel string |
| `review_comment_message` | ~60.57% NULL | `ISNULL(..., 'No Message')` | NULL → sentinel string |
| `review_creation_date` | String timestamp | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE |
| `review_answer_date` | `review_answer_timestamp`, string | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Renamed + Cast to DATE |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication (special case):**
- Bronze had **1,204 duplicate `review_id`** values
- Collapsed to **one row per `order_id`** keeping the most recently answered review:
  `PARTITION BY order_id ORDER BY TRY_CAST(review_answer_timestamp AS DATE) DESC, _ingested_at DESC`

**Bronze Notes:**
- 1,204 `review_id` duplicates detected — same review stored multiple times during ingestion
- Text fields extremely sparse: title ~88% NULL, message ~61% NULL → expected for the dataset
- `review_score` was inferred as string in Bronze → cast to TINYINT in Silver

---

### 8. `silver.marketing_qualified_leads`

**Source:** `bronze.marketing_qualified_leads` → **8,000 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `mql_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `first_contact_date` | Date string | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE, NULL → sentinel |
| `landing_page_id` | `NVARCHAR`, may be NULL | `ISNULL(LTRIM(RTRIM(...)), 'UNKNOWN')` | NULL → sentinel |
| `origin` | Raw snake_case (`organic_search`, `other_publicities`) | CASE → human-readable label | Standardized marketing channel labels |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Origin Mapping:**

| Bronze Value | Silver Value |
|---|---|
| `organic_search` | `Organic Search` |
| `paid_search` | `Paid Search` |
| `social` | `Social` |
| `email` | `Email` |
| `referral` | `Referral` |
| `display` | `Display` |
| `direct_traffic` | `Direct Traffic` |
| `other` / `other_publicities` / NULL / unknown | `Other` |

**Deduplication:** `PARTITION BY mql_id ORDER BY _ingested_at DESC`

---

### 9. `silver.closed_deals`

**Source:** `bronze.closed_deals` → **842 rows**

| Column | Bronze State | Silver Transformation | Rationale |
|--------|-------------|----------------------|-----------|
| `mql_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Trim whitespace |
| `seller_id` | `NVARCHAR` | `LTRIM(RTRIM(...))` | Bridge FK to e-commerce sellers |
| `sdr_id` | `NVARCHAR`, may be NULL | `ISNULL(..., 'UNKNOWN')` | NULL → sentinel |
| `sr_id` | `NVARCHAR`, may be NULL | `ISNULL(..., 'UNKNOWN')` | NULL → sentinel |
| `won_date` | Datetime string, may be NULL | `ISNULL(TRY_CAST(... AS DATE), '1900-01-01')` | Cast to DATE |
| `business_segment` | Raw snake_case | `STRING_SPLIT` + `STRING_AGG` → Title Case | Same snake_case → Title Case logic as products |
| `lead_type` | Raw snake_case | CASE → human-readable label | e.g. `online_big` → `Online Big` |
| `lead_behaviour_profile` | Raw values | CASE → Title Case label | `cat` → `Cat`, `eagle` → `Eagle`, etc. |
| `has_company` | `FLOAT`, may be NULL | `ISNULL(CAST(... AS TINYINT), 0)` | Boolean flag, NULL → 0 |
| `has_gtin` | `FLOAT`, may be NULL | `ISNULL(CAST(... AS TINYINT), 0)` | Boolean flag, NULL → 0 |
| `average_stock` | Varchar range (e.g. `"100-500"`) | `ISNULL(LTRIM(RTRIM(...)), 'Not Specified')` | Not numeric — kept as text |
| `business_type` | Raw values | CASE → human-readable label | `reseller` → `Reseller`, `others` → `Other` |
| `declared_product_catalog_size` | `FLOAT`, may be NULL | `ISNULL(CAST(... AS DECIMAL(10,2)), 0.00)` | Financial precision |
| `declared_monthly_revenue` | `FLOAT`, may be NULL | `ISNULL(CAST(... AS DECIMAL(10,2)), 0.00)` | Financial precision |
| `_processed_at` | *(new column)* | `GETDATE()` | Silver processing timestamp |

**Deduplication:** `PARTITION BY mql_id ORDER BY _ingested_at DESC` (one deal per lead)

---

## General Transformation Rules Applied

| Rule | Description |
|------|-------------|
| **Deduplication** | All tables: `ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _ingested_at DESC)` — most recent ingestion wins |
| **Whitespace cleaning** | `LTRIM(RTRIM(...))` applied to all string/ID columns |
| **NULL → Sentinel** | Dates: `'1900-01-01'`; FK strings: `'UNKNOWN'`; free text: `'No Title'`/`'No Message'`; categoricals: `'Not Specified'`; numerics: `0` or `0.00` |
| **snake_case → Title Case** | `STRING_SPLIT` (ordinal) + `STRING_AGG` — requires SQL Server 2022+ |
| **Date casting** | `TRY_CAST(... AS DATE)` — safe cast, invalid strings become NULL then sentinel |
| **Financial precision** | `CAST(... AS DECIMAL(10,2))` for all monetary columns |
| **Metadata** | `_ingested_at` and `_source` carried through; `_processed_at` added as Silver timestamp |
| **No NVARCHAR → VARCHAR** | All string columns remain `NVARCHAR` to preserve Brazilian locale characters (ã, ç, é, etc.) |

---

## Excluded Tables

| Table | Reason |
|-------|--------|
| `bronze.geolocation` | Not included in the Galaxy Schema model — excluded from Silver and Gold |
| `bronze.product_category_name_translation` | Used as a lookup JOIN inside `silver.load_products`; not materialized as a standalone Silver table |

---

## Data Quality Audit Results

An automated Data Quality Audit (`silver_quality_checks.sql`) was run on **2026-05-12** after the initial Silver load. The results validated the transformation logic:

- **Row Counts & Deduplication**: All tables successfully loaded with 0 duplicates based on PKs. The `order_reviews` table correctly dropped 559 duplicate rows (resulting in 99,441 clean rows).
- **NULL Handling**: Zero unexpected NULLs in key columns. Dates missing in raw data were successfully converted to our sentinels (`1900-01-01` for missing/canceled, `9999-12-31` for active/in-transit).
- **Formatting**: ZIP codes were padded to 5 characters, categorical features Title Cased, and location strings UPPERCASED with trailing spaces removed. 
- **Referential Integrity**: Tested 8 foreign key relationships. 7 passed with 0 orphan rows (e.g., all `order_items` matched valid `products` and `orders`).
  - **Exception**: `silver.closed_deals` -> `silver.sellers` found **462 orphan rows**. This means there are 462 closed deals in the marketing funnel where the `seller_id` does not exist in the e-commerce `sellers` table. This is a known issue from the source data and will be handled during the Gold layer dimension modeling.

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `load_customers.sql` | SP: Bronze → Silver for customers |
| `load_sellers.sql` | SP: Bronze → Silver for sellers |
| `load_products.sql` | SP: Bronze → Silver for products (with category translation join) |
| `load_orders.sql` | SP: Bronze → Silver for orders |
| `load_order_items.sql` | SP: Bronze → Silver for order_items |
| `load_order_payments.sql` | SP: Bronze → Silver for order_payments |
| `load_order_reviews.sql` | SP: Bronze → Silver for order_reviews |
| `load_marketing_qualified_leads.sql` | SP: Bronze → Silver for MQLs |
| `load_closed_deals.sql` | SP: Bronze → Silver for closed deals |
| `silver_master.sql` | Master orchestrator — runs all 9 SPs in order |
| `silver_quality_checks.sql` | Comprehensive data quality audit script for the Silver layer |

## How to Run

```sql
-- 1. Execute each load_*.sql file to register the procedures (first time only)
-- 2. Run the full pipeline:
USE [BI_AI];
EXEC silver.silver_master;
```

---

## Next Step → Gold Layer

The Silver layer feeds the **Gold layer Galaxy Schema**, which will consist of:
- **Shared dimensions** (dim_customer, dim_seller, dim_product, dim_date)
- **E-commerce fact tables** (fact_orders, fact_order_items, fact_payments, fact_reviews)
- **Marketing fact tables** (fact_mql_pipeline bridging MQLs → closed_deals → sellers)
