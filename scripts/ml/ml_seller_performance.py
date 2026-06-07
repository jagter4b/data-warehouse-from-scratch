"""
ml_seller_performance.py
─────────────────────────
Seller performance scoring using weighted KPIs + K-Means (k=3).

KPIs:
  - avg_review_score    (weight 0.35)
  - pct_on_time         (weight 0.30)
  - total_revenue       (weight 0.20)
  - total_orders        (weight 0.15)

Composite score = 0–100.  Tiers: Top Seller / Average / Underperformer

Outputs written to gold.obt_master:
  seller_performance_score  FLOAT
  seller_tier               VARCHAR

Usage:
    python scripts/ml/ml_seller_performance.py
    python scripts/ml/ml_seller_performance.py --execute
"""

import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from dotenv import load_dotenv

load_dotenv()

WEIGHTS = {
    "avg_review_score": 0.35,
    "pct_on_time":      0.30,
    "total_revenue":    0.20,
    "total_orders":     0.15,
}
N_CLUSTERS = 3


def get_engine():
    host = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    return create_engine(
        f"mssql+pyodbc://@{host}:{port}/{db}"
        f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
        fast_executemany=True,
    )


def run(engine, execute: bool = False):
    print("=" * 60)
    print("ml_seller_performance.py  [Weighted KPI + K-Means]")
    print("=" * 60)

    # ── 1. Load ───────────────────────────────────────────────
    print("\n[1/6] Loading seller data from gold.obt_master ...")
    q = """
    SELECT seller_id, order_id, review_score, is_delivered_on_time,
           total_order_value
    FROM gold.obt_master
    WHERE order_status = 'delivered'
      AND seller_id IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    print(f"      → {len(df):,} order rows, {df['seller_id'].nunique():,} sellers")

    # ── 2. Aggregate per seller ───────────────────────────────
    print("\n[2/6] Aggregating seller KPIs ...")
    sellers = df.groupby("seller_id").agg(
        total_orders      = ("order_id", "count"),
        avg_review_score  = ("review_score", "mean"),
        pct_on_time       = ("is_delivered_on_time", "mean"),
        total_revenue     = ("total_order_value", "sum"),
    ).reset_index()

    print(f"      → {len(sellers):,} sellers aggregated")
    print(f"        avg review: {sellers['avg_review_score'].mean():.2f}")
    print(f"        avg on-time: {sellers['pct_on_time'].mean():.1%}")

    # ── 3. Compute composite score ────────────────────────────
    print("\n[3/6] Computing composite score (0–100) ...")
    kpi_cols = list(WEIGHTS.keys())
    scaler = MinMaxScaler()
    scaled = pd.DataFrame(
        scaler.fit_transform(sellers[kpi_cols]),
        columns=kpi_cols
    )
    sellers["seller_performance_score"] = sum(
        scaled[col] * WEIGHTS[col] for col in kpi_cols
    ) * 100

    print(f"      → Score range: [{sellers['seller_performance_score'].min():.1f}, "
          f"{sellers['seller_performance_score'].max():.1f}] | "
          f"avg={sellers['seller_performance_score'].mean():.1f}")

    # ── 4. K-Means cluster → seller tier ─────────────────────
    print(f"\n[4/6] K-Means clustering (k={N_CLUSTERS}) ...")
    X = sellers[["seller_performance_score"]].values
    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    sellers["cluster_id"] = km.fit_predict(X)

    cluster_means = sellers.groupby("cluster_id")["seller_performance_score"].mean()
    sorted_clusters = cluster_means.sort_values(ascending=False).index.tolist()
    tier_map = {
        sorted_clusters[0]: "Top Seller",
        sorted_clusters[1]: "Average",
        sorted_clusters[2]: "Underperformer",
    }
    sellers["seller_tier"] = sellers["cluster_id"].map(tier_map)

    tier_counts = sellers["seller_tier"].value_counts()
    print(f"      → {tier_counts.to_string()}")

    result = sellers[["seller_id", "seller_performance_score", "seller_tier"]].copy()

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(result.head(5).to_string())
        return

    # ── 5. Write to gold.obt_master ──────────────────────────
    print("\n[5/6] Writing to gold.obt_master ...")
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#seller_stage', 'U') IS NOT NULL DROP TABLE #seller_stage;
            CREATE TABLE #seller_stage (
                seller_id                VARCHAR(50),
                seller_performance_score FLOAT,
                seller_tier              VARCHAR(30)
            );
        """))
        result.to_sql("#seller_stage", schema=None, con=conn,
                      if_exists="append", index=False, chunksize=5000)
        conn.execute(text("""
            UPDATE o
            SET o.seller_performance_score = s.seller_performance_score,
                o.seller_tier              = s.seller_tier
            FROM gold.obt_master o
            JOIN #seller_stage s ON o.seller_id = s.seller_id;
        """))

    print(f"      → {len(result):,} seller records updated ✓")
    print("\n✅ Seller performance scoring complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    run(engine, execute=args.execute)
