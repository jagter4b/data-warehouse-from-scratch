# 🏭 Olist Data Warehouse, ML Analytics & AI Assistant — Complete Project Documentation

---

## 📑 Table of Contents

1. [Executive Summary & Project Overview](#-1-executive-summary--project-overview)
2. [System Architecture & Medallion Design](#-2-system-architecture--medallion-design)
3. [Tech Stack & Prerequisites](#-3-tech-stack--prerequisites)
4. [Installation & Environment Setup](#-4-installation--environment-setup)
5. [Bronze Layer — Data Ingestion Pipeline](#-5-bronze-layer--data-ingestion-pipeline)
6. [Silver Layer — Transformation Pipeline](#-6-silver-layer--transformation-pipeline)
7. [Gold Layer — Kimball Galaxy Schema & Data Warehouse](#-7-gold-layer--kimball-galaxy-schema--data-warehouse)
8. [Complete Data Dictionary](#-8-complete-data-dictionary)
9. [Feature Store — One Big Tables (OBTs)](#-9-feature-store--one-big-tables-obts)
10. [Machine Learning Pipeline (7 Models)](#-10-machine-learning-pipeline-7-models)
11. [Streamlit Analytics Dashboard](#-11-streamlit-analytics-dashboard)
12. [SQL Assistant — AI BI Agent](#-12-sql-assistant--ai-bi-agent)
13. [End-to-End Pipeline Execution Runbook](#-13-end-to-end-pipeline-execution-runbook)
14. [Data Quality Audits & Verification](#-14-data-quality-audits--verification)
15. [Key Design Decisions & Limitations](#-15-key-design-decisions--limitations)

---

## 🎯 1. Executive Summary & Project Overview

This project represents a **production-grade, end-to-end Data Engineering, Machine Learning, and AI Analytics Platform** built entirely from scratch. It processes raw e-commerce and marketing data through an automated **Medallion Architecture (Bronze → Silver → Gold → ML)** on Microsoft SQL Server 2022, powering 7 predictive machine learning models, an interactive Streamlit dashboard, and an AI-driven SQL query assistant.

### Key Platform Achievements
- **Multi-Source Automated Ingestion:** Extracted ~1.28M rows across 11 raw tables from Neon PostgreSQL, Google Drive (CSV + Google Sheets), and a custom Google Apps Script REST API.
- **Idempotent T-SQL Transformations:** Implemented 9 idempotent stored procedures handling deduplication, string standardization, Title Case conversions, date sentinel mapping, and null handling.
- **Kimball Galaxy Schema:** Engineered a dual-subject area dimensional model featuring 7 conformed/shared dimensions, 5 fact tables (including an Accumulating Snapshot), and 1 outrigger table.
- **Unified Feature Stores:** Built 3 denormalized One Big Tables (OBTs) serving as feature stores for downstream ML tasks.
- **Predictive Machine Learning:** Trained and evaluated 7 machine learning models (XGBoost, Random Forest, K-Means) covering customer segmentation, churn prediction, LTV estimation, seller performance scoring, seller churn, delivery risk prediction, and review score forecasting.
- **Interactive Visual Analytics:** Created a 4-page dark glassmorphism Streamlit dashboard featuring live database queries and static CSV fallback (Demo Mode).
- **Bilingual AI BI Agent (SQL Assistant):** Built a natural-language SQL BI assistant using Google Gemini (with automatic model fallback) supporting English and Egyptian Arabic, protected by a 4-layer security validation engine.

---

## 🏗️ 2. System Architecture & Medallion Design

The platform strictly enforces the **Medallion Architecture**, establishing clear boundaries between raw ingestion, cleaning, business logic, feature engineering, and presentation.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                  │
│                                                                         │
│  ┌────────────────────┐  ┌────────────────────┐  ┌───────────────────┐  │
│  │  Neon PostgreSQL   │  │    Google Drive    │  │  Geolocation REST │  │
│  │ (7 E-Commerce tbls)│  │ (MQLs, Deals, Rev) │  │  API (856K rows)  │  │
│  └─────────┬──────────┘  └─────────┬──────────┘  └─────────┬─────────┘  │
└────────────┼───────────────────────┼───────────────────────┼────────────┘
             │ Python (`ingestion/`) │                       │
             ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        🥉 BRONZE LAYER (Raw)                            │
│                      SQL Server: `[BI_AI].[bronze]`                     │
│                                                                         │
│  • 11 Raw Tables (~1.28M rows)                                          │
│  • Ingestion Audit Metadata (`_ingested_at`, `_source`)                 │
│  • Idempotent: Full Drop & Recreate per run                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ T-SQL Stored Procedures
                                 │ `EXEC silver.silver_master`
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      🥈 SILVER LAYER (Cleaned)                          │
│                      SQL Server: `[BI_AI].[silver]`                     │
│                                                                         │
│  • 9 Standardized Tables (~550K rows)                                   │
│  • Deduplication via ROW_NUMBER() OVER (PARTITION BY PK)                │
│  • Title Case, Sentinel Dates ('1900-01-01', '9999-12-31')              │
│  • Financial decimal casting & Portuguese-to-English mapping            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ T-SQL Stored Procedures
                                 │ `EXEC gold.gold_master`
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    🥇 GOLD LAYER (Dimensional Schema)                   │
│                       SQL Server: `[BI_AI].[gold]`                      │
│                                                                         │
│  Kimball Galaxy Schema:                                                 │
│  • 7 Dimensions (Shared `dim_seller`, Conformed `dim_date`)             │
│  • 5 Fact Tables (Transactional & Accumulating Snapshot)                │
│  • 1 Outrigger (`review_comments` for CCI compression)                  │
└────────────┬──────────────────────────────────────────────┬─────────────┘
             │                                              │
             │ Python (`scripts/ml/create_obt_master.py`)   │ Direct SQL
             ▼                                              ▼
┌─────────────────────────────────────────┐   ┌───────────────────────────┐
│        📊 OBT FEATURE STORES            │   │  💬 SQL ASSISTANT AGENT   │
│  `gold.obt_customers`  (96K rows)       │   │   • Google Gemini API     │
│  `gold.obt_sellers`    (3.1K rows)      │   │   • Schema Auto-Discovery │
│  `gold.obt_orders`     (99.4K rows)     │   │   • 4-Layer Security      │
└────────────┬────────────────────────────┘   └───────────────────────────┘
             │ Python ML (`scripts/ml/`)
             ▼
┌─────────────────────────────────────────┐
│          🤖 7 ML MODELS                 │
│  RFM K-Means, RF Churn, XGB LTV,        │
│  Seller Score, Seller Churn,            │
│  Delivery Risk, Review Regressor        │
└────────────┬────────────────────────────┘
             │ Predictions written back
             ▼
┌─────────────────────────────────────────┐
│       📈 STREAMLIT DASHBOARD            │
│  Live SQL Server + CSV Fallback Mode    │
└─────────────────────────────────────────┘
```

---

## 🛠️ 3. Tech Stack & Prerequisites

### Technology Stack Table

| Domain | Technology | Version / Specification | Usage |
|--------|------------|-------------------------|-------|
| **Database Engine** | Microsoft SQL Server | 2022 Developer / Enterprise | Target Data Warehouse (`BI_AI`) |
| **Source Engine** | Neon PostgreSQL | Serverless Postgres | E-commerce source data host |
| **Languages** | Python, T-SQL | Python 3.9+, T-SQL (MSSQL 2022) | Ingestion scripts, SPs, ML pipeline |
| **ODBC Drivers** | Microsoft ODBC Driver | Driver 17 / Driver 18 | Connectivity to SQL Server |
| **Data Libraries** | Pandas, SQLAlchemy, PyODB, Psycopg2 | Latest stable | Data manipulation, connection pooling |
| **Machine Learning** | Scikit-learn, XGBoost, Imbalanced-learn | sklearn 1.4+, xgboost 2.0+ | Model training, SMOTE, evaluation |
| **Analytics UI** | Streamlit, Plotly Express | Streamlit 1.30+ | Web application, custom CSS themes |
| **AI LLM API** | Google Gemini API | `google-genai` SDK | NL-to-SQL translation, explanations |

### System Prerequisites
1. **Python 3.9+** installed and added to PATH.
2. **Microsoft SQL Server 2022** (local instance or network server named `BI_AI`). SQL Server 2022 is required for `STRING_SPLIT(str, delimiter, enable_ordinal)`.
3. **Microsoft ODBC Driver 17 for SQL Server**.

---

## ⚙️ 4. Installation & Environment Setup

### 1. Repository Clone & Environment Creation
```bash
git clone https://github.com/jagter4b/data-warehouse-from-scratch.git
cd data-warehouse-from-scratch

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux / macOS

# Install base dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration (`.env`)
Create a `.env` file in the project root directory:

```env
# Source Database (Neon PostgreSQL)
SOURCE_DB_HOST=ep-example-123456.us-east-2.aws.neon.tech
SOURCE_DB_PORT=5432
SOURCE_DB_NAME=neondb
SOURCE_DB_USER=neon_user
SOURCE_DB_PASSWORD=neon_password
SOURCE_DB_SSL_MODE=require

# Destination Database (SQL Server)
DEST_DB_HOST=localhost
DEST_DB_PORT=1433
DEST_DB_NAME=BI_AI
DEST_DB_TRUSTED_CONNECTION=yes

# Google Gemini API Key (for SQL Assistant)
Gemini_API_Key=AIzaSyYourGeminiApiKeyHere
```

### 3. Database Initialization (SQL Server)
Execute the following commands in SQL Server Management Studio (SSMS) or via `sqlcmd`:

```sql
CREATE DATABASE [BI_AI];
GO

USE [BI_AI];
GO
CREATE SCHEMA bronze;
GO
CREATE SCHEMA silver;
GO
CREATE SCHEMA gold;
GO
```

---

## 🥉 5. Bronze Layer — Data Ingestion Pipeline

The Bronze layer ingests raw data AS-IS from three disparate data sources without applying business transformations.

### Ingestion Performance Summary

| Ingestion Script | Source System | Target Table(s) | Rows Loaded | Time | Strategy |
|------------------|---------------|-----------------|-------------|------|----------|
| `ingest_neon_postgres.py` | Neon PostgreSQL | `bronze.customers`<br>`bronze.orders`<br>`bronze.order_items`<br>`bronze.order_payments`<br>`bronze.sellers`<br>`bronze.products`<br>`bronze.product_category_name_translation` | 99,441<br>99,441<br>112,650<br>103,886<br>3,095<br>32,951<br>71 | 159.2s | Drop & Create (Full Load) |
| `ingest_google_drive.py` | Google Drive API / Export | `bronze.order_reviews`<br>`bronze.marketing_qualified_leads`<br>`bronze.closed_deals` | 100,000<br>8,000<br>842 | 93.3s | Drop & Create (Full Load) |
| `ingest_geolocation_api.py` | Google Apps Script REST API | `bronze.geolocation` | 855,781 | 53.5s | Drop & Create (Chunked API) |
| **Total Ingestion** | **3 Sources** | **11 Tables** | **~1.28 Million Rows** | **306s** | **Fully Idempotent** |

### Bronze Technical Highlights
- **Audit Columns:** Every inserted row is appended with `_ingested_at` (`DATETIME2`), `_source` (`NVARCHAR`), and source-specific metadata.
- **SQL Server Parameter Limit Handling:** Implemented dynamic chunk sizing (`safe_chunk = floor(2000 / num_cols)`) in Python to prevent hitting SQL Server's 2,100 parameter limit in ODBC multi-row inserts.
- **Google Sheets API Bypassing:** For `order_reviews`, the script programmatically constructs direct Google Sheet export links to stream data without complex OAuth web flows.

---

## 🥈 6. Silver Layer — Transformation Pipeline

The Silver layer cleans, standardizes, deduplicates, and validates data using 9 modular T-SQL stored procedures managed by `silver.silver_master`.

### Silver Transformation Summary

| Stored Procedure | Source → Target | Transformations Applied | Rows Loaded |
|------------------|-----------------|-------------------------|-------------|
| `silver.load_customers` | `bronze.customers` → `silver.customers` | • `LTRIM(RTRIM)` string whitespace<br>• Zero-pad 5-digit ZIP codes: `RIGHT('00000' + CAST(zip AS VARCHAR(5)), 5)`<br>• Uppercase `customer_city` and `customer_state`<br>• Deduplication via `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY _ingested_at DESC)` | 99,441 |
| `silver.load_sellers` | `bronze.sellers` → `silver.sellers` | • `LTRIM(RTRIM)` and zero-pad ZIP code<br>• Uppercase city/state with NULL fallbacks to `'Not Specified'`<br>• Deduplicate by `seller_id` | 3,095 |
| `silver.load_products` | `bronze.products` → `silver.products` | • LEFT JOIN `product_category_name_translation` to translate Portuguese snake_case to English<br>• Convert snake_case to Title Case using `STRING_SPLIT(..., 1)` and `STRING_AGG`<br>• Fix source column typos (`lenght` → `length`) and cast floats to INT | 32,951 |
| `silver.load_orders` | `bronze.orders` → `silver.orders` | • Lowercase `order_status`<br>• Safe date casting using `TRY_CAST(... AS DATE)`<br>• Context-aware sentinels: `'1900-01-01'` for missing/canceled, `'9999-12-31'` for active in-transit orders | 99,441 |
| `silver.load_order_items` | `bronze.order_items` → `silver.order_items` | • Cast `price` and `freight_value` to `DECIMAL(10,2)`<br>• Map NULL foreign keys to `'UNKNOWN'` | 112,650 |
| `silver.load_order_payments` | `bronze.order_payments` → `silver.order_payments` | • Map snake_case `payment_type` (`credit_card` → `'Credit Card'`, `boleto` → `'Boleto'`)<br>• Cast `payment_value` to `DECIMAL(10,2)` | 103,886 |
| `silver.load_order_reviews` | `bronze.order_reviews` → `silver.order_reviews` | • **Deduplication:** Dropped 559 duplicate `review_id` instances keeping the latest answered review<br>• Cast `review_score` string to `TINYINT`<br>• Replace NULL titles/messages with sentinels (`'No Title'`, `'No Message'`) | 99,441 |
| `silver.load_marketing_qualified_leads` | `bronze.marketing_qualified_leads` → `silver.marketing_qualified_leads` | • Standardize `origin` channels (`organic_search` → `'Organic Search'`, `paid_search` → `'Paid Search'`) | 8,000 |
| `silver.load_closed_deals` | `bronze.closed_deals` → `silver.closed_deals` | • Title Case `business_segment` and `lead_type`<br>• Convert float boolean indicators (`has_company`, `has_gtin`) to `TINYINT`<br>• Cast financial declarations to `DECIMAL(10,2)` | 842 |

### Master Orchestration (`silver.silver_master`)
```sql
CREATE PROCEDURE silver.silver_master AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        EXEC silver.load_customers;
        EXEC silver.load_sellers;
        EXEC silver.load_products;
        EXEC silver.load_orders;
        EXEC silver.load_order_items;
        EXEC silver.load_order_payments;
        EXEC silver.load_order_reviews;
        EXEC silver.load_marketing_qualified_leads;
        EXEC silver.load_closed_deals;
    END TRY
    BEGIN CATCH
        THROW;
    END CATCH
END;
```

---

## 🥇 7. Gold Layer — Kimball Galaxy Schema & Data Warehouse

The Gold layer models business entities into a **Kimball Galaxy Schema** featuring two distinct subject areas (E-Commerce and Marketing Funnel) connected via conformed and shared dimensions.

```
                  E-COMMERCE SUBJECT AREA                     MARKETING SUBJECT AREA
              ┌─────────────────────────────┐             ┌─────────────────────────────┐
              │  gold.fact_order_items      │             │  gold.fact_marketing_funnel │
              │  gold.fact_payments         │             │                             │
              │  gold.fact_reviews          │             │  • declared_monthly_revenue │
              │  gold.fact_order_life_cycle │             │  • declared_catalog_size    │
              └──────────────┬──────────────┘             └──────────────┬──────────────┘
                             │                                           │
                             ├──────────────┐            ┌───────────────┤
                             ▼              ▼            ▼               ▼
                      ┌──────────────┐  ┌────────────────────┐  ┌───────────────────────┐
                      │ dim_customer │  │    dim_seller      │  │ dim_marketing_channel │
                      │ dim_product  │  │ (SHARED DIMENSION) │  │                       │
                      │ dim_status   │  └────────────────────┘  └───────────────────────┘
                      │ dim_payment  │             │
                      └──────────────┘             ▼
                                         ┌───────────────────┐
                                         │     dim_date      │
                                         │(CONFORMED DATE    │
                                         │     DIMENSION)    │
                                         └───────────────────┘
```

### Key Dimensional Strategies
1. **Conformed Date Dimension (`gold.dim_date`):** Populated using a recursive CTE covering 2016-01-01 to 2020-12-31 with explicit integer keys (`YYYYMMDD`). Includes sentinels `19000101` (Unknown/Missing) and `99991231` (Not Yet Occurred).
2. **Shared Seller Dimension (`gold.dim_seller`):** Connects e-commerce line-item sales (`fact_order_items`) with seller acquisition metrics (`fact_marketing_funnel`).
3. **Outrigger Pattern (`gold.review_comments`):** Free-text review titles and messages are separated from `fact_reviews` into a 1:1 outrigger table to prevent text fragmentation in SQL Server's Clustered Columnstore Indexes (CCI).
4. **Accumulating Snapshot (`gold.fact_order_life_cycle`):** Tracks the complete order milestone timeline (Purchase → Approval → Carrier Handoff → Delivery) in a single wide row with duration variance metrics.

---

## 📖 8. Complete Data Dictionary

### Dimensions

#### 1. `gold.dim_date` (Conformed Date Dimension)
- **Grain:** One row per calendar day (`date_key` = YYYYMMDD).

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `date_key` | `INT` | NO | **PK** | Integer surrogate date key (YYYYMMDD) |
| `full_date` | `DATE` | NO | — | Full calendar date |
| `day_of_week_num` | `TINYINT` | NO | — | ISO day number (1=Monday, 7=Sunday) |
| `day_of_week_name` | `VARCHAR(10)` | NO | — | English day name (e.g., 'Monday') |
| `day_of_month` | `TINYINT` | NO | — | Day of the month (1–31) |
| `day_of_year` | `SMALLINT` | NO | — | Day of the year (1–366) |
| `week_of_year` | `TINYINT` | NO | — | ISO week number (1–53) |
| `month_num` | `TINYINT` | NO | — | Month number (1–12) |
| `month_name` | `VARCHAR(10)` | NO | — | Full month name (e.g., 'January') |
| `quarter_num` | `TINYINT` | NO | — | Quarter number (1–4) |
| `quarter_name` | `CHAR(2)` | NO | — | Quarter string ('Q1'–'Q4') |
| `year` | `SMALLINT` | NO | — | Four-digit calendar year |
| `year_month` | `CHAR(7)` | NO | — | Year-month string ('YYYY-MM') |
| `is_weekend` | `BIT` | NO | — | Flag: 1 if Saturday or Sunday |
| `is_holiday` | `BIT` | NO | — | Placeholder flag for national holidays |

#### 2. `gold.dim_customer` (SCD Type 1)
- **Grain:** One row per unique customer person (`customer_unique_id_bk`).

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `customer_sk` | `INT IDENTITY` | NO | **PK** | Customer surrogate key (-1 = Unknown) |
| `customer_unique_id_bk` | `VARCHAR(32)` | NO | — | Natural person business key |
| `customer_zip_code_prefix` | `CHAR(5)` | NO | — | Zero-padded 5-digit postal code |
| `customer_city` | `VARCHAR(50)` | NO | — | Uppercased customer city |
| `customer_state` | `CHAR(2)` | NO | — | Two-letter state abbreviation |
| `load_timestamp` | `DATETIME2` | NO | — | MERGE processing timestamp |
| `source_system` | `VARCHAR(20)` | NO | — | Source system identifier |

#### 3. `gold.dim_product` (SCD Type 1)
- **Grain:** One row per product SKU.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `product_sk` | `INT IDENTITY` | NO | **PK** | Product surrogate key (-1 = Unknown) |
| `product_id_bk` | `VARCHAR(32)` | NO | — | Product UUID business key |
| `product_category_name` | `VARCHAR(100)` | YES | — | Translated English Title Case category |
| `product_name_length` | `INT` | YES | — | Character length of product title |
| `product_description_length` | `INT` | YES | — | Character length of product description |
| `product_photos_qty` | `INT` | YES | — | Number of gallery photos |
| `product_weight_g` | `INT` | YES | — | Weight in grams |
| `product_length_cm` | `INT` | YES | — | Length dimension in centimeters |
| `product_height_cm` | `INT` | YES | — | Height dimension in centimeters |
| `product_width_cm` | `INT` | YES | — | Width dimension in centimeters |

#### 4. `gold.dim_seller` (Shared Dimension, SCD Type 1)
- **Grain:** One row per seller.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `seller_sk` | `INT IDENTITY` | NO | **PK** | Seller surrogate key (-1 = Unknown) |
| `seller_id_bk` | `VARCHAR(32)` | NO | — | Seller UUID business key |
| `seller_zip_code_prefix` | `CHAR(5)` | NO | — | Zero-padded 5-digit postal code |
| `seller_city` | `VARCHAR(50)` | NO | — | Uppercased seller city |
| `seller_state` | `CHAR(2)` | NO | — | Two-letter state abbreviation |

#### 5. `gold.dim_marketing_channel` (SCD Type 1)
- **Grain:** One row per Marketing Qualified Lead (MQL).

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `mql_channel_sk` | `INT IDENTITY` | NO | **PK** | Marketing channel surrogate key |
| `mql_id_bk` | `VARCHAR(32)` | NO | — | MQL UUID business key |
| `origin` | `VARCHAR(30)` | NO | — | Marketing acquisition channel |
| `landing_page_id` | `VARCHAR(32)` | YES | — | Target landing page hash |
| `business_segment` | `VARCHAR(60)` | YES | — | Industry segment (for converted deals) |
| `lead_type` | `VARCHAR(20)` | YES | — | Lead category (e.g., 'Online Big') |
| `lead_behaviour_profile` | `VARCHAR(20)` | YES | — | Persona profile ('Cat', 'Eagle', etc.) |
| `business_type` | `VARCHAR(20)` | YES | — | Business model ('Reseller', 'Manufacturer') |
| `average_stock` | `VARCHAR(20)` | YES | — | Declared stock range |
| `has_company` | `TINYINT` | NO | — | Flag: 1 if registered company |
| `has_gtin` | `TINYINT` | NO | — | Flag: 1 if product GTIN barcode available |

---

### Fact Tables & Outrigger

#### 1. `gold.fact_order_items` (Transactional Fact)
- **Grain:** One row per individual order line item.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `order_item_sk` | `INT IDENTITY` | NO | **PK** | Fact surrogate key |
| `purchase_date_key` | `INT` | NO | **FK** (`dim_date`) | Order purchase date key |
| `shipping_limit_date_key` | `INT` | NO | **FK** (`dim_date`) | Seller shipping deadline date key |
| `customer_sk` | `INT` | NO | **FK** (`dim_customer`) | Resolved customer surrogate key |
| `product_sk` | `INT` | NO | **FK** (`dim_product`) | Product surrogate key |
| `seller_sk` | `INT` | NO | **FK** (`dim_seller`) | Seller surrogate key |
| `order_id_bk` | `VARCHAR(32)` | NO | — | Degenerate order ID dimension |
| `order_item_id_bk` | `INT` | NO | — | Line item sequence number within order |
| `unit_price` | `DECIMAL(10,2)` | NO | — | Unit selling price |
| `unit_freight_value` | `DECIMAL(10,2)` | NO | — | Shipping freight fee for item |
| `line_total` | `DECIMAL(10,2)` | NO | — | Calculated total (`unit_price + unit_freight_value`) |

#### 2. `gold.fact_payments` (Transactional Fact)
- **Grain:** One row per payment installment transaction sequence.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `payment_sk` | `INT IDENTITY` | NO | **PK** | Fact surrogate key |
| `purchase_date_key` | `INT` | NO | **FK** (`dim_date`) | Order purchase date key |
| `customer_sk` | `INT` | NO | **FK** (`dim_customer`) | Customer surrogate key |
| `payment_type_sk` | `INT` | NO | **FK** (`dim_payment_type`) | Payment method lookup key |
| `order_id_bk` | `VARCHAR(32)` | NO | — | Degenerate order ID dimension |
| `payment_sequential_bk` | `INT` | NO | — | Payment sequence number |
| `payment_value` | `DECIMAL(10,2)` | NO | — | Monetary payment amount |
| `payment_installments` | `INT` | NO | — | Number of payment installments |

#### 3. `gold.fact_reviews` (Transactional Fact)
- **Grain:** One row per order review.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `review_sk` | `INT IDENTITY` | NO | **PK** | Fact surrogate key |
| `review_creation_date_key` | `INT` | NO | **FK** (`dim_date`) | Date survey was sent to customer |
| `review_answer_date_key` | `INT` | NO | **FK** (`dim_date`) | Date customer answered review |
| `customer_sk` | `INT` | NO | **FK** (`dim_customer`) | Customer surrogate key |
| `review_id_bk` | `VARCHAR(32)` | NO | — | Review UUID business key |
| `order_id_bk` | `VARCHAR(32)` | NO | — | Degenerate order ID dimension |
| `review_score` | `TINYINT` | NO | — | Numerical review rating (1 to 5) |

#### 4. `gold.review_comments` (1:1 Outrigger Table)
- **Grain:** One row per review (stores text details).

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `review_sk` | `INT` | NO | **PK, FK** (`fact_reviews`) | Joins 1:1 to `fact_reviews.review_sk` |
| `review_comment_title` | `NVARCHAR(200)`| YES | — | Customer review title text |
| `review_comment_message`| `NVARCHAR(1000)`| YES | — | Customer review body message text |

#### 5. `gold.fact_order_life_cycle` (Accumulating Snapshot Fact)
- **Grain:** One row per order tracking fulfillment stage milestones.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `order_fulfillment_sk` | `INT IDENTITY` | NO | **PK** | Fact surrogate key |
| `purchase_date_key` | `INT` | NO | **FK** (`dim_date`) | Milestone 1: Purchase date |
| `approval_date_key` | `INT` | NO | **FK** (`dim_date`) | Milestone 2: Approval date |
| `carrier_date_key` | `INT` | NO | **FK** (`dim_date`) | Milestone 3: Carrier handoff date |
| `delivery_date_key` | `INT` | NO | **FK** (`dim_date`) | Milestone 4: Customer delivery date |
| `estimated_delivery_date_key`| `INT` | NO | **FK** (`dim_date`) | Promised delivery date |
| `customer_sk` | `INT` | NO | **FK** (`dim_customer`) | Customer surrogate key |
| `order_status_sk` | `INT` | NO | **FK** (`dim_order_status`) | Order status lookup key |
| `order_id_bk` | `VARCHAR(32)` | NO | — | Degenerate order ID dimension |
| `days_to_approve` | `INT` | YES | — | Lag: purchase → approval |
| `days_to_ship` | `INT` | YES | — | Lag: approval → carrier handoff |
| `days_to_deliver` | `INT` | YES | — | Lag: carrier handoff → customer delivery |
| `days_purchase_to_delivery` | `INT` | YES | — | Total lag: purchase → customer delivery |
| `days_delivery_variance` | `INT` | YES | — | Actual delivery date minus estimated date |
| `is_delivered_on_time` | `BIT` | YES | — | Flag: 1 if actual delivery <= estimated date |
| `total_items` | `INT` | NO | — | Count of items in order |
| `total_distinct_products` | `INT` | NO | — | Count of unique products in order |
| `total_distinct_sellers` | `INT` | NO | — | Count of unique sellers fulfilling order |
| `total_order_value` | `DECIMAL(10,2)`| NO | — | Sum of item unit prices |
| `total_freight_value` | `DECIMAL(10,2)`| NO | — | Sum of item freight values |
| `total_payment_value` | `DECIMAL(10,2)`| NO | — | Total payment value recorded |

#### 6. `gold.fact_marketing_funnel` (Transactional Fact)
- **Grain:** One row per closed marketing lead deal.

| Column Name | Data Type | Nullable | Primary / Foreign Key | Description |
|-------------|-----------|----------|-----------------------|-------------|
| `closed_deal_sk` | `INT IDENTITY` | NO | **PK** | Fact surrogate key |
| `first_contact_date_key` | `INT` | NO | **FK** (`dim_date`) | First lead contact date key |
| `won_date_key` | `INT` | NO | **FK** (`dim_date`) | Deal closed won date key |
| `seller_sk` | `INT` | NO | **FK** (`dim_seller`) | Onboarded seller key |
| `mql_channel_sk` | `INT` | NO | **FK** (`dim_marketing_channel`)| Acquisition channel key |
| `mql_id_bk` | `VARCHAR(32)` | NO | — | Lead MQL UUID natural key |
| `sdr_id_bk` | `VARCHAR(32)` | YES | — | Sales Development Representative ID |
| `sr_id_bk` | `VARCHAR(32)` | YES | — | Sales Representative ID |
| `days_to_close` | `INT` | YES | — | Lead conversion lag (won_date - first_contact) |
| `declared_monthly_revenue` | `DECIMAL(15,2)`| YES | — | Lead self-reported monthly revenue |
| `declared_product_catalog_size`|`DECIMAL(10,2)`| YES | — | Lead self-reported catalog size |

---

## 📊 9. Feature Store — One Big Tables (OBTs)

To bridge dimensional modeling with machine learning, `scripts/ml/create_obt_master.py` compiles the Gold schema into three denormalized **One Big Tables (OBTs)** serving as unified feature stores.

### Feature Store Summary

```
                 gold layer (facts + dimensions)
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│gold.obt_customers │ │ gold.obt_sellers  │ │  gold.obt_orders  │
│(96,097 Rows)      │ │ (3,096 Rows)      │ │  (99,441 Rows)    │
│• Recency, Freq    │ │ • Total Revenue   │ │ • Delay Risk      │
│• Monetary Spend   │ │ • On-Time Rate    │ │ • Review Score    │
│• Churn Labels     │ │ • Performance Score│ │ • Fulfillment Lags│
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

1. **`gold.obt_customers` (96,097 rows):** Aggregated at `customer_unique_id_bk` grain. Contains customer lifetime spend, total order count, recency days (relative to max date `2018-10-17`), review averages, and assigned customer segment.
2. **`gold.obt_sellers` (3,096 rows):** Aggregated at `seller_id_bk` grain. Contains lifetime revenue, total order volume, fulfillment speed metrics, review averages, marketing lead acquisition origin, and performance score.
3. **`gold.obt_orders` (99,441 rows):** Aggregated at `order_id_bk` grain. Combines customer state, seller state, delivery variance, line item totals, freight fees, review scores, and delay risk probabilities.

---

## 🤖 10. Machine Learning Pipeline (7 Models)

The machine learning pipeline evaluates models across Customer, Seller, and Order analytics. All ML scripts read from the OBT feature stores and update predictions in-place.

### Machine Learning Master Summary

| # | Domain | Analytical Task | Algorithm & Technique | Features Used | Target Metric / Evaluation Output |
|---|--------|-----------------|-----------------------|---------------|----------------------------------|
| 1 | **Customer** | Behavioral Segmentation | K-Means Clustering ($k=4$, Log Transform, StandardScaler) | Recency Days, Order Frequency, Monetary Total (log-transformed) | **Silhouette Score: 0.4788**<br>Clusters: Champions, Loyal, At Risk, Lost |
| 2 | **Customer** | Churn Risk Prediction | Random Forest Classifier + SMOTE Oversampling | Order Frequency, Monetary Spend, Avg Order Value, Avg Review Score, Delivery Speed, On-Time Rate | **AUC-ROC: 0.6829**<br>Target: Inactive >180 days (recency excluded to prevent target leakage) |
| 3 | **Customer** | Lifetime Value (LTV) | XGBoost Regressor | Order History, Category Variety, Payment Installments, Satisfaction Average | **$R^2$: 0.1710** (Leakage-Clean)<br>Tiers: Platinum, Gold, Silver, Bronze |
| 4 | **Seller** | Performance Scoring | Weighted Composite KPI + K-Means ($k=3$) | Avg Review Score (35%), On-Time Rate (30%), Total Revenue (20%), Total Orders (15%) | **Silhouette Score: 0.5679**<br>Tiers: Top Seller, Average, Underperformer |
| 5 | **Seller** | Seller Churn Prediction | XGBoost Classifier + Dynamic SMOTE | Revenue Trends, Recency, Delivery Variance, Review Averages | **AUC-ROC: 0.7846**<br>Output: Seller Churn Probability |
| 6 | **Order** | Delivery Delay Risk | XGBoost Classifier (`scale_pos_weight`) | Item Count, Order Value, Payment Installments, Purchase Month, Day of Week, Category, Seller/Customer State | **AUC-ROC: 0.7483**<br>Output: High Risk (≥40%), Medium Risk, Low Risk |
| 7 | **Order** | Review Score Forecasting | XGBoost Regressor | Days to Deliver, Delivery Variance, Freight Ratio, Customer/Seller Location | **RMSE: 1.1311** ($R^2 = 0.21$)<br>Classes: Excellent (≥4.5), Good, Average, Poor |

---

## 📈 11. Streamlit Analytics Dashboard

The platform includes a multi-page web application built with Streamlit and Plotly Express, featuring a dark glassmorphism design theme.

🚀 **Live Deployment URL:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

### Application Structure & Pages

```
streamlit/
├── app.py                          # Overview Page (KPI Header, Revenue Trends, State Map)
├── assets/
│   └── style.css                   # Dark Glassmorphism CSS Design System
├── components/
│   ├── db.py                       # DB Connection Engine + Demo Mode Fallback
│   └── filters.py                  # Global Sidebar Filter Components
├── pages/
│   ├── 1_Customer_Intelligence.py  # RFM Segments, Churn Tiers, LTV Distribution
│   ├── 2_Delivery_Analytics.py     # Delay Risk Gauge, Delivery Lags, Review Correlations
│   └── 3_Seller_Intelligence.py    # Seller Score Matrix, Funnel Origins, Top 20 Table
└── data/
    └── obt_master.csv              # Static CSV Snapshot (Auto-fallback for Cloud hosting)
```

### Automatic Demo Mode (CSV Fallback)
`components/db.py` attempts a direct SQL Server connection with a 5-second timeout. If the database is unreachable (e.g., hosted on Streamlit Cloud without access to a local SQL Server), it automatically switches to reading from `streamlit/data/obt_master.csv` and renders a blue **Demo Mode** indicator banner.

---

## 💬 12. SQL Assistant — AI BI Agent

Located in `sql_assistant/`, the **SQL Assistant** is an autonomous Business Intelligence agent that allows non-technical users to ask complex analytical questions in natural language and receive accurate T-SQL queries and Plotly visualizations.

```
                      USER QUESTION (Arabic / English)
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │    Schema Auto-Discovery  │
                      │  (`sql_assistant/schema`) │
                      └─────────────┬─────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │    Google Gemini LLM      │
                      │ (`sql_assistant/ai_serv`) │
                      └─────────────┬─────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │    4-Layer Security Engine│
                      │ (`sql_assistant/security`)│
                      └─────────────┬─────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │  SQL Server Execution     │
                      │  + Plotly Visualization   │
                      └───────────────────────────┘
```

### Key AI Agent Features
1. **Egyptian Arabic & English Natively:** Understands dialectal business questions (e.g., *"وريني أعلى 10 منتجات من حيث المبيعات"* or *"Which customers have the highest LTV?"*).
2. **Dynamic Schema Discovery (`schema.py`):** Automatically inspects database system tables (`INFORMATION_SCHEMA`) at startup, building an up-to-date schema prompt context with primary keys, foreign keys, and row counts.
3. **Multi-Model Fallback Chain (`ai_service.py`):** Prevents API quota failures by cycling through models automatically:
   `gemini-2.5-flash-lite` → `gemini-2.5-flash` → `gemini-3.1-flash-lite` → `gemini-2.0-flash`.
4. **4-Layer Security Engine (`security.py`):** Protects the database from malicious inputs or prompt injections:
   - **Layer 1 (Comment Stripping):** Removes `--` and `/* */` SQL comments to prevent keyword hiding.
   - **Layer 2 (Multi-Statement Blocker):** Rejects query strings containing semicolons `;`.
   - **Layer 3 (First Token Whitelist):** Enforces that queries must start strictly with `SELECT` or `WITH`.
   - **Layer 4 (Regex Keyword Blocklist):** Rejects forbidden words (`DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `EXEC`, `MERGE`, `GRANT`, `SHUTDOWN`).
5. **Developer Mode:** Provides a collapsible SQL editor where engineers can inspect, modify, validate, and explain generated queries.

---

## 🔄 13. End-to-End Pipeline Execution Runbook

To execute the entire data pipeline from raw ingestion to model training and application launch, execute the following sequence:

```bash
# -------------------------------------------------------------------------
# STEP 1: BRONZE INGESTION (Python)
# -------------------------------------------------------------------------
python ingestion/run_all_ingestion.py
# Output: Ingests ~1.28M rows into [BI_AI].[bronze] (~5 minutes)

# -------------------------------------------------------------------------
# STEP 2: SILVER TRANSFORMATION (T-SQL)
# -------------------------------------------------------------------------
# Execute via SSMS or sqlcmd:
sqlcmd -S localhost -d BI_AI -Q "EXEC silver.silver_master;"
# Output: Cleans, deduplicates, and populates [BI_AI].[silver] (~15 seconds)

# -------------------------------------------------------------------------
# STEP 3: GOLD DIMENSIONAL LOADING (T-SQL)
# -------------------------------------------------------------------------
# Execute via SSMS or sqlcmd:
sqlcmd -S localhost -d BI_AI -Q "EXEC gold.gold_master;"
# Output: Populates Kimball Galaxy Schema in [BI_AI].[gold] (~30 seconds)

# -------------------------------------------------------------------------
# STEP 4: OBT FEATURE STORE CREATION (Python)
# -------------------------------------------------------------------------
python scripts/ml/create_obt_master.py --execute
# Output: Generates gold.obt_customers, gold.obt_sellers, gold.obt_orders

# -------------------------------------------------------------------------
# STEP 5: MACHINE LEARNING PIPELINE (Python)
# -------------------------------------------------------------------------
python scripts/ml/run_all_ml.py --execute
# Output: Trains all 7 ML models and writes predictions back to OBTs (~100s)

# -------------------------------------------------------------------------
# STEP 6: CSV EXPORT FOR DEMO MODE (Python)
# -------------------------------------------------------------------------
python export_csv.py
# Output: Generates static CSV snapshot in streamlit/data/obt_master.csv

# -------------------------------------------------------------------------
# STEP 7: LAUNCH APPLICATIONS
# -------------------------------------------------------------------------
# Launch Streamlit Analytics Dashboard
streamlit run streamlit/app.py --server.port 8501

# Launch AI SQL Assistant (in a separate terminal)
streamlit run sql_assistant/app.py --server.port 8502
```

---

## 🧪 14. Data Quality Audits & Verification

An automated verification script (`scripts/silver/silver_quality_checks.sql`) performs over 50 integrity tests against the Silver and Gold schemas.

### Audit Test Suite
1. **Primary Key Uniqueness:** Verified 0 duplicate primary keys across all 9 Silver tables. `order_reviews` correctly purged 559 duplicate rows.
2. **Referential Integrity:** Tested 8 foreign key relationships. Verified 0 orphan rows between `fact_order_items`, `dim_customer`, `dim_product`, and `dim_seller`.
3. **Known Source Issue (Orphan Sellers):** Verified 462 closed deals in the marketing funnel where `seller_id` did not exist in e-commerce sellers. Handled gracefully by resolving foreign keys to the Gold layer unknown member (`seller_sk = -1`).
4. **Date Sentinel Integrity:** Confirmed zero unmapped `NULL` dates. All missing dates successfully resolved to `'1900-01-01'` or `'9999-12-31'`.

---

## 🧠 15. Key Design Decisions & Limitations

### Design Decisions
1. **Full Idempotency:** Every script and stored procedure utilizes `DROP/CREATE`, `TRUNCATE/INSERT`, or `MERGE` patterns, making the entire platform safe to re-run at any point.
2. **In-Place ML Output Writes:** Predictions are written directly back to the OBT feature stores, maintaining a unified interface for downstream dashboards.
3. **Text Outrigger Pattern:** Separated `review_comment_title` and `review_comment_message` into `gold.review_comments` to preserve SQL Server Clustered Columnstore Index (CCI) compression efficiency.

### System Limitations
1. **Historical Dataset Boundaries:** The Kaggle Olist dataset spans 2016 to 2018. The customer churn anchor date is hardcoded to `2018-10-17` to enable meaningful churn labelling.
2. **Marketing Funnel Coverage:** Only ~842 closed deals exist in the marketing dataset compared to 3,095 sellers in the e-commerce platform.
