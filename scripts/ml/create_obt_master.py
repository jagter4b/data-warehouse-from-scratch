"""
create_obt_master.py
────────────────────
Builds gold.obt_master — a single denormalized One Big Table joining all
key gold-layer facts and dimensions.

Grain: one row per order (order_id is the PK).

Extra columns added by ML scripts:
  customer_segment, churn_probability, churn_risk_tier,
  delay_risk_score, delay_risk_tier,
  predicted_review_score, predicted_satisfaction,
  seller_performance_score, seller_tier

Usage:
    python scripts/ml/create_obt_master.py           # dry-run (print row count)
    python scripts/ml/create_obt_master.py --execute  # create / refresh table
"""

import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────────
# DB connection
# ──────────────────────────────────────────────
def get_engine():
    host = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    conn = (
        f"mssql+pyodbc://@{host}:{port}/{db}"
        f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes"
    )
    return create_engine(conn, fast_executemany=True)


# ──────────────────────────────────────────────
# DDL for gold.obt_master
# ──────────────────────────────────────────────
DDL_DROP_CREATE = """
IF OBJECT_ID('gold.obt_master', 'U') IS NOT NULL
    DROP TABLE gold.obt_master;

CREATE TABLE gold.obt_master (
    -- Order
    order_id                     VARCHAR(50)     NOT NULL,
    purchase_date                DATE            NULL,
    purchase_year                INT             NULL,
    purchase_month               INT             NULL,
    purchase_month_name          VARCHAR(20)     NULL,
    purchase_day_of_week         VARCHAR(20)     NULL,
    is_weekend_purchase          BIT             NULL,
    order_status                 VARCHAR(30)     NULL,

    -- Customer
    customer_unique_id           VARCHAR(50)     NULL,
    customer_state               CHAR(2)         NULL,
    customer_city                VARCHAR(100)    NULL,

    -- Delivery
    days_to_approve              INT             NULL,
    days_to_ship                 INT             NULL,
    days_to_deliver              INT             NULL,
    days_purchase_to_delivery    INT             NULL,
    days_delivery_variance       INT             NULL,
    is_delivered_on_time         BIT             NULL,

    -- Order value
    total_items                  INT             NULL,
    total_distinct_products      INT             NULL,
    total_distinct_sellers       INT             NULL,
    total_order_value            DECIMAL(12,2)   NULL,
    total_freight_value          DECIMAL(12,2)   NULL,
    total_payment_value          DECIMAL(12,2)   NULL,

    -- Payment
    payment_type                 VARCHAR(30)     NULL,
    payment_installments         INT             NULL,

    -- Product
    product_category_name        VARCHAR(100)    NULL,

    -- Seller
    seller_id                    VARCHAR(50)     NULL,
    seller_state                 CHAR(2)         NULL,
    seller_city                  VARCHAR(100)    NULL,

    -- Review
    review_score                 TINYINT         NULL,

    -- Marketing (seller acquisition)
    marketing_origin             VARCHAR(50)     NULL,
    days_to_close                INT             NULL,
    business_segment             VARCHAR(100)    NULL,
    lead_type                    VARCHAR(100)    NULL,
    business_type                VARCHAR(100)    NULL,

    -- ML Outputs (filled by ML scripts)
    recency_days                 INT             NULL,
    frequency_orders             INT             NULL,
    monetary_total               DECIMAL(14,2)   NULL,
    customer_segment             VARCHAR(30)     NULL,
    churn_probability            FLOAT           NULL,
    churn_risk_tier              VARCHAR(10)     NULL,
    delay_risk_score             FLOAT           NULL,
    delay_risk_tier              VARCHAR(10)     NULL,
    predicted_review_score       FLOAT           NULL,
    predicted_satisfaction       VARCHAR(20)     NULL,
    seller_performance_score     FLOAT           NULL,
    seller_tier                  VARCHAR(30)     NULL,

    -- Audit
    load_timestamp               DATETIME        DEFAULT GETDATE(),

    CONSTRAINT pk_obt_master PRIMARY KEY (order_id)
);
"""

# ──────────────────────────────────────────────
# Individual sub-queries (kept separate for readability)
# ──────────────────────────────────────────────

# Deduplicated payment: pick the payment_type with highest total value per order
QUERY_PAYMENT = """
SELECT order_id_bk, payment_type_sk, MAX(payment_installments) AS payment_installments
FROM (
    SELECT order_id_bk, payment_type_sk, payment_installments,
           SUM(payment_value) OVER (PARTITION BY order_id_bk, payment_type_sk) AS total_val,
           ROW_NUMBER() OVER (PARTITION BY order_id_bk ORDER BY SUM(payment_value) OVER (PARTITION BY order_id_bk, payment_type_sk) DESC) AS rn
    FROM gold.fact_payments
) sub
WHERE rn = 1
GROUP BY order_id_bk, payment_type_sk
"""

# Deduplicated marketing funnel: most recent won deal per seller
QUERY_MKT = """
SELECT seller_sk, mql_channel_sk, days_to_close
FROM (
    SELECT seller_sk, mql_channel_sk, days_to_close,
           ROW_NUMBER() OVER (PARTITION BY seller_sk ORDER BY won_date_key DESC) AS rn
    FROM gold.fact_marketing_funnel
    WHERE seller_sk <> -1
) sub
WHERE rn = 1
"""

# Main OBT query
QUERY_BUILD = """
WITH pay_agg AS (
    -- Step 1: aggregate total value per order+payment_type combination
    SELECT order_id_bk, payment_type_sk,
           SUM(payment_value)           AS total_pay_value,
           MAX(payment_installments)    AS payment_installments
    FROM gold.fact_payments
    GROUP BY order_id_bk, payment_type_sk
),
pay_dedup AS (
    -- Step 2: keep only the highest-value payment type per order
    SELECT order_id_bk, payment_type_sk, payment_installments
    FROM (
        SELECT order_id_bk, payment_type_sk, payment_installments,
               ROW_NUMBER() OVER (PARTITION BY order_id_bk ORDER BY total_pay_value DESC) AS rn
        FROM pay_agg
    ) s1
    WHERE rn = 1
),
item_first AS (
    SELECT order_id_bk, MIN(order_item_id_bk) AS min_item_id
    FROM gold.fact_order_items
    GROUP BY order_id_bk
),
mkt_dedup AS (
    SELECT seller_sk, mql_channel_sk, days_to_close
    FROM (
        SELECT seller_sk, mql_channel_sk, days_to_close,
               ROW_NUMBER() OVER (PARTITION BY seller_sk ORDER BY won_date_key DESC) AS rn
        FROM gold.fact_marketing_funnel
        WHERE seller_sk <> -1
    ) s2
    WHERE rn = 1
)
SELECT
    olc.order_id_bk                          AS order_id,
    CAST(dd.full_date AS DATE)               AS purchase_date,
    dd.year                                  AS purchase_year,
    dd.month_num                             AS purchase_month,
    dd.month_name                            AS purchase_month_name,
    dd.day_of_week_name                      AS purchase_day_of_week,
    dd.is_weekend                            AS is_weekend_purchase,
    dos.order_status,
    dc.customer_unique_id_bk                 AS customer_unique_id,
    dc.customer_state,
    dc.customer_city,
    olc.days_to_approve,
    olc.days_to_ship,
    olc.days_to_deliver,
    olc.days_purchase_to_delivery,
    olc.days_delivery_variance,
    olc.is_delivered_on_time,
    olc.total_items,
    olc.total_distinct_products,
    olc.total_distinct_sellers,
    olc.total_order_value,
    olc.total_freight_value,
    olc.total_payment_value,
    dpt.payment_type,
    pd.payment_installments,
    dp.product_category_name,
    ds.seller_id_bk                          AS seller_id,
    ds.seller_state,
    ds.seller_city,
    fr.review_score,
    dmc.origin                               AS marketing_origin,
    mk.days_to_close,
    dmc.business_segment,
    dmc.lead_type,
    dmc.business_type
FROM gold.fact_order_life_cycle olc
LEFT JOIN gold.dim_date dd          ON olc.purchase_date_key = dd.date_key
LEFT JOIN gold.dim_customer dc      ON olc.customer_sk = dc.customer_sk
LEFT JOIN gold.dim_order_status dos ON olc.order_status_sk = dos.order_status_sk
LEFT JOIN gold.fact_reviews fr      ON olc.order_id_bk = fr.order_id_bk
LEFT JOIN pay_dedup pd              ON olc.order_id_bk = pd.order_id_bk
LEFT JOIN gold.dim_payment_type dpt ON pd.payment_type_sk = dpt.payment_type_sk
LEFT JOIN item_first itf            ON olc.order_id_bk = itf.order_id_bk
LEFT JOIN gold.fact_order_items foi ON olc.order_id_bk = foi.order_id_bk
                                    AND foi.order_item_id_bk = itf.min_item_id
LEFT JOIN gold.dim_product dp       ON foi.product_sk = dp.product_sk
LEFT JOIN gold.dim_seller ds        ON foi.seller_sk = ds.seller_sk
LEFT JOIN mkt_dedup mk              ON ds.seller_sk = mk.seller_sk
LEFT JOIN gold.dim_marketing_channel dmc ON mk.mql_channel_sk = dmc.mql_channel_sk
"""


# ──────────────────────────────────────────────
# Build + write
# ──────────────────────────────────────────────
def build_obt(engine, execute: bool = False):
    print("=" * 60)
    print("create_obt_master.py")
    print("=" * 60)

    print("\n[1/4] Fetching data from gold schema ...")
    with engine.connect() as conn:
        df = pd.read_sql(QUERY_BUILD, conn)

    print(f"      → {len(df):,} rows fetched")

    # Deduplicate at Python level (safety net)
    before = len(df)
    df = df.drop_duplicates(subset="order_id", keep="first")
    after = len(df)
    if before != after:
        print(f"      → Dropped {before - after} duplicate order_ids (kept first)")

    print(f"      → {len(df):,} unique orders")

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(df.dtypes)
        print(df.head(3).to_string())
        return

    print("\n[2/4] Creating gold.obt_master DDL ...")
    with engine.begin() as conn:
        conn.execute(text(DDL_DROP_CREATE))
    print("      → Table created")

    print("\n[3/4] Adding ML placeholder columns ...")
    ml_cols = [
        "recency_days", "frequency_orders", "monetary_total",
        "customer_segment", "churn_probability", "churn_risk_tier",
        "delay_risk_score", "delay_risk_tier",
        "predicted_review_score", "predicted_satisfaction",
        "seller_performance_score", "seller_tier",
    ]
    for c in ml_cols:
        df[c] = None

    print("\n[4/4] Inserting rows ...")
    df.to_sql(
        name="obt_master",
        schema="gold",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=5000,
    )
    print(f"      → {len(df):,} rows inserted into gold.obt_master ✓")
    print("\n✅ Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write to DB")
    args = parser.parse_args()
    engine = get_engine()
    build_obt(engine, execute=args.execute)
