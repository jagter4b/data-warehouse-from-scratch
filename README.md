# Olist Data Warehouse: From Scratch (Medallion Architecture)

🚀 **Goal**: This project builds a production-grade Data Warehouse solution following the **Medallion Architecture** (Bronze, Silver, Gold). The objective is to integrate disparate data sources—including Google Sheets, External APIs, and PostgreSQL databases—into a centralized **Single Point of Truth** in a local SQL Server instance using an **ELT (Extract, Load, Transform)** approach.

The datasets used are the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and the [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist).

> [!NOTE]
> This project is under active development. Current focus: **Gold Layer Modeling**.

---

## 🏗️ Architecture: The Medallion Approach

1.  **Bronze (Raw)**: Data is ingested directly from source systems as-is. Minimal processing (only adding audit columns) to ensure full data lineage.
2.  **Silver (Cleaned/Standardized)**: Data is cleaned, deduplicated, and typed. Brazilian locale support is maintained via `NVARCHAR`. Relationships and context-aware sentinels (e.g., in-transit dates) are established.
3.  **Gold (Analytical)**: *[Planned]* Star-schema dimensional modeling (Kimball style) optimized for Power BI and analytical reporting (Galaxy Schema).

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
Open SQL Server Management Studio (SSMS) and execute the master stored procedure:
```sql
USE [BI_AI];
EXEC silver.silver_master;
```

---

## 🧰 Tech Stack
*   **Language**: Python (pandas, SQLAlchemy, pyodbc), T-SQL
*   **Database**: SQL Server 2022 (Destination), PostgreSQL (Source)
*   **Cloud Tools**: Google Drive API, Google Apps Script
*   **Orchestration**: Custom Python Master Runner, SQL Stored Procedures

---

## 📁 Repository Structure
```
├── ingestion/                 # Python scripts for Bronze layer extraction
│   ├── run_all_ingestion.py   # Master ingestion runner
│   └── ...                    # Individual source extractors
├── scripts/
│   ├── silver/                # Silver layer SQL stored procedures
│   │   ├── load_*.sql         # Individual table transformations
│   │   ├── silver_master.sql  # Silver orchestration SP
│   │   ├── silver_quality_checks.sql # Silver data validation script
│   │   └── README.md          # Detailed Silver layer documentation
│   └── bronze_quality_checks.sql # Bronze data profiling script
├── metadata/                  # Project metadata and screenshots
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 📈 Roadmap
- [x] **Bronze Layer**: Ingestion (Idempotent ELT via Python)
- [x] **Bronze Layer**: Data Quality Profiling
- [x] **Silver Layer**: Data Cleaning, Type Casting & Deduplication (T-SQL SPs)
- [x] **Silver Layer**: Data Quality Checks & Referential Integrity Audits
- [ ] **Gold Layer**: Dimensional Modeling (Star / Galaxy Schema)
- [ ] **Gold Layer**: Slowly Changing Dimensions (SCD Type 1/2) & Columnstore Indexes
- [ ] **Reporting Layer**: Power BI Dashboards
