# Olist Data Warehouse: From Scratch (Medallion Architecture)

🚀 **Goal**: This project builds a production-grade Data Warehouse solution following the **Medallion Architecture** (Bronze, Silver, Gold). The objective is to integrate disparate data sources—including Google Sheets, External APIs, and PostgreSQL databases—into a centralized **Single Point of Truth** in a local SQL Server instance using an **ELT (Extract, Load, Transform)** approach.

The datasets used are the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and the [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist).

> [!NOTE]
> This project has successfully completed the Data Engineering phase (Medallion Architecture). Current focus: **Reporting & Dashboarding in Power BI**.

---

## 🏗️ Architecture: The Medallion Approach

1.  **Bronze (Raw)**: Data is ingested directly from source systems as-is. Minimal processing (only adding audit columns) to ensure full data lineage.
2.  **Silver (Cleaned/Standardized)**: Data is cleaned, deduplicated, and typed. Brazilian locale support is maintained via `NVARCHAR`. Relationships and context-aware sentinels (e.g., in-transit dates) are established.
3.  **Gold (Analytical)**: Star-schema dimensional modeling (Kimball style) optimized for Power BI and analytical reporting (Galaxy Schema). Enforces referential integrity with facts and dimensions.

---

## 📥 Bronze Layer: Data Ingestion

The Bronze layer is fully automated and handles the extraction and loading of over **1.2 million rows** from three distinct sources.

### Source Systems
| Source Type | Source Platform | Datasets |
| :--- | :--- | :--- |
| **Relational DB** | Neon PostgreSQL | 7 Olist E-commerce tables (Orders, Customers, Items, Payments, Reviews, Sellers, Products) |
| **Cloud Storage** | Google Drive / Sheets | 2 Marketing tables (Leads, Closed Deals) & Category Translation |
| **Custom API** | Google Apps Script | High-volume Geolocation CSV data (~850K rows) |

### Key Features
*   **Pure ELT**: No transformations occur during ingestion; data lands raw in the `bronze` schema.
*   **Idempotency**: All Python scripts use a "Drop & Recreate" logic, making them safe to re-run anytime.
*   **Auditability**: Every row is tagged with `_ingested_at`, `_source`, and source-specific metadata.
*   **Performance Optimized**: Handles SQL Server's 2100-parameter limit via dynamic batching (`safe_chunk` logic).
*   **Quality Checks**: A comprehensive `bronze_quality_checks.sql` script is used to profile missing values, duplicates, and referential integrity before moving to Silver.

---

## 🛠️ Silver Layer: Data Transformation

The Silver layer transforms the raw bronze data into refined, production-ready tables using idempotent stored procedures.

### Key Features
*   **Deduplication**: `ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _ingested_at DESC)` ensures only the most recent ingestion record is kept.
*   **Data Cleansing**: Whitespace trimming (`LTRIM/RTRIM`), zero-padding for zip codes, and case standardization (Title Case, UPPER/LOWER).
*   **Context-Aware Sentinels**: 
    *   NULL dates replaced with `'1900-01-01'` for missing/canceled data.
    *   In-transit delivery dates replaced with `'9999-12-31'`.
    *   Missing foreign keys mapped to `'UNKNOWN'`.
*   **Categorical Mapping**: Snake_case values (e.g., `credit_card`) mapped to human-readable labels (`Credit Card`).
*   **Orchestration**: A master stored procedure (`silver.silver_master`) triggers 9 load procedures in the correct dependency sequence with integrated `TRY/CATCH` error handling.
*   **Quality Assurance**: A dedicated `silver_quality_checks.sql` script validates row counts, checks for unexpected NULLs, verifies data type casting, and ensures cross-table referential integrity within the Silver schema.

*(Note: The `geolocation` table is intentionally excluded from the Silver layer as it will not be part of the final Galaxy Schema.)*

---

## 🌟 Gold Layer: Dimensional Modeling

The Gold layer represents the final presentation layer, structured as a Kimball Galaxy Schema. It connects e-commerce operations with marketing acquisition metrics, forming a comprehensive analytical model.

### Key Features
*   **Dimensions (SCD Type 1)**: `dim_customer`, `dim_product`, `dim_seller`, and `dim_marketing_channel` load via `MERGE` statements.
*   **Conformed Date Spine**: `dim_date` handles a robust range (2016-2020) ensuring unified time-series analysis across all facts.
*   **Fact Tables**: Five granular fact tables loaded idempotently via `TRUNCATE + INSERT`:
    *   `fact_order_items` (Order Item grain)
    *   `fact_payments` (Payment method grain)
    *   `fact_reviews` (Review grain)
    *   `fact_order_life_cycle` (Accumulating Snapshot for delivery tracking)
    *   `fact_marketing_funnel` (MQL Conversion grain)
*   **Outrigger Strategy**: `review_comments` is implemented as an outrigger to `fact_reviews` to efficiently store long-form text without bloating the primary fact table.
*   **Orchestration**: `gold.gold_master` handles the end-to-end load sequence, processing dimensions before facts and managing complex Foreign Key constraint validations during full-reloads.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.9+
*   SQL Server (Local instance with `BI_AI` database)
*   `.env` file with necessary credentials (see `.env.example` if available)

### Installation
```bash
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Pipeline

**1. Bronze Ingestion:**
```bash
python ingestion/run_all_ingestion.py
```

**2. Silver Transformation:**
Open SQL Server Management Studio (SSMS) or use `sqlcmd` to execute the master stored procedure:
```sql
USE [BI_AI];
EXEC silver.silver_master;
```

**3. Gold Dimensional Load:**
Load the Galaxy Schema and fact tables:
```sql
USE [BI_AI];
EXEC gold.gold_master;
```

---

## 🧰 Tech Stack
*   **Language**: Python (pandas, SQLAlchemy, pyodbc), T-SQL
*   **Database**: SQL Server 2022 (Destination), PostgreSQL (Source)
*   **Cloud Tools**: Google Drive API, Google Apps Script
*   **Architecture**: Kimball Dimensional Modeling, Medallion Architecture

---

## 📁 Repository Structure
```
├── ingestion/                 # Python scripts for Bronze layer extraction
├── scripts/
│   ├── bronze/                # Bronze schema DDL and quality checks
│   ├── silver/                # Silver layer T-SQL stored procedures
│   └── gold/                  # Gold layer Kimball modeling, DDL, and ETL SPs
├── metadata/                  # Project metadata, DBML schemas, and diagrams
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 📈 Roadmap
- [x] **Bronze Layer**: Ingestion (Idempotent ELT via Python)
- [x] **Bronze Layer**: Data Quality Profiling
- [x] **Silver Layer**: Data Cleaning, Type Casting & Deduplication (T-SQL SPs)
- [x] **Silver Layer**: Data Quality Checks & Referential Integrity Audits
- [x] **Gold Layer**: Dimensional Modeling (Star / Galaxy Schema)
- [x] **Gold Layer**: Medallion Master Orchestration & FK Management
- [ ] **Reporting Layer**: Power BI Dashboards
