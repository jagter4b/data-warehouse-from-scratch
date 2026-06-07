"""
ml_churn_prediction.py
───────────────────────
Random Forest customer churn classifier.

Definition: a customer is "churned" if their LAST purchase was more than
180 days before the anchor date (2018-10-17) AND they only placed 1 order
OR their last order was >365 days ago.

Outputs written to gold.obt_master:
  churn_probability  FLOAT
  churn_risk_tier    VARCHAR ('High' | 'Medium' | 'Low')

Usage:
    python scripts/ml/ml_churn_prediction.py
    python scripts/ml/ml_churn_prediction.py --execute
"""

import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from dotenv import load_dotenv

load_dotenv()

ANCHOR_DATE  = pd.Timestamp("2018-10-17")
CHURN_DAYS   = 180     # inactive for > 6 months = churned


def get_engine():
    host = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    return create_engine(
        f"mssql+pyodbc://@{host}:{port}/{db}"
        f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
        fast_executemany=True,
    )


def risk_tier(prob):
    if prob >= 0.65:
        return "High"
    elif prob >= 0.40:
        return "Medium"
    return "Low"


def run(engine, execute: bool = False):
    print("=" * 60)
    print("ml_churn_prediction.py  [Random Forest Churn]")
    print("=" * 60)

    # ── 1. Load ───────────────────────────────────────────────
    print("\n[1/6] Loading data from gold.obt_master ...")
    q = """
    SELECT customer_unique_id, purchase_date, total_order_value,
           total_items, total_freight_value, review_score,
           days_to_deliver, days_delivery_variance, is_delivered_on_time,
           payment_type, payment_installments
    FROM gold.obt_master
    WHERE order_status = 'delivered'
      AND customer_unique_id IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    print(f"      → {len(df):,} rows")

    # ── 2. Build customer-level features ─────────────────────
    print("\n[2/6] Engineering customer-level features ...")

    cust = df.groupby("customer_unique_id").agg(
        recency_days     = ("purchase_date", lambda x: (ANCHOR_DATE - x.max()).days),
        frequency        = ("purchase_date", "count"),
        monetary         = ("total_order_value", "sum"),
        avg_order_value  = ("total_order_value", "mean"),
        avg_review_score = ("review_score", "mean"),
        pct_on_time      = ("is_delivered_on_time", "mean"),
        avg_days_deliver = ("days_to_deliver", "mean"),
        avg_variance     = ("days_delivery_variance", "mean"),
    ).reset_index()

    # Target: churned = last purchase > CHURN_DAYS ago
    cust["churned"] = (cust["recency_days"] > CHURN_DAYS).astype(int)
    churn_rate = cust["churned"].mean()
    print(f"      → {len(cust):,} customers | churn rate: {churn_rate:.1%}")

    # ── 3. Train model ────────────────────────────────────────
    print("\n[3/6] Training Random Forest ...")
    feature_cols = [
        "frequency", "monetary", "avg_order_value",
        "avg_review_score", "pct_on_time", "avg_days_deliver", "avg_variance"
    ]  # NOTE: recency_days excluded — it IS the churn definition (data leakage)
    X = cust[feature_cols].fillna(0)
    y = cust["churned"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, class_weight="balanced",
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)

    y_prob_test = rf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob_test)
    print(f"      → AUC-ROC: {auc:.4f}")
    print(classification_report(y_test, (y_prob_test >= 0.5).astype(int), digits=3))

    # ── 4. Score all customers ────────────────────────────────
    print("\n[4/6] Scoring all customers ...")
    cust["churn_probability"] = rf.predict_proba(X.fillna(0))[:, 1]
    cust["churn_risk_tier"]   = cust["churn_probability"].apply(risk_tier)

    result = cust[["customer_unique_id", "churn_probability", "churn_risk_tier"]].copy()
    tier_counts = result["churn_risk_tier"].value_counts()
    print(f"      → {tier_counts.to_string()}")

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(result.head(5).to_string())
        return

    # ── 5. Write to gold.obt_master ──────────────────────────
    print("\n[5/6] Writing results to gold.obt_master ...")
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#churn_stage', 'U') IS NOT NULL DROP TABLE #churn_stage;
            CREATE TABLE #churn_stage (
                customer_unique_id VARCHAR(50),
                churn_probability  FLOAT,
                churn_risk_tier    VARCHAR(10)
            );
        """))
        result.to_sql("#churn_stage", schema=None, con=conn,
                      if_exists="append", index=False, chunksize=5000)
        conn.execute(text("""
            UPDATE o
            SET o.churn_probability = s.churn_probability,
                o.churn_risk_tier   = s.churn_risk_tier
            FROM gold.obt_master o
            JOIN #churn_stage s ON o.customer_unique_id = s.customer_unique_id;
        """))

    print(f"      → {len(result):,} customer rows updated ✓")
    print("\n✅ Churn prediction complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    run(engine, execute=args.execute)
