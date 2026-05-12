# Gold Layer: Dimensional Modeling

The Gold layer is the final stage of our Medallion Architecture, providing business-ready, analytical models structured as a Kimball Galaxy Schema. This layer is optimized for fast read queries, business intelligence reporting, and cross-domain analytics.

## Architecture & Design

The Gold layer integrates e-commerce operational data with marketing funnel metrics using a dimensional modeling approach. 

### Dimensions (SCD Type 1)
- `gold.dim_customer`: Customer demographic and geographic information. Grain: One row per unique customer (`customer_unique_id`).
- `gold.dim_product`: Product catalog including category, weight, and dimensions. Grain: One row per product.
- `gold.dim_seller`: Seller geographic and identifier details. Grain: One row per seller.
- `gold.dim_marketing_channel`: Marketing channel attributes derived from UTM parameters and acquisition channels.
- `gold.dim_date`: A conformed date spine (2016-2020) used across all facts to enable unified time-series analysis.

### Fact Tables
- `gold.fact_order_items`: Core e-commerce metrics (price, freight value). Grain: One row per order item.
- `gold.fact_payments`: Payment metrics and installment details. Grain: One row per payment method per order.
- `gold.fact_reviews`: Customer satisfaction metrics (review score). Grain: One row per order review.
- `gold.fact_order_life_cycle`: Accumulating snapshot tracking order progression (purchase, approval, shipping, delivery). Grain: One row per order.
- `gold.fact_marketing_funnel`: Marketing conversions and lead acquisition metrics. Grain: One row per qualified lead (MQL).

### Outriggers
- `gold.review_comments`: Captures large text data (review titles and messages) independently to keep the `fact_reviews` table lean and high-performing.

## ETL Processes & Idempotency

- **Dimension Loads**: Implemented using `MERGE` statements (SCD Type 1) to handle inserts and updates idempotently.
- **Fact Loads**: Implemented using a combination of `TRUNCATE` and `INSERT` for rapid, full-reload idempotency. 
  - *Note*: Tables referenced by foreign keys (e.g., `fact_reviews` referenced by `review_comments`) use specific drop-truncate-recreate constraint patterns.
- **Orchestration**: The `gold.gold_master` stored procedure orchestrates the entire layer load, processing dimensions before facts to ensure referential integrity.

## Execution

To refresh the entire Gold layer, execute the master orchestration procedure:

```sql
EXEC gold.gold_master;
```
