# 🏗️ Architecture Documentation

## Overview

This project implements a **production-grade Medallion Architecture** (Bronze → Silver → Gold → ML) on top of two Olist e-commerce datasets. The platform covers the full data lifecycle: multi-source ingestion, transformation, dimensional modeling, machine learning, and interactive visualization.

---

## High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │  Neon PostgreSQL │  │  Google Drive    │  │  Geolocation REST  │  │
│  │  (7 tables,      │  │  (2 Google Sheets│  │  API (Google Apps  │  │
│  │   ~448K rows)    │  │   + 1 CSV file)  │  │  Script, 856K rows)│  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬─────────┘  │
└───────────┼──────────────────────┼───────────────────────┼────────────┘
            │  Python (ingestion/) │                        │
            ▼                      ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     🥉 BRONZE LAYER                                  │
│                   SQL Server [BI_AI].[bronze]                        │
│                                                                      │
│  11 raw tables • ~1.28M rows • _ingested_at audit column             │
│  Idempotent: DROP + CREATE on each run                               │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  T-SQL Stored Procedures
                               │  EXEC silver.silver_master
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     🥈 SILVER LAYER                                  │
│                   SQL Server [BI_AI].[silver]                        │
│                                                                      │
│  9 clean tables • Deduplication • Type casting • NULL sentinels      │
│  snake_case → Title Case • Zero-padded ZIP codes • English labels    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  T-SQL Stored Procedures
                               │  EXEC gold.gold_master
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     🥇 GOLD LAYER                                    │
│                   SQL Server [BI_AI].[gold]                          │
│                                                                      │
│  Kimball Galaxy Schema:                                              │
│  • 7 Dimensions (incl. shared dim_seller, conformed dim_date)        │
│  • 5 Fact Tables (incl. Accumulating Snapshot)                       │
│  • 1 Outrigger (review_comments)                                     │
│  • 3 OBTs (obt_customers, obt_sellers, obt_orders)                  │
└──────────┬───────────────────────────────────────────────────────────┘
           │                           │
           │  Python ML scripts        │  Streamlit + SQL Assistant
           ▼                           ▼
┌──────────────────────┐   ┌──────────────────────────────────────────┐
│  🤖 ML PIPELINE      │   │  📊 PRESENTATION LAYER                   │
│                      │   │                                          │
│  K-Means (RFM)       │   │  Streamlit Dashboard (4 pages)           │
│  Random Forest Churn │   │  SQL Assistant (AI BI Agent)             │
│  XGBoost LTV         │   │  Power BI Reports                        │
│  XGBoost Delivery    │   │  Live at: streamlit.app                  │
│  XGBoost Reviews     │   │                                          │
│  Seller Scoring      │   │                                          │
│  Seller Churn        │   │                                          │
└──────────────────────┘   └──────────────────────────────────────────┘
```

---

## Medallion Layer Details

### 🥉 Bronze Layer — Raw Ingestion

| Principle | Implementation |
|-----------|---------------|
| **No transformations** | Data lands exactly as received from sources |
| **Idempotency** | Each run drops and recreates the target table |
| **Audit trail** | Every row stamped with `_ingested_at`, `_source` |
| **Chunked loading** | Dynamic `safe_chunk = floor(2000 / num_cols)` for SQL Server 2100-param limit |
| **Schema enforcement** | Pandas infers types; pyodbc handles SQL Server bulk insert |

**Sources & tables loaded:**

| Source | Tables | Rows |
|--------|--------|------|
| Neon PostgreSQL | customers, orders, order_items, order_payments, sellers, products, product_category_name_translation | ~448K |
| Google Drive | order_reviews, marketing_qualified_leads, closed_deals | ~109K |
| Geolocation API | geolocation | 855,781 |
| **Total** | **11 tables** | **~1.28M rows** |

---

### 🥈 Silver Layer — Transformation

| Principle | Implementation |
|-----------|---------------|
| **Strategy** | DROP + SELECT INTO (full-load, idempotent) |
| **Deduplication** | `ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _ingested_at DESC)` |
| **NULL handling** | Dates → `'1900-01-01'`; FK strings → `'UNKNOWN'`; free text → sentinel; numerics → `0` |
| **Sentinel dates** | `'1900-01-01'` = missing/canceled; `'9999-12-31'` = in-transit/future |
| **Type safety** | `TRY_CAST` for dates; `DECIMAL(10,2)` for financials; `TINYINT` for booleans |
| **Locale preservation** | All strings stay `NVARCHAR` (preserves ã, ç, é from Brazilian Portuguese) |

**9 SPs executed by `silver.silver_master`** in this order:
`load_customers` → `load_sellers` → `load_products` → `load_orders` → `load_order_items` → `load_order_payments` → `load_order_reviews` → `load_marketing_qualified_leads` → `load_closed_deals`

---

### 🥇 Gold Layer — Kimball Galaxy Schema

**Pattern:** Galaxy Schema with two subject areas sharing `dim_seller` and `dim_date`.

```
E-Commerce Subject Area:           Marketing Subject Area:
  dim_customer ◄──┐                  dim_marketing_channel ◄──┐
  dim_product  ◄──┤                                           │
  dim_seller   ◄──┼── fact_order_items    fact_marketing_funnel ──► dim_seller (shared)
  dim_date     ◄──┤── fact_payments
  dim_payment_type ─── fact_reviews
  dim_order_status ─── fact_order_life_cycle (Accumulating Snapshot)
```

**ETL Load Strategies:**

| Object | Strategy | Why |
|--------|----------|-----|
| Dimensions (customer, product, seller, channel) | MERGE (SCD Type 1 upsert) | Handles inserts + updates idempotently |
| Static lookups (payment_type, order_status) | INSERT WHERE NOT EXISTS (seeded in DDL) | Static reference data |
| dim_date | Recursive CTE, INSERT WHERE NOT EXISTS | One-time generation, safe to re-run |
| All fact tables | TRUNCATE + INSERT | Simple, fast, idempotent |

---

### 📊 One Big Tables (OBTs) — Feature Stores

Three ML-ready denormalized tables are built from the Gold schema by `scripts/ml/create_obt_master.py`:

| OBT | Grain | Rows | Key Features |
|-----|-------|------|-------------|
| `gold.obt_customers` | 1 row per unique customer | 96,097 | RFM metrics, churn labels, LTV |
| `gold.obt_sellers` | 1 row per seller | 3,096 | Revenue, on-time rate, acquisition channel |
| `gold.obt_orders` | 1 row per order | 99,441 | Delivery timing, payment details, ML predictions |

---

### 🤖 ML Pipeline

All ML models read from OBTs and write predictions back via idempotent `TRUNCATE + INSERT`.

```
OBT (feature store)
       │
       ├──► K-Means RFM Segmentation      → customer_segment
       ├──► Random Forest Churn           → churn_probability, churn_risk_tier
       ├──► XGBoost LTV Regression        → ltv_segment
       ├──► Weighted KPI + K-Means        → seller_performance_score, seller_tier
       ├──► XGBoost Seller Churn          → seller_churn_probability
       ├──► XGBoost Delivery Risk         → delay_risk_score, delay_risk_tier
       └──► XGBoost Review Prediction     → predicted_review_score
```

---

## Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| Data Engineering | Python 3.9+, T-SQL, SQL Server 2022, Neon PostgreSQL, Google Apps Script |
| Ingestion | pyodbc, SQLAlchemy, psycopg2, pandas, requests |
| Transformation | T-SQL Stored Procedures, SQL Server 2022 (STRING_SPLIT ordinal) |
| Modeling | Kimball Galaxy Schema, Medallion Architecture, SCD Type 1, Accumulating Snapshot |
| ML | XGBoost, Scikit-learn (RandomForest, KMeans), imbalanced-learn (SMOTE) |
| Visualization | Streamlit, Plotly Express, Custom CSS Design System |
| AI | Google Gemini API (google-genai SDK), Model fallback chain |

---

## Key Design Principles

1. **Idempotency** — Every script and stored procedure can be re-run at any time with no side effects.
2. **ELT not ETL** — Transformation happens inside the target database (SQL Server), not in Python.
3. **Separation of concerns** — Each layer has a distinct responsibility; layers only read from the layer below them.
4. **Defense in depth** — The SQL Assistant uses 4 independent security layers before any query touches the database.
5. **Demo Mode** — The Streamlit app works in cloud environments (no SQL Server needed) via CSV fallback.
6. **Unknown members** — Every dimension has a `SK = -1` unknown member to handle orphan foreign keys gracefully.
