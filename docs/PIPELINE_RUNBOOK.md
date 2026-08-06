# 🔄 Pipeline Runbook

> **This document describes how to run the complete end-to-end ELT + ML pipeline from scratch.**  
> All scripts are designed to be fully idempotent — safe to re-run at any time.

---

## Quick Reference — Full Pipeline

```bash
# ── PHASE 1: Ingestion (Bronze) ────────────────────────────────────
python ingestion/run_all_ingestion.py

# ── PHASE 2: Transformation (Silver) — run in SSMS or sqlcmd ───────
EXEC silver.silver_master;

# ── PHASE 3: Dimensional Load (Gold) — run in SSMS or sqlcmd ────────
EXEC gold.gold_master;

# ── PHASE 4: Feature Store ──────────────────────────────────────────
python scripts/ml/create_obt_master.py --execute

# ── PHASE 5: ML Training & Scoring ─────────────────────────────────
python scripts/ml/run_all_ml.py --execute

# ── PHASE 6: Export CSV snapshots ───────────────────────────────────
python export_csv.py

# ── PHASE 7: Launch Applications ────────────────────────────────────
streamlit run streamlit/app.py            # Dashboard (port 8501)
streamlit run sql_assistant/app.py        # AI Assistant (port 8502)
```

---

## Phase 1: 🥉 Bronze Layer Ingestion

**Script:** `ingestion/run_all_ingestion.py`  
**Duration:** ~306 seconds (5 minutes)  
**Output:** 11 tables in `[BI_AI].[bronze]`

### What it does

1. Connects to **Neon PostgreSQL** and extracts 7 tables (~448K rows)
2. Fetches **Google Drive** files (order_reviews from Google Sheets, MQLs from CSV, closed_deals from CSV)
3. Calls the **Geolocation REST API** (Google Apps Script) and loads 855,781 geolocation rows

### Running individual sources

```bash
# Neon PostgreSQL only
python ingestion/ingest_neon_postgres.py

# Google Drive files only
python ingestion/ingest_google_drive.py

# Geolocation API only
python ingestion/ingest_geolocation_api.py

# All sources (recommended)
python ingestion/run_all_ingestion.py
```

### Expected output

```
Pipeline Summary
  ✅ Neon PostgreSQL   SUCCESS  159.2s  7 tables, ~448K rows
  ✅ Google Drive      SUCCESS   93.3s  3 files, ~109K rows
  ✅ Geolocation API   SUCCESS   53.5s  855,781 rows (52MB)
  Total: ~1.28M rows ingested in 306s
```

### Idempotency note
Each table is dropped and recreated on every run. All previously loaded data is replaced.

---

## Phase 2: 🥈 Silver Layer Transformation

**Command:** `EXEC silver.silver_master;` (in SSMS or sqlcmd)  
**Duration:** ~15 seconds  
**Output:** 9 tables in `[BI_AI].[silver]`

### Running in SSMS

```sql
USE [BI_AI];
EXEC silver.silver_master;
```

### Running via sqlcmd

```bash
sqlcmd -S YOUR_SERVER -d BI_AI -Q "EXEC silver.silver_master"
```

### What each stored procedure does

| # | SP Name | Source → Target | Key Operations |
|---|---------|----------------|----------------|
| 1 | `silver.load_customers` | bronze.customers → silver.customers | Trim, uppercase city/state, zero-pad ZIP, dedup |
| 2 | `silver.load_sellers` | bronze.sellers → silver.sellers | Same as customers |
| 3 | `silver.load_products` | bronze.products → silver.products | Translation JOIN, Title Case categories, fix typos |
| 4 | `silver.load_orders` | bronze.orders → silver.orders | TRY_CAST dates, context-aware sentinels |
| 5 | `silver.load_order_items` | bronze.order_items → silver.order_items | Rename columns, DECIMAL precision |
| 6 | `silver.load_order_payments` | bronze.order_payments → silver.order_payments | Payment type mapping |
| 7 | `silver.load_order_reviews` | bronze.order_reviews → silver.order_reviews | Deduplicate by order_id (removes 559 dupes) |
| 8 | `silver.load_marketing_qualified_leads` | bronze.marketing_qualified_leads → silver.marketing_qualified_leads | Origin labels |
| 9 | `silver.load_closed_deals` | bronze.closed_deals → silver.closed_deals | Multiple label cleanups |

### Verifying Silver results

```sql
SELECT 'customers' AS tbl, COUNT(*) AS rows FROM silver.customers
UNION ALL SELECT 'sellers',                   COUNT(*) FROM silver.sellers
UNION ALL SELECT 'products',                  COUNT(*) FROM silver.products
UNION ALL SELECT 'orders',                    COUNT(*) FROM silver.orders
UNION ALL SELECT 'order_items',               COUNT(*) FROM silver.order_items
UNION ALL SELECT 'order_payments',            COUNT(*) FROM silver.order_payments
UNION ALL SELECT 'order_reviews',             COUNT(*) FROM silver.order_reviews
UNION ALL SELECT 'marketing_qualified_leads', COUNT(*) FROM silver.marketing_qualified_leads
UNION ALL SELECT 'closed_deals',              COUNT(*) FROM silver.closed_deals;
```

---

## Phase 3: 🥇 Gold Layer Dimensional Load

**Command:** `EXEC gold.gold_master;` (in SSMS)  
**Output:** 7 dimensions + 5 facts + 1 outrigger in `[BI_AI].[gold]`

### Running in SSMS

```sql
USE [BI_AI];
EXEC gold.gold_master;
```

### Execution order within gold_master

```
1. load_dim_customer      (MERGE — SCD Type 1)
2. load_dim_product       (MERGE — SCD Type 1)
3. load_dim_seller        (MERGE — SCD Type 1)
4. load_dim_marketing_channel  (MERGE — SCD Type 1)
5. load_fact_order_items  (TRUNCATE + INSERT)
6. load_fact_payments     (TRUNCATE + INSERT)
7. load_fact_reviews      (TRUNCATE + INSERT + outrigger)
8. load_fact_order_life_cycle (TRUNCATE + INSERT)
9. load_fact_marketing_funnel (TRUNCATE + INSERT)
```

> ⚠️ Any failure raises a `THROW` and halts execution immediately.

---

## Phase 4: 📊 Feature Store Creation

**Script:** `scripts/ml/create_obt_master.py`  
**Duration:** ~30 seconds  
**Output:** `gold.obt_master` (99,441 rows, 47 columns)

```bash
# Dry run (shows what would be created, doesn't write)
python scripts/ml/create_obt_master.py

# Execute (writes to database)
python scripts/ml/create_obt_master.py --execute
```

The OBT joins all Gold layer facts and dimensions into a single flat table suitable for ML training. Grain: one row per order.

---

## Phase 5: 🤖 ML Training & Scoring

**Script:** `scripts/ml/run_all_ml.py`  
**Duration:** ~100 seconds total  
**Output:** ML prediction columns added to `gold.obt_master`

```bash
# Dry run (trains models but doesn't write back)
python scripts/ml/run_all_ml.py

# Execute (trains + writes predictions to DB)
python scripts/ml/run_all_ml.py --execute
```

### Running models individually

```bash
python scripts/ml/ml_customer_segments.py --execute   # K-Means RFM
python scripts/ml/ml_churn_prediction.py --execute    # Random Forest Churn
python scripts/ml/ml_delivery_risk.py --execute       # XGBoost Delivery Risk
python scripts/ml/ml_review_prediction.py --execute   # XGBoost Review Score
python scripts/ml/ml_seller_performance.py --execute  # Seller KPI Scoring
```

### Expected pipeline summary

```
======================================================================
  Pipeline Summary
======================================================================
  ✅ OK   K-Means RFM Segmentation        (39.6s)
  ✅ OK   Random Forest Churn             (34.4s)
  ✅ OK   XGBoost Delivery Risk           (12.4s)
  ✅ OK   XGBoost Review Prediction       ( 8.1s)
  ✅ OK   Seller Performance Scoring      ( 3.3s)
  Total runtime: ~100s
======================================================================
```

---

## Phase 6: 📁 CSV Export (Streamlit Demo Mode)

**Script:** `export_csv.py`  
**Output:** `streamlit/data/obt_master.csv`

```bash
python export_csv.py
```

This exports the `gold.obt_master` table to a CSV snapshot so the Streamlit dashboard works without a live SQL Server connection (Demo Mode on Streamlit Cloud).

> ⚠️ CSV files are gitignored by default. To deploy to Streamlit Cloud, temporarily remove `*.csv` from `.gitignore`, commit the snapshot, then restore the rule.

---

## Phase 7: 🚀 Launching Applications

### Streamlit Dashboard

```bash
# Install Streamlit-specific dependencies (first time)
pip install -r streamlit/requirements.txt

# Run from project root
streamlit run streamlit/app.py
```

Opens at: `http://localhost:8501`

### SQL Assistant (AI BI Agent)

```bash
# Install SQL Assistant dependencies (first time)
pip install -r sql_assistant/requirements.txt

# Run (use a different port to run alongside the dashboard)
streamlit run sql_assistant/app.py --server.port 8502
```

Opens at: `http://localhost:8502`

---

## Incremental Refresh (Ongoing)

After initial setup, a full refresh requires only:

```bash
# 1. Re-ingest (if source data has changed)
python ingestion/run_all_ingestion.py

# 2. Re-transform
# In SSMS: EXEC silver.silver_master;
# In SSMS: EXEC gold.gold_master;

# 3. Re-score ML
python scripts/ml/create_obt_master.py --execute
python scripts/ml/run_all_ml.py --execute

# 4. Re-export CSV snapshot
python export_csv.py
```

---

## Data Validation

Run the Silver quality checks script to validate the transformation results:

```sql
-- In SSMS
-- File: scripts/silver/silver_quality_checks.sql
```

This runs ~50 automated checks covering:
- Row counts and deduplication
- NULL handling correctness
- Date sentinel values
- Foreign key referential integrity
- Formatting (ZIP padding, Title Case, etc.)

Results are printed as a formatted report. A full passing run confirms the Silver layer is clean and ready for Gold loading.
