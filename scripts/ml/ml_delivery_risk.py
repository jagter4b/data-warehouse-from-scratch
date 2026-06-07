"""
ml_delivery_risk.py
────────────────────
XGBoost binary classifier: predicts whether an order will be LATE
(is_delivered_on_time = 0).

Outputs written to gold.obt_master:
  delay_risk_score  FLOAT   (probability of delay)
  delay_risk_tier   VARCHAR ('High' | 'Medium' | 'Low')

Usage:
    python scripts/ml/ml_delivery_risk.py
    python scripts/ml/ml_delivery_risk.py --execute
"""

import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.preprocessing import LabelEncoder
from dotenv import load_dotenv

try:
    import xgboost as xgb
except ImportError:
    raise ImportError("Install xgboost: pip install xgboost")

load_dotenv()


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
    if prob >= 0.40:
        return "High"
    elif prob >= 0.20:
        return "Medium"
    return "Low"


def run(engine, execute: bool = False):
    print("=" * 60)
    print("ml_delivery_risk.py  [XGBoost Delivery Delay]")
    print("=" * 60)

    # ── 1. Load ───────────────────────────────────────────────
    print("\n[1/6] Loading delivered orders from gold.obt_master ...")
    q = """
    SELECT order_id, is_delivered_on_time, total_items, total_order_value,
           total_freight_value, payment_installments, purchase_month,
           purchase_day_of_week, is_weekend_purchase,
           product_category_name, seller_state, customer_state,
           days_to_approve, days_to_ship
    FROM gold.obt_master
    WHERE order_status = 'delivered'
      AND is_delivered_on_time IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    print(f"      → {len(df):,} rows")

    # ── 2. Feature engineering ────────────────────────────────
    print("\n[2/6] Engineering features ...")
    df["is_delivered_on_time"] = df["is_delivered_on_time"].astype(int)
    df["is_weekend_purchase"]  = df["is_weekend_purchase"].astype(int)
    df["is_late"] = (1 - df["is_delivered_on_time"]).astype(int)

    # Encode categoricals
    cat_cols = ["purchase_day_of_week", "product_category_name",
                "seller_state", "customer_state"]
    le = LabelEncoder()
    for c in cat_cols:
        df[c] = df[c].fillna("Unknown")
        df[c + "_enc"] = le.fit_transform(df[c].astype(str))

    feature_cols = [
        "total_items", "total_order_value", "total_freight_value",
        "payment_installments", "purchase_month", "is_weekend_purchase",
        "days_to_approve", "days_to_ship",
    ] + [c + "_enc" for c in cat_cols]

    X = df[feature_cols].fillna(0)
    y = df["is_late"]

    late_rate = y.mean()
    print(f"      → Late rate: {late_rate:.1%} | {int(y.sum()):,} late orders")

    # ── 3. Train XGBoost ──────────────────────────────────────
    print("\n[3/6] Training XGBoost ...")
    scale_pos = (1 - late_rate) / late_rate

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        scale_pos_weight=scale_pos, subsample=0.8, colsample_bytree=0.8,
        random_state=42, eval_metric="auc", verbosity=0, use_label_encoder=False
    )
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], verbose=False)

    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    print(f"      → AUC-ROC: {auc:.4f}")
    print(classification_report(y_test, (y_prob >= 0.5).astype(int), digits=3))

    # ── 4. Score all orders ───────────────────────────────────
    print("\n[4/6] Scoring all orders ...")
    df["delay_risk_score"] = model.predict_proba(X)[:, 1]
    df["delay_risk_tier"]  = df["delay_risk_score"].apply(risk_tier)

    result = df[["order_id", "delay_risk_score", "delay_risk_tier"]].copy()
    tier_counts = result["delay_risk_tier"].value_counts()
    print(f"      → {tier_counts.to_string()}")

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(result.head(5).to_string())
        return

    # ── 5. Write to gold.obt_master ──────────────────────────
    print("\n[5/6] Writing to gold.obt_master ...")
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#delay_stage', 'U') IS NOT NULL DROP TABLE #delay_stage;
            CREATE TABLE #delay_stage (
                order_id          VARCHAR(50),
                delay_risk_score  FLOAT,
                delay_risk_tier   VARCHAR(10)
            );
        """))
        result.to_sql("#delay_stage", schema=None, con=conn,
                      if_exists="append", index=False, chunksize=5000)
        conn.execute(text("""
            UPDATE o
            SET o.delay_risk_score = s.delay_risk_score,
                o.delay_risk_tier  = s.delay_risk_tier
            FROM gold.obt_master o
            JOIN #delay_stage s ON o.order_id = s.order_id;
        """))

    print(f"      → {len(result):,} order rows updated ✓")
    print("\n✅ Delivery risk prediction complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    run(engine, execute=args.execute)
