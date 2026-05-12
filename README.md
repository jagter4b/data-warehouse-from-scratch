# Olist Data Warehouse: From Scratch (Medallion Architecture)

🚀 **Goal**: This project builds a production-grade Data Warehouse solution following the **Medallion Architecture** (Bronze, Silver, Gold). The objective is to integrate disparate data sources—including Google Sheets, External APIs, and PostgreSQL databases—into a centralized **Single Point of Truth** in a local SQL Server instance using an **ELT (Extract, Load, Transform)** approach.

> [!NOTE]
> This project is under active development. Current focus: **Gold Layer Modeling**.

---

## 🏗️ Architecture: The Medallion Approach

1.  **Bronze (Raw)**: Data is ingested directly from source systems as-is. Minimal processing (only adding audit columns) to ensure full data lineage.
2.  **Silver (Cleaned/Standardized)**: Data is cleaned, deduplicated, and typed. Brazilian locale support is maintained via `NVARCHAR`. Relationships and context-aware sentinels (e.g., in-transit dates) are established.
3.  **Gold (Analytical)**: *[Planned]* Star-schema dimensional modeling (Kimball style) optimized for Power BI and analytical reporting.

---

## 📥 Bronze Layer: Data Ingestion

The Bronze layer is fully automated and handles the extraction and loading of over **1.2 million rows** from three distinct sources:

### 1. Source Systems
| Source Type | Source Platform | Datasets |
| :--- | :--- | :--- |
| **Relational DB** | Neon PostgreSQL | 7 Olist E-commerce tables (Orders, Customers, etc.) |
| **Cloud Storage** | Google Drive / Sheets | Marketing Leads, Closed Deals, Order Reviews |
| **Custom API** | Google Apps Script | High-volume Geolocation CSV data (~850K rows) |

### 2. Key Features
*   **Pure ELT**: No transformations occur during ingestion; data lands raw in the `bronze` schema.
*   **Idempotency**: All scripts use a "Drop & Recreate" logic, making them safe to re-run anytime.
*   **Auditability**: Every row is tagged with `_ingested_at`, `_source`, and source-specific metadata.
*   **Performance Optimized**: Handles SQL Server's 2100-parameter limit via dynamic batching (`safe_chunk` logic).

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

### Running Ingestion
To ingest all data sources into the Bronze layer:
```bash
python ingestion/run_all_ingestion.py
```

---

## 🛠️ Tech Stack
*   **Language**: Python (pandas, SQLAlchemy, pyodbc)
*   **Database**: SQL Server (Destination), PostgreSQL (Source)
*   **Cloud Tools**: Google Drive API, Google Apps Script
*   **Orchestration**: Custom Python Master Runner

---

## 📈 Roadmap
- [x] Bronze Layer Ingestion (Idempotent ELT)
- [x] Silver Layer: Data Cleaning & Type Casting
- [x] Silver Layer: Data Quality Checks (Audit Scripts)
- [ ] Gold Layer: Dimensional Modeling (Star Schema)
- [ ] Power BI Reporting Layer
