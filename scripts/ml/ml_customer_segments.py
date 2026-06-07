"""
ml_customer_segments.py
────────────────────────
RFM-based K-Means customer segmentation (k=4).
Reads from gold.obt_master, computes RFM features, runs K-Means,
then writes segment labels back to gold.obt_master.

Segments: Champions | Loyal | At Risk | Lost/Inactive

Usage:
    python scripts/ml/ml_customer_segments.py           # dry-run
    python scripts/ml/ml_customer_segments.py --execute # write to DB
"""

import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from dotenv import load_dotenv

load_dotenv()

ANCHOR_DATE = pd.Timestamp("2018-10-17")   # max purchase date in dataset + 1 day
N_CLUSTERS  = 4
RANDOM_STATE = 42


def get_engine():
    host = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    return create_engine(
        f"mssql+pyodbc://@{host}:{port}/{db}"
        f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
        fast_executemany=True,
    )


def label_segment(row):
    """Map (R, F, M) ranks 1-4 to a human-readable segment."""
    r, f, m = row["r_rank"], row["f_rank"], row["m_rank"]
    score = (r + f + m) / 3
    if score >= 3.5:
        return "Champions"
    elif score >= 2.5:
        return "Loyal"
    elif score >= 1.8:
        return "At Risk"
    else:
        return "Lost/Inactive"


def run(engine, execute: bool = False):
    print("=" * 60)
    print("ml_customer_segments.py  [K-Means RFM Segmentation]")
    print("=" * 60)

    # ── 1. Load data ──────────────────────────────────────────
    print("\n[1/5] Loading orders from gold.obt_master ...")
    q = """
    SELECT customer_unique_id, purchase_date, total_order_value
    FROM gold.obt_master
    WHERE order_status = 'delivered'
      AND customer_unique_id IS NOT NULL
      AND total_order_value IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    print(f"      → {len(df):,} delivered orders loaded")

    # ── 2. Compute RFM per customer ───────────────────────────
    print("\n[2/5] Computing RFM features ...")
    rfm = df.groupby("customer_unique_id").agg(
        recency_days   = ("purchase_date", lambda x: (ANCHOR_DATE - x.max()).days),
        frequency_orders = ("purchase_date", "count"),
        monetary_total = ("total_order_value", "sum"),
    ).reset_index()

    print(f"      → {len(rfm):,} unique customers | "
          f"avg recency={rfm.recency_days.mean():.0f}d | "
          f"avg frequency={rfm.frequency_orders.mean():.2f} | "
          f"avg monetary=R${rfm.monetary_total.mean():.2f}")

    # ── 3. Scale + K-Means ────────────────────────────────────
    print(f"\n[3/5] Fitting K-Means (k={N_CLUSTERS}) ...")
    features = rfm[["recency_days", "frequency_orders", "monetary_total"]].copy()
    # Log-transform monetary to reduce skew
    features["monetary_total"] = np.log1p(features["monetary_total"])

    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=10)
    rfm["cluster_id"] = km.fit_predict(X)

    # Rank clusters by mean recency (ascending = more recent = better)
    cluster_means = rfm.groupby("cluster_id")[["recency_days", "frequency_orders", "monetary_total"]].mean()
    cluster_means["r_rank"] = cluster_means["recency_days"].rank(ascending=False)   # low recency = recent = good
    cluster_means["f_rank"] = cluster_means["frequency_orders"].rank(ascending=True)
    cluster_means["m_rank"] = cluster_means["monetary_total"].rank(ascending=True)

    rfm = rfm.merge(cluster_means[["r_rank", "f_rank", "m_rank"]], on="cluster_id")
    rfm["customer_segment"] = rfm.apply(label_segment, axis=1)

    seg_counts = rfm["customer_segment"].value_counts()
    print(f"      → Segment distribution:\n{seg_counts.to_string()}")

    # ── 4. Merge back to order level ──────────────────────────
    print("\n[4/5] Merging results to order level ...")
    result = rfm[["customer_unique_id", "recency_days", "frequency_orders",
                   "monetary_total", "customer_segment"]].copy()

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(result.head(5).to_string())
        return

    # ── 5. Write back to gold.obt_master ──────────────────────
    print("\n[5/5] Writing results to gold.obt_master ...")
    # Build a temp staging table and UPDATE via JOIN
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#seg_stage', 'U') IS NOT NULL
                DROP TABLE #seg_stage;
            CREATE TABLE #seg_stage (
                customer_unique_id VARCHAR(50),
                recency_days INT,
                frequency_orders INT,
                monetary_total FLOAT,
                customer_segment VARCHAR(30)
            );
        """))

        result.to_sql(
            name="#seg_stage", schema=None, con=conn,
            if_exists="append", index=False, chunksize=5000
        )

        conn.execute(text("""
            UPDATE o
            SET o.recency_days       = s.recency_days,
                o.frequency_orders   = s.frequency_orders,
                o.monetary_total     = s.monetary_total,
                o.customer_segment   = s.customer_segment
            FROM gold.obt_master o
            JOIN #seg_stage s ON o.customer_unique_id = s.customer_unique_id;
        """))

    print(f"      → {len(result):,} customer records updated ✓")
    print("\n✅ Customer segmentation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    run(engine, execute=args.execute)
