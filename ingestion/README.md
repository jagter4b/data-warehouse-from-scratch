## ✅ Bronze Layer Ingestion — Complete

All **11 tables** are now loaded into `[BI_AI].[bronze]` in your local SQL Server:

| Pipeline | Status | Time | Tables / Rows |
|---|---|---|---|
| **Neon PostgreSQL** | ✓ SUCCESS | 159.2s | 7 tables: customers (99K), orders (99K), order_items (112K), order_payments (103K), sellers (3K), products (32K), product_category_name_translation (71) |
| **Google Drive** | ✓ SUCCESS | 93.3s | closed_deals (842), marketing_qualified_leads (8K), order_reviews (100K) |
| **Geolocation API (GAS)** | ✓ SUCCESS | 53.5s | geolocation (855,781 rows, 52MB) |
| **Total** | ✓ | **306s** | **~1.28 million rows ingested** |



**Key design decisions:**
- **ELT pattern**: All data lands AS-IS in `bronze` — zero transformations
- **Idempotent**: Each run drops & recreates the target table (safe to re-run anytime)
- **Audit columns**: Every row gets `_ingested_at`, `_source`, and source-specific metadata
- **SQL Server fix**: Dynamic `safe_chunk = floor(2000 / num_cols)` bypasses the ODBC 2100-parameter limit
- **Google Sheet detection**: `order_reviews` uses the Sheets export URL automatically
