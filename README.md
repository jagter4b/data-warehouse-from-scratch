<div align="center">

# 🏭 Olist Data Warehouse & ML Analytics

### Production-Grade End-to-End Data Engineering & Machine Learning Pipeline

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://python.org)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-2022-CC2927?logo=microsoftsqlserver&logoColor=white)](https://www.microsoft.com/sql-server)
[![T-SQL](https://img.shields.io/badge/T--SQL-Stored%20Procedures-blue)](https://docs.microsoft.com/en-us/sql/t-sql/)
[![Architecture](https://img.shields.io/badge/Architecture-Medallion-gold)](https://databricks.com/glossary/medallion-architecture)
[![Modeling](https://img.shields.io/badge/Modeling-Kimball%20Galaxy%20Schema-purple)](https://www.kimballgroup.com)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost-orange?logo=xgboost)](https://xgboost.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

🚀 **Live Dashboard:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

> A full-stack data platform built using the **Medallion Architecture** (Bronze → Silver → Gold → ML). It integrates two Olist datasets through an automated ELT pipeline into a Kimball-style **Galaxy Schema**, powering **7 predictive machine learning models** and a live **Streamlit dashboard**.

</div>

---

## 🎯 1. Project Overview

This project demonstrates a production-ready data platform built entirely from scratch. It handles the full data lifecycle: from heterogeneous ingestion to dimensional modeling, feature engineering, predictive ML, and interactive visualization.

**Key Achievements:**
- **Automated ELT:** Extracted ~1.28M rows from Neon PostgreSQL, Google Drive, and a custom REST API.
- **Robust Transformation:** 9 idempotent T-SQL stored procedures for cleaning, deduping, and standardization.
- **Dimensional Modeling:** Kimball Galaxy Schema with 7 dimensions, 5 fact tables, and 1 outrigger, completely enforcing foreign key constraints.
- **Feature Stores:** 3 "One Big Tables" (OBTs) denormalizing the Gold layer into ML-ready datasets.
- **Machine Learning:** 7 models (XGBoost, Random Forest, K-Means) covering segmentation, churn, LTV, performance scoring, delivery risk, and review prediction.
- **Data Apps:** Live multi-page Streamlit dashboard with a robust cloud-ready "Demo Mode".

---

## 🏗️ 2. Architecture Overview

The pipeline implements a strict **Medallion Architecture**, isolating raw ingestion, cleaning, business modeling, and ML inference.

<div align="center">
  <img src="./docs/DataFlowDiagram.excalidraw.png" alt="Data Flow Diagram" width="100%">
  <br>
  <em>End-to-end ELT data pipeline showing ingestion, transformation, and dimensional modeling.</em>
</div>

---

## 🛠️ 3. Tech Stack

- **Data Engineering:** Python, T-SQL, Microsoft SQL Server 2022, Neon PostgreSQL, Google Apps Script API.
- **Data Modeling:** Kimball Galaxy Schema, Medallion Architecture, SCD Type 1, Accumulating Snapshot.
- **Machine Learning:** XGBoost, Scikit-learn (Random Forest, K-Means), SMOTE (Imbalanced-learn).
- **Analytics & UI:** Streamlit, Plotly Express, Custom CSS Design System.

---

## 📦 4. Data Sources

The platform integrates two publicly available datasets from Olist (a Brazilian e-commerce marketplace):
1. **Brazilian E-Commerce Dataset:** ~100k orders from 2016–2018 spanning customers, products, payments, reviews, sellers, and geolocation.
2. **Marketing Funnel Dataset:** ~8k leads and closed deals showing seller acquisition.

*Note: The datasets are bridged via the `seller_id`, allowing a shared dimension in the Galaxy Schema for cross-domain analysis.*

---

## 🔄 5. Medallion Architecture & ELT

### 🥉 Bronze (Ingestion)
Python scripts extract data from PostgreSQL, Drive, and API. It is loaded raw into 11 tables (~1.28M rows) with `_ingested_at` audit columns. Process is idempotent (drop & recreate).

### 🥈 Silver (Transformation)
9 T-SQL stored procedures clean and standardize the data. Operations include deduplication (e.g., 559 duplicate reviews removed), string trimming, standardizing sentinels (`1900-01-01`), zero-padding ZIP codes, casting types, and English translations.

### 🥇 Gold (Dimensional Modeling)
Data is modeled into a **Kimball Galaxy Schema**:
- **7 Dimensions:** Date, Customer, Product, Seller (shared), Payment Type, Order Status, Marketing Channel.
- **5 Facts & 1 Outrigger:** Order Items, Payments, Reviews, Order Lifecycle (Accumulating Snapshot), Marketing Funnel.

### 📊 One Big Tables (Feature Stores)
The Gold schema is flattened into 3 ML-ready feature stores:
- **`obt_customers`** (96,097 rows): Spends, recency, frequency, satisfaction.
- **`obt_sellers`** (3,096 rows): Revenue, delivery performance, acquisition channel.
- **`obt_orders`** (99,441 rows): Delivery timing, payment details.

---

## 🤖 6. Machine Learning Pipeline

The project features 7 predictive models trained on the OBTs.

| Domain | Model | Algorithm | Output | Performance |
|:---|:---|:---|:---|:---|
| **Customer** | RFM Segmentation | K-Means (k=4) | 4 Behavioral Clusters | Silhouette: **0.4788** |
| **Customer** | Churn Prediction | Random Forest + SMOTE | High/Med/Low Risk | AUC-ROC: **0.6829** |
| **Customer** | Lifetime Value (LTV) | XGBoost Regressor | Platinum/Gold/Silver/Bronze | R²: **0.1710** * |
| **Seller** | Performance Scoring | Weighted + K-Means | Top/Avg/Underperformer | Silhouette: **0.5679** |
| **Seller** | Churn Risk | XGBoost + Dynamic SMOTE | Churn Probability | AUC-ROC: **0.7846** |
| **Order** | Delivery Risk | XGBoost + SMOTE | Delay Probability | AUC-ROC: **0.7483** |
| **Order** | Review Prediction | XGBoost Regressor | Predicted Score (1-5) | RMSE: **1.1311** |

> ***Data Leakage Note:** Initial LTV models showed R² = 0.9982 due to target leakage (e.g., `avg_order_value`). Removing direct derivations of total spend dropped the R² to 0.1710, yielding an honest, production-realistic model.*

All ML scripts output results via idempotent `TRUNCATE + INSERT` into the Gold schema.

---

## 📈 7. Streamlit Dashboard

🚀 **Live at:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

A premium, custom-styled Streamlit application visually exploring the ML outputs. It features:
- **Customer, Seller, and Order Intelligence pages** with interactive Plotly charts.
- **CSV Fallback (Demo Mode):** For cloud environments without direct DB access, the app automatically switches to reading from `streamlit/data/*.csv` snapshots.

---

## 🚀 8. How To Run This Project

### Prerequisites
- Python 3.9+ and Git
- Microsoft SQL Server 2022 (local instance `BI_AI`)
- ODBC Driver 17 for SQL Server

### Setup
```bash
git clone https://github.com/jagter4b/data-warehouse-from-scratch.git
cd data-warehouse-from-scratch
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
*Configure `.env` with source (Neon) and destination (SQL Server) credentials.*

### 1. Run ELT Pipeline
```bash
# Ingestion (Python)
python ingestion/run_all_ingestion.py

# Transformation (T-SQL in SSMS or sqlcmd)
EXEC silver.silver_master;

# Dimensional Load (T-SQL in SSMS)
EXEC gold.gold_master;
```

### 2. Run ML Pipeline
```bash
# Create feature stores
python scripts/ml/create_obt_customers.py --execute
python scripts/ml/create_obt_sellers.py --execute
python scripts/ml/create_obt_orders.py --execute

# Train models & score data
python scripts/ml/ml_customer_segments.py --execute
python scripts/ml/ml_churn_predictions.py --execute
python scripts/ml/ml_clv_predictions.py --execute
python scripts/ml/ml_seller_scores.py --execute
python scripts/ml/ml_seller_churn.py --execute
python scripts/ml/ml_delivery_risk.py --execute
python scripts/ml/ml_review_predictions.py --execute
```

### 3. Launch Dashboard
```bash
python export_csv.py             # Re-export data snapshots for Streamlit Demo Mode
cd streamlit
pip install -r requirements.txt  # Streamlit-specific deps
streamlit run app.py
```

---

## 🧠 9. Key Design Decisions & Limitations

- **Idempotency:** Every script and SP is designed to be fully re-runnable (Drop/Create, Truncate/Insert, Merge).
- **Demo Mode:** Avoids requiring VPNs or cloud DB hosting for the Streamlit app by falling back to static CSV exports.
- **Limitation — Data Freshness:** The Kaggle dataset covers 2016-2018. The churn anchor date was hardcoded to the maximum dataset timestamp to maintain realistic labels.
- **Limitation — Orphan Sellers:** The marketing funnel data includes 462 sellers not found in the e-commerce dataset, which were handled via unknown member records (`-1`).

---

## 📚 10. Documentation

Each pipeline layer contains an in-depth README covering logic and schemas:
- 🥉 [Bronze Documentation](ingestion/README.md)
- 🥈 [Silver Documentation](scripts/silver/README.md)
- 🥇 [Gold Documentation](scripts/gold/README.md)
- 🤖 [ML Documentation](scripts/ml/README.md)
- 📈 [Streamlit Documentation](streamlit/README.md)

<div align="center">
<br>
Built with ❤️ using Python, SQL Server, XGBoost, and Streamlit
</div>
