# ⚙️ Setup & Installation Guide

## Prerequisites

Before you begin, ensure you have the following installed:

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.9+ | [python.org](https://www.python.org/downloads/) |
| Git | Any | [git-scm.com](https://git-scm.com/) |
| Microsoft SQL Server | 2022 | Local instance named `BI_AI` |
| ODBC Driver 17 for SQL Server | 17+ | [Microsoft Download](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| SQL Server Management Studio (SSMS) | Any | For running T-SQL scripts |

> **Note:** SQL Server 2022 is required for the Silver layer's `STRING_SPLIT(..., 1)` ordinal syntax used for Title Case conversion. Earlier versions will fail.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/jagter4b/data-warehouse-from-scratch.git
cd data-warehouse-from-scratch
```

---

## Step 2: Create a Virtual Environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

---

## Step 3: Install Root Dependencies

```bash
pip install -r requirements.txt
```

This installs the core ingestion dependencies:
- `pandas` — data manipulation
- `pyodbc` — SQL Server ODBC driver
- `sqlalchemy` — database engine
- `python-dotenv` — environment variable loading
- `requests` — HTTP calls for the geolocation API
- `openpyxl` — Excel export support
- `psycopg2-binary` — Neon PostgreSQL driver

---

## Step 4: Configure Environment Variables

Copy the example file and fill in your credentials:

```bash
copy .env.example .env   # Windows
cp .env.example .env      # macOS / Linux
```

Edit `.env` with your actual values:

```env
# ── Source Database (Neon PostgreSQL) ────────────────────────────
SOURCE_DB_HOST=your-neon-host.neon.tech
SOURCE_DB_PORT=5432
SOURCE_DB_NAME=neondb
SOURCE_DB_USER=your_user
SOURCE_DB_PASSWORD=your_password
SOURCE_DB_SSL_MODE=require

# ── Destination Database (Local SQL Server) ───────────────────────
DEST_DB_HOST=DESKTOP-XXXXXXX    # Your machine hostname (or 'localhost')
DEST_DB_PORT=1433
DEST_DB_NAME=BI_AI
DEST_DB_TRUSTED_CONNECTION=yes  # Use 'no' for SQL Auth

# Optional: SQL Server Auth (only if TRUSTED_CONNECTION=no)
# DEST_DB_USER=sa
# DEST_DB_PASSWORD=your_password

# ── AI Services ───────────────────────────────────────────────────
Gemini_API_Key=your_gemini_api_key_here
```

### Finding your SQL Server hostname

Open SSMS → look at the **Server name** field in the connect dialog.  
Alternatively, run this in PowerShell:
```powershell
$env:COMPUTERNAME
```

---

## Step 5: Prepare the SQL Server Database

Open SSMS and create the `BI_AI` database with the required schemas:

```sql
-- Create database
CREATE DATABASE [BI_AI];
GO

-- Create schemas
USE [BI_AI];
GO
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
GO
```

> The Python ingestion scripts will create the `bronze` schema automatically if it doesn't exist, but it's good practice to create all schemas upfront.

---

## Step 6: Initialize the Gold Layer DDL (One-time setup)

In SSMS, execute these scripts **in order**:

```sql
-- 1. Create all dimension tables and seed static lookups
-- File: scripts/gold/gold_ddl_dimensions.sql

-- 2. Populate the date spine (2016–2020 + sentinel rows)
-- File: scripts/gold/gold_generate_dim_date.sql

-- 3. Create all fact tables and foreign key constraints
-- File: scripts/gold/gold_ddl_facts.sql
```

Then register all stored procedures by executing each `silver/` and `gold/` SQL file once.

---

## Step 7: Initialize Silver Layer SPs

Execute all files in `scripts/silver/` to register stored procedures:

```bash
# In SSMS: open and execute each file, OR use sqlcmd:
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_customers.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_sellers.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_products.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_orders.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_order_items.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_order_payments.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_order_reviews.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_marketing_qualified_leads.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/load_closed_deals.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/silver/silver_master.sql
```

---

## Step 8: Register Gold Layer SPs

Execute all load SP files in `scripts/gold/`:

```bash
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_dim_customer.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_dim_product.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_dim_seller.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_dim_marketing_channel.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_fact_order_items.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_fact_payments.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_fact_reviews.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_fact_order_life_cycle.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_load_fact_marketing_funnel.sql
sqlcmd -S YOUR_SERVER -d BI_AI -i scripts/gold/gold_master.sql
```

---

## Verification

After setup, verify row counts in Gold:

```sql
USE [BI_AI];
SELECT 'dim_date'               AS table_name, COUNT(*) AS row_count FROM gold.dim_date
UNION ALL SELECT 'dim_customer',               COUNT(*) FROM gold.dim_customer
UNION ALL SELECT 'dim_product',                COUNT(*) FROM gold.dim_product
UNION ALL SELECT 'dim_seller',                 COUNT(*) FROM gold.dim_seller
UNION ALL SELECT 'dim_payment_type',           COUNT(*) FROM gold.dim_payment_type
UNION ALL SELECT 'dim_order_status',           COUNT(*) FROM gold.dim_order_status
UNION ALL SELECT 'dim_marketing_channel',      COUNT(*) FROM gold.dim_marketing_channel
UNION ALL SELECT 'fact_order_items',           COUNT(*) FROM gold.fact_order_items
UNION ALL SELECT 'fact_payments',              COUNT(*) FROM gold.fact_payments
UNION ALL SELECT 'fact_reviews',               COUNT(*) FROM gold.fact_reviews
UNION ALL SELECT 'fact_order_life_cycle',      COUNT(*) FROM gold.fact_order_life_cycle
UNION ALL SELECT 'fact_marketing_funnel',      COUNT(*) FROM gold.fact_marketing_funnel
ORDER BY table_name;
```

Expected approximate row counts after a successful full pipeline run:

| Table | Expected Rows |
|-------|--------------|
| dim_customer | ~96,097 |
| dim_product | ~32,951 |
| dim_seller | ~3,096 |
| fact_order_items | ~112,650 |
| fact_payments | ~103,886 |
| fact_reviews | ~99,441 |
| fact_order_life_cycle | ~99,441 |
| fact_marketing_funnel | ~842 |

---

## Troubleshooting Common Issues

### ❌ ODBC Driver Not Found
```
No SQL Server ODBC driver found.
```
**Fix:** Download and install [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

### ❌ Cannot connect to SQL Server
```
Could not connect to DESKTOP-XXXXX
```
**Checklist:**
1. ✅ SQL Server service is running (check Windows Services or SQL Server Configuration Manager)
2. ✅ TCP/IP is enabled in SQL Server Configuration Manager → Network Configuration
3. ✅ SQL Server Browser service is running (needed for named instances)
4. ✅ Server name matches exactly what SSMS shows

### ❌ STRING_SPLIT ordinal syntax error
```
The function 'string_split' requires the compatibility level 130
```
**Fix:** SQL Server 2022 is required. Alternatively, upgrade database compatibility level:
```sql
ALTER DATABASE [BI_AI] SET COMPATIBILITY_LEVEL = 160; -- SQL Server 2022
```

### ❌ psycopg2 SSL error on Neon PostgreSQL
```
SSL connection has been closed unexpectedly
```
**Fix:** Ensure `SOURCE_DB_SSL_MODE=require` is set in `.env` and that `psycopg2-binary` is installed.
