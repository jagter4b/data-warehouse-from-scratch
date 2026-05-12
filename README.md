# Olist Data Warehouse: From Scratch (Medallion Architecture)

> **Production-grade Data Warehouse** integrating disparate data sources into a centralized **Single Point of Truth** using **ELT (Extract, Load, Transform)** pipeline and **Kimball Dimensional Modeling**.

[![SQL Server](https://img.shields.io/badge/SQL%20Server-2022-red?logo=microsoftsqlserver)](https://www.microsoft.com/sql-server)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://python.org)
[![T-SQL](https://img.shields.io/badge/T--SQL-Stored%20Procedures-orange)](#)
[![Medallion Architecture](https://img.shields.io/badge/Architecture-Medallion%20(Bronze%7CSilver%7CGold)-green)](#)
[![Kimball](https://img.shields.io/badge/Modeling-Kimball%20Galaxy%20Schema-purple)](#)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
   - [Medallion Overview](#the-medallion-approach)
   - [Bronze Layer](#bronze-layer--raw-ingestion)
   - [Silver Layer](#silver-layer--cleaning--standardization)
   - [Gold Layer](#gold-layer--dimensional-modeling)
3. [Data Sources](#data-sources)
4. [Technology Stack](#technology-stack)
5. [Repository Structure](#repository-structure)
6. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [Running the Pipeline](#running-the-pipeline)
7. [Schema Documentation](#schema-documentation)
8. [Data Quality](#data-quality)
9. [Key Design Decisions](#key-design-decisions)
10. [Performance Metrics](#performance-metrics)
11. [Roadmap](#roadmap)
12. [Contributing](#contributing)

---

## Project Overview

This project builds a complete **Data Warehouse from scratch** following industry best practices. It integrates data from **three distinct source systems** -- a PostgreSQL database, Google Sheets, and a custom Apps Script API -- into a local SQL Server instance structured as a **Medallion Architecture** with a **Kimball Galaxy Schema** presentation layer.

### Objectives

- Build a production-grade, reproducible ELT pipeline
- Implement proper data quality checks at every layer
- Create a dimensional model optimized for BI tools (Power BI)
- Maintain full data lineage from source to presentation
- Demonstrate multi-source integration with disparate data formats

### Datasets

| Dataset | Source | Records | Description |
|---------|--------|---------|-------------|
| [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | Kaggle (via Neon PostgreSQL) | ~100K orders, ~112K items | E-commerce transactions from 2016--2018 |
| [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel) | Kaggle (via Google Sheets) | ~8K leads, ~842 deals | Marketing qualified leads and closed deals |
| Brazilian Geolocation | Google Apps Script API | ~856K ZIP code coordinates | Latitude/longitude for Brazilian postal codes |

### Current Status

> The **Data Engineering phase is complete**. All three Medallion layers (Bronze, Silver, Gold) are fully operational.  
> **Current focus:** Reporting & Dashboarding in Power BI.

---

## Architecture

### The Medallion Approach

```
                   +-------------------+        +------------------+        +-------------------+
                   |    BRONZE (Raw)   |  --->  | SILVER (Cleaned) |  --->  |   GOLD (Analytical) |
                   +-------------------+        +------------------+        +-------------------+
                   |                   |        |                  |        |                   |
   PostgreSQL  --->| bronze.customers  |        | silver.customers |        | dim_customer      |
   (7 tables)      | bronze.orders     |        | silver.orders    |        | dim_product       |
                    | bronze.order_items|        | silver.products  |        | dim_seller        |
   Google Sheets ->| bronze.closed_... |        | silver.sellers   |        | dim_date          |
   (3 tables)      | bronze.mql        |        | silver.payments  |        | dim_marketing_... |
                    | bronze.reviews    |        | silver.reviews   |        | dim_payment_type  |
   GAS API    ---->| bronze.geolocation|        | (9 tables)       |        | dim_order_status  |
   (~856K rows)   +-------------------+        +------------------+        +-------------------+
                    ~1.28M rows                   ~1.28M rows                    |
                     (11 tables)                  (11 tables)                   |   5 Fact Tables
                                                                              |   + Outrigger
                                                                              +------------------
                                                                                Galaxy Schema
```

### Bronze Layer -- Raw Ingestion

Data lands **exactly as-is** from source systems with minimal processing.

| Characteristic | Implementation |
|----------------|----------------|
| **Philosophy** | Zero transformations -- preserve full source fidelity |
| **Processing** | Only audit columns added (`_ingested_at`, `_source`) |
| **Idempotency** | Drop & Recreate on every run |
| **Row Count** | ~1.28 million rows across 11 tables |

**Key Features:**
- **Pure ELT:** No transformations during ingestion
- **Multi-source support:** PostgreSQL, Google Sheets (Excel), REST API
- **Batching:** Dynamic `safe_chunk = floor(2000 / num_cols)` bypasses SQL Server's 2100-parameter limit
- **Audit trail:** Every row tagged with ingestion timestamp and source system metadata
- **Quality checks:** Dedicated [`data_validation.sql`](./ingestion/data_validation.sql) profiles missing values, duplicates, and referential integrity

**Ingestion Summary:**

| Pipeline | Source | Tables | Rows | Duration |
|----------|--------|--------|------|----------|
| Neon PostgreSQL | Cloud DB | 7 | ~450K | ~159s |
| Google Drive | Sheets | 3 | ~108K | ~93s |
| Geolocation API | Apps Script | 1 | ~856K | ~54s |
| **Total** | | **11** | **~1.28M** | **~306s** |

[Detailed Bronze Documentation >](./ingestion/README.md)

---

### Silver Layer -- Cleaning & Standardization

Raw data is cleaned, deduplicated, typed, and prepared for dimensional modeling.

| Characteristic | Implementation |
|----------------|----------------|
| **Philosophy** | Clean once, reuse everywhere -- establish single source of truth |
| **Processing** | Deduplication, type casting, standardization, relationship building |
| **Idempotency** | `DROP + SELECT INTO` full reload per table |
| **Row Count** | ~1.28 million rows across 11 cleaned tables |

**Key Transformations:**

| Transformation | Implementation |
|----------------|----------------|
| **Deduplication** | `ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _ingested_at DESC)` -- keeps most recent |
| **Whitespace Cleaning** | `LTRIM/RTRIM` on all string columns |
| **ZIP Code Standardization** | Zero-padding to 5 digits (`01415001` -> `01415`) |
| **Case Standardization** | Title Case for cities, UPPER for states, human-readable labels for categories |
| **Date Sentinels** | `NULL` -> `1900-01-01` (unknown), in-transit -> `9999-12-31` |
| **Missing FKs** | Mapped to `'UNKNOWN'` sentinel values |
| **Categorical Mapping** | `snake_case` -> human-readable (`credit_card` -> `'Credit Card'`) |

**Orchestration:**
The `silver.silver_master` stored procedure executes 9 load procedures in dependency sequence with integrated `TRY/CATCH` error handling.

[Detailed Silver Documentation >](./scripts/silver/README.md)

---

### Gold Layer -- Dimensional Modeling

The presentation layer structured as a **Kimball Galaxy Schema** -- optimized for Power BI and analytical reporting.

| Characteristic | Implementation |
|----------------|----------------|
| **Philosophy** | Business-ready models that hide complexity from analysts |
| **Method** | Kimball Dimensional Modeling (Galaxy Schema) |
| **Dimensions** | 7 (4 dynamic SCD Type 1 + 2 static seeded + 1 conformed date) |
| **Facts** | 5 (4 transactional + 1 accumulating snapshot) + 1 outrigger |
| **Referential Integrity** | Full FK constraint enforcement |

**Dimension Tables:**

| Dimension | Grain | Strategy | Rows |
|-----------|-------|----------|------|
| `dim_date` | One row per calendar day | Generated date spine (2016--2020) | 1,829 |
| `dim_customer` | One per unique customer | MERGE (SCD Type 1) | ~96,000 |
| `dim_product` | One per product | MERGE (SCD Type 1) | ~32,000 |
| `dim_seller` | One per seller | MERGE (SCD Type 1) | ~3,000 |
| `dim_marketing_channel` | One per channel combo | MERGE (SCD Type 1) | ~10--50 |
| `dim_payment_type` | One per payment method | Static seeded in DDL | 5 |
| `dim_order_status` | One per status value | Static seeded in DDL | 8 |

**Fact Tables:**

| Fact Table | Grain | Type | Rows |
|------------|-------|------|------|
| `fact_order_items` | One per order line item | Transactional | ~112,000 |
| `fact_payments` | One per payment method per order | Transactional | ~104,000 |
| `fact_reviews` | One per order review | Transactional + Outrigger | ~99,000 |
| `fact_order_life_cycle` | One per order | Accumulating Snapshot | ~99,000 |
| `fact_marketing_funnel` | One per qualified lead | Transactional | ~8,000 |

**ETL Patterns:**
- **Dimensions:** `MERGE` (upsert) for SCD Type 1 idempotency
- **Facts:** `TRUNCATE + INSERT` for clean full reload
- **Unknown Members:** SK = -1 in every dimension for orphaned fact rows
- **Date Keys:** Integer `YYYYMMDD` role-played from `dim_date`
- **Orchestration:** `gold.gold_master` stored procedure with dependency-safe execution

[Detailed Gold Documentation >](./scripts/gold/README.md)

---

## Data Sources

### Source 1: Neon PostgreSQL (Relational Database)

| Bronze Table | Silver Table | Rows | Description |
|-------------|-------------|------|-------------|
| `bronze.customers` | `silver.customers` | ~99K | Customer demographics with ZIP/city/state |
| `bronze.orders` | `silver.orders` | ~99K | Order headers with status and timestamps |
| `bronze.order_items` | `silver.order_items` | ~113K | Line items with price, freight, product/seller |
| `bronze.order_payments` | `silver.order_payments` | ~104K | Payment methods, values, installments |
| `bronze.order_reviews` | `silver.order_reviews` | ~100K | Review scores and comment text |
| `bronze.sellers` | `silver.sellers` | ~3K | Seller demographics with ZIP/city/state |
| `bronze.products` | `silver.products` | ~33K | Product catalog with category, weight, dimensions |
| `bronze.product_category_name_translation` | (joined to products) | 71 | Portuguese -> English category mapping |

### Source 2: Google Sheets (Cloud Storage)

| Bronze Table | Silver Table | Rows | Description |
|-------------|-------------|------|-------------|
| `bronze.closed_deals` | `silver.closed_deals` | ~842 | Won deals with seller, date, value |
| `bronze.marketing_qualified_leads` | `silver.marketing_qualified_leads` | ~8K | Lead acquisition with UTM/channel data |

### Source 3: Google Apps Script API (Custom API)

| Bronze Table | Silver Table | Rows | Description |
|-------------|-------------|------|-------------|
| `bronze.geolocation` | (Silver excluded -- not in final schema) | ~856K | Brazilian ZIP codes with lat/long coordinates |

> **Note:** The `geolocation` table is intentionally excluded from the Silver and Gold layers as it is not part of the final Galaxy Schema. It remains available in Bronze for potential future geospatial analysis.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Languages** | Python 3.9+ | Bronze ingestion pipelines |
| | T-SQL (Transact-SQL) | Silver transformations, Gold modeling, stored procedures |
| | Google Apps Script | Geolocation microservice API |
| **Databases** | SQL Server 2022 | Destination data warehouse (BI_AI database) |
| | Neon PostgreSQL | Source operational database |
| **Python Libraries** | `pandas` | Data manipulation and transformation |
| | `sqlalchemy` + `pyodbc` | Database connectivity |
| | `psycopg2-binary` | PostgreSQL source connection |
| | `python-dotenv` | Environment variable management |
| | `requests` | HTTP API calls |
| | `openpyxl` | Excel/Sheets parsing |
| **Cloud** | Google Drive API | Marketing data ingestion |
| | Google Apps Script | Geolocation API endpoint |
| **Architecture** | Medallion (Bronze/Silver/Gold) | Data organization and quality gates |
| | Kimball Galaxy Schema | Analytical presentation layer |
| | ELT Pattern | Extract -> Load -> Transform workflow |

---

## Repository Structure

```
data-warehouse-from-scratch/
|
|-- ingestion/                          # Bronze Layer -- Python ELT pipelines
|   |-- __init__.py
|   |-- db_connections.py              # Centralized DB connection manager (SQL Server + PostgreSQL)
|   |-- ingest_neon_postgres.py        # Pipeline 1: Extract 7 tables from Neon PostgreSQL
|   |-- ingest_google_drive.py         # Pipeline 2: Extract 3 tables from Google Sheets
|   |-- ingest_geolocation_api.py      # Pipeline 3: Extract 856K geolocation rows from GAS API
|   |-- run_all_ingestion.py           # Orchestrator: Runs all 3 pipelines sequentially
|   |-- data_validation.sql            # Bronze quality checks (NULLs, dupes, RI)
|   |-- README.md                      # Detailed Bronze layer documentation
|
|-- scripts/
|   |-- bronze/                        # (Bronze DDL handled by Python ingestion)
|   |
|   |-- silver/                        # Silver Layer -- T-SQL cleaning & standardization
|   |   |-- Silver_layer_transformation.sql   # Silver DDL (schema, table creation)
|   |   |-- load_customers.sql         # Load silver.customers (dedupe, clean, standardize)
|   |   |-- load_sellers.sql           # Load silver.sellers
|   |   |-- load_products.sql          # Load silver.products
|   |   |-- load_orders.sql            # Load silver.orders (date sentinels, status mapping)
|   |   |-- load_order_items.sql       # Load silver.order_items
|   |   |-- load_order_payments.sql    # Load silver.order_payments (payment type labels)
|   |   |-- load_order_reviews.sql     # Load silver.order_reviews
|   |   |-- load_closed_deals.sql      # Load silver.closed_deals
|   |   |-- load_marketing_qualified_leads.sql  # Load silver.marketing_qualified_leads
|   |   |-- silver_master.sql          # Orchestrator: Runs all 9 loads in dependency order
|   |   |-- silver_quality_checks.sql  # Comprehensive Silver quality audit
|   |   |-- README.md                  # Detailed Silver layer documentation
|   |
|   |-- gold/                          # Gold Layer -- Kimball dimensional modeling
|       |-- gold_ddl_dimensions.sql    # Create gold schema + 7 dimension tables
|       |-- gold_generate_dim_date.sql # Populate conformed date spine (2016--2020)
|       |-- gold_ddl_facts.sql         # Create 5 fact tables + outrigger + FK constraints
|       |-- gold_load_dim_customer.sql     # MERGE load dim_customer (SCD Type 1)
|       |-- gold_load_dim_product.sql      # MERGE load dim_product
|       |-- gold_load_dim_seller.sql       # MERGE load dim_seller
|       |-- gold_load_dim_marketing_channel.sql  # MERGE load dim_marketing_channel
|       |-- gold_load_fact_order_items.sql     # TRUNCATE+INSERT fact_order_items
|       |-- gold_load_fact_payments.sql        # TRUNCATE+INSERT fact_payments
|       |-- gold_load_fact_reviews.sql         # TRUNCATE+INSERT fact_reviews + outrigger
|       |-- gold_load_fact_order_life_cycle.sql # TRUNCATE+INSERT fact_order_life_cycle
|       |-- gold_load_fact_marketing_funnel.sql # TRUNCATE+INSERT fact_marketing_funnel
|       |-- gold_master.sql            # Orchestrator: Runs all Gold loads in dependency order
|       |-- drawSQL-sqlsrv-export-2026-05-12.sql  # Database diagram export
|       |-- README.md                  # Detailed Gold layer documentation
|
|-- geolocation_api.gs                 # Google Apps Script: Geolocation microservice
|-- requirements.txt                   # Python dependencies
|-- .gitignore                         # Git ignore rules
|-- README.md                          # This file
```

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.9+ | For Bronze ingestion |
| SQL Server | 2019+ or Express | Destination database |
| ODBC Driver | 17+ | For pyodbc connectivity |
| PostgreSQL client | (optional) | For direct source inspection |
| `.env` file | | See environment variables below |

### Required Environment Variables

Create a `.env` file in the project root:

```env
# SQL Server (Destination)
SQL_SERVER=localhost
SQL_DATABASE=BI_AI
SQL_DRIVER=ODBC Driver 17 for SQL Server
SQL_TRUSTED_CONNECTION=yes

# Neon PostgreSQL (Source)
NEON_HOST=your-neon-host.neon.tech
NEON_PORT=5432
NEON_DATABASE=olist
NEON_USER=your-username
NEON_PASSWORD=your-password

# Google Drive (Source)
GOOGLE_SHEET_ID=your-google-sheet-id
```

### Installation

```bash
# Clone the repository
git clone https://github.com/jagter4b/data-warehouse-from-scratch.git
cd data-warehouse-from-scratch

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify SQL Server database exists
# Create database [BI_AI] if not present
```

### Running the Pipeline

The pipeline runs in three sequential stages:

#### Stage 1: Bronze Ingestion (Python)

```bash
python ingestion/run_all_ingestion.py
```

This runs all 3 ingestion pipelines:
1. Neon PostgreSQL (7 tables, ~159s)
2. Google Drive (3 tables, ~93s)
3. Geolocation API (1 table, ~54s)

Verify: All 11 tables should appear in `[BI_AI].[bronze]`.

#### Stage 2: Silver Transformation (T-SQL)

```sql
-- In SQL Server Management Studio (SSMS) or sqlcmd:
USE [BI_AI];
EXEC silver.silver_master;
```

Verify: 9 cleaned tables should appear in `[BI_AI].[silver]`.

#### Stage 3: Gold Dimensional Modeling (T-SQL)

```sql
-- Prerequisites (run once):
:r ./scripts/gold/gold_ddl_dimensions.sql
:r ./scripts/gold/gold_generate_dim_date.sql
:r ./scripts/gold/gold_ddl_facts.sql

-- Deploy load procedures (run once):
:r ./scripts/gold/gold_load_dim_customer.sql
:r ./scripts/gold/gold_load_dim_product.sql
:r ./scripts/gold/gold_load_dim_seller.sql
:r ./scripts/gold/gold_load_dim_marketing_channel.sql
:r ./scripts/gold/gold_load_fact_order_items.sql
:r ./scripts/gold/gold_load_fact_payments.sql
:r ./scripts/gold/gold_load_fact_reviews.sql
:r ./scripts/gold/gold_load_fact_order_life_cycle.sql
:r ./scripts/gold/gold_load_fact_marketing_funnel.sql
:r ./scripts/gold/gold_master.sql

-- Run full Gold layer:
USE [BI_AI];
EXEC gold.gold_master;
```

Verify: 7 dimensions + 5 facts + 1 outrigger in `[BI_AI].[gold]`.

---

## Schema Documentation

### Bronze Layer (`bronze` schema)

| Table | Source | PK | Row Count | Description |
|-------|--------|-----|-----------|-------------|
| `customers` | PostgreSQL | `customer_id` | ~99K | Customer demographics |
| `orders` | PostgreSQL | `order_id` | ~99K | Order headers with timestamps |
| `order_items` | PostgreSQL | `order_id, order_item_id` | ~113K | Line items |
| `order_payments` | PostgreSQL | `order_id, payment_sequential` | ~104K | Payment records |
| `order_reviews` | PostgreSQL | `review_id` | ~100K | Customer reviews |
| `sellers` | PostgreSQL | `seller_id` | ~3K | Seller demographics |
| `products` | PostgreSQL | `product_id` | ~33K | Product catalog |
| `product_category_name_translation` | PostgreSQL | `product_category_name` | 71 | Category translations |
| `closed_deals` | Google Sheets | `mql_id` | ~842 | Won deals |
| `marketing_qualified_leads` | Google Sheets | `mql_id` | ~8K | Marketing leads |
| `geolocation` | GAS API | `geolocation_zip_code_prefix` | ~856K | ZIP code coordinates |

### Silver Layer (`silver` schema)

| Table | Bronze Source | Cleaning Applied | Row Count |
|-------|--------------|-----------------|-----------|
| `customers` | `bronze.customers` | Deduplicate on `customer_unique_id`, trim, case standardize | ~99K |
| `orders` | `bronze.orders` | Date casting, sentinel dates, status standardization | ~99K |
| `order_items` | `bronze.order_items` | Type casting, decimal precision | ~113K |
| `order_payments` | `bronze.order_payments` | Payment type human-readable labels | ~104K |
| `order_reviews` | `bronze.order_reviews` | Text trimming, date casting | ~100K |
| `sellers` | `bronze.sellers` | ZIP zero-padding, case standardize | ~3K |
| `products` | `bronze.products` | Category English translation, dimension standardize | ~33K |
| `closed_deals` | `bronze.closed_deals` | Date casting, value standardization | ~842 |
| `marketing_qualified_leads` | `bronze.marketing_qualified_leads` | Channel parsing, date casting | ~8K |

### Gold Layer (`gold` schema)

See [Gold Layer Documentation](./scripts/gold/README.md) for complete dimensional model documentation.

---

## Data Quality

Quality checks are implemented at every layer:

### Bronze Quality Checks

[`ingestion/data_validation.sql`](./ingestion/data_validation.sql) validates:
- NULL percentage profiling per column
- Primary key uniqueness checks
- Cross-table referential integrity (e.g., every `order_item.order_id` exists in `orders`)
- Data type validation
- Source completeness row counts

### Silver Quality Checks

[`scripts/silver/silver_quality_checks.sql`](./scripts/silver/silver_quality_checks.sql) validates:
- Row count consistency (Bronze vs Silver)
- No unexpected NULLs in required fields
- Data type casting success
- Categorical value validation (payment types, order statuses)
- Cross-table referential integrity within Silver
- Duplicate detection post-dedup

### Gold Quality Checks

Post-deployment validation queries verify:
- Dimension row counts match expectations
- Fact row counts match source
- No orphaned foreign keys (every fact FK resolves to a dimension row or unknown member)
- Sentinel rows present in all dimensions (SK = -1)
- Date spine completeness (no gaps in 2016--2020)

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **ELT over ETL** | Load raw first, transform in-database. Simpler pipeline, preserves lineage, leverages SQL Server for set-based operations |
| **Medallion Architecture** | Clear separation of concerns: Bronze (land), Silver (clean), Gold (model). Enables iterative quality improvement |
| **SCD Type 1 (not Type 2)** | Olist is a static historical dataset with no attribute changes over time. Type 1 avoids row explosion and complexity |
| **TRUNCATE+INSERT for Facts** | Dataset is small enough (~1.3M rows total) that full reload is seconds. Eliminates incremental complexity |
| **Integer Date Keys (YYYYMMDD)** | Self-documenting, range-friendly, enables date filtering without joining dim_date |
| **Galaxy Schema** | Integrates e-commerce + marketing domains with shared conformed dimensions for cross-domain analysis |
| **MERGE for Dimensions** | Idempotent upsert pattern handles both inserts and updates safely on re-runs |
| **Unknown Members (SK = -1)** | Ensures FK integrity even when dimension lookups fail -- no orphaned fact rows |
| **Sentinel Dates** | `1900-01-01` (unknown) and `9999-12-31` (not yet occurred) eliminate NULL date keys |
| **Review Comments Outrigger** | Separates large text from fact table to keep analytical queries fast |
| **Geolocation Excluded** | 856K geolocation rows not needed for current Galaxy Schema. Available in Bronze for future use |
| **Dynamic Batch Size** | `safe_chunk = floor(2000 / num_cols)` automatically handles SQL Server's 2100-parameter limit |

---

## Performance Metrics

### Ingestion Performance (Bronze)

| Pipeline | Tables | Rows | Duration | Rows/Second |
|----------|--------|------|----------|-------------|
| Neon PostgreSQL | 7 | ~450,000 | 159.2s | ~2,826 |
| Google Drive | 3 | ~108,000 | 93.3s | ~1,157 |
| Geolocation API | 1 | ~856,000 | 53.5s | ~15,999 |
| **Total** | **11** | **~1,414,000** | **306s** | **~4,621** |

### Transformation Performance (Silver)

| Procedure | Table | Rows | Duration |
|-----------|-------|------|----------|
| `load_customers` | `silver.customers` | 99,441 | ~10s |
| `load_sellers` | `silver.sellers` | 3,095 | ~1s |
| `load_products` | `silver.products` | 32,951 | ~0s |
| `load_orders` | `silver.orders` | 99,441 | ~1s |
| `load_order_items` | `silver.order_items` | 112,650 | ~1s |
| `load_order_payments` | `silver.order_payments` | 103,886 | ~1s |
| `load_order_reviews` | `silver.order_reviews` | 99,441 | ~1s |
| `load_closed_deals` | `silver.closed_deals` | 842 | ~0s |
| `load_marketing_qualified_leads` | `silver.marketing_qualified_leads` | 7,980 | ~0s |
| **Total** | | **~558,727** | **~15s** |

### Gold Layer Load Performance

| Procedure | Target | Rows | Duration |
|-----------|--------|------|----------|
| `load_dim_customer` | `dim_customer` | 96,000 | ~2s |
| `load_dim_product` | `dim_product` | 32,000 | ~1s |
| `load_dim_seller` | `dim_seller` | 3,000 | ~0s |
| `load_dim_marketing_channel` | `dim_marketing_channel` | ~20 | ~0s |
| `load_fact_order_items` | `fact_order_items` | 112,650 | ~3s |
| `load_fact_payments` | `fact_payments` | 103,886 | ~2s |
| `load_fact_reviews` | `fact_reviews` | 99,441 | ~2s |
| `load_fact_order_life_cycle` | `fact_order_life_cycle` | 99,441 | ~2s |
| `load_fact_marketing_funnel` | `fact_marketing_funnel` | 7,980 | ~1s |
| **Total** | | **~554,418** | **~13s** |

**Full Pipeline End-to-End:** ~5 minutes (Bronze + Silver + Gold)

---

## Roadmap

### Completed

- [x] Bronze Layer: Multi-source ingestion (PostgreSQL, Google Sheets, REST API)
- [x] Bronze Layer: Data quality profiling and validation
- [x] Silver Layer: Data cleaning, deduplication, and standardization
- [x] Silver Layer: Data quality checks and referential integrity audits
- [x] Gold Layer: Dimensional modeling (Kimball Galaxy Schema)
- [x] Gold Layer: Conformed date dimension with role-playing
- [x] Gold Layer: ETL stored procedures with MERGE and TRUNCATE+INSERT patterns
- [x] Gold Layer: Master orchestration with dependency management
- [x] Gold Layer: Foreign key constraint enforcement

### In Progress

- [ ] Power BI: Semantic model and relationship design
- [ ] Power BI: Sales and revenue dashboards
- [ ] Power BI: Delivery performance and logistics dashboards
- [ ] Power BI: Marketing funnel and CAC dashboards
- [ ] Power BI: Customer satisfaction (NPS/review) dashboards

### Future Enhancements

- [ ] Implement SCD Type 2 for customer dimension (track address changes)
- [ ] Add incremental loading for daily delta processing
- [ ] Deploy to cloud SQL (Azure SQL / AWS RDS)
- [ ] Add Airflow/Docker orchestration
- [ ] Implement data observability (Great Expectations)
- [ ] Add geospatial analysis (delivery route optimization)
- [ ] Real-time streaming pipeline (Kafka/Debezium)

---

## Contributing

This is a portfolio project demonstrating end-to-end data warehouse engineering skills. While not actively seeking contributions, feedback and suggestions are welcome via Issues.

### Development Guidelines

- Follow existing naming conventions (`*_sk` for surrogate keys, `*_bk` for business keys)
- Maintain idempotency in all load procedures
- Add comments to all SQL scripts explaining grain, join paths, and business logic
- Update quality check scripts when adding new tables or columns
- Test `gold_master` and `silver_master` end-to-end before committing

---

## License

This project is for educational purposes. The underlying Olist datasets are published under the [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license via Kaggle.

---

*Built as a capstone project to demonstrate production-grade Data Warehouse engineering -- from raw ingestion to dimensional modeling.*
