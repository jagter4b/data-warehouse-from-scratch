"""
ml_review_prediction.py
────────────────────────
XGBoost regressor to predict the review score (1.0–5.0) for an order.

Outputs written to gold.obt_master:
  predicted_review_score  FLOAT
  predicted_satisfaction  VARCHAR ('Excellent' | 'Good' | 'Average' | 'Poor')

Usage:
    python scripts/ml/ml_review_prediction.py
    python scripts/ml/ml_review_prediction.py --execute
"""

import os
import argparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
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


def satisfaction_label(score: float) -> str:
    if score >= 4.5:
        return "Excellent"
    elif score >= 3.5:
        return "Good"
    elif score >= 2.5:
        return "Average"
    return "Poor"


def run(engine, execute: bool = False):
    print("=" * 60)
    print("ml_review_prediction.py  [XGBoost Review Regressor]")
    print("=" * 60)

    # ── 1. Load ───────────────────────────────────────────────
    print("\n[1/6] Loading orders with reviews from gold.obt_master ...")
    q = """
    SELECT order_id, review_score, total_items, total_order_value,
           total_freight_value, payment_installments, payment_type,
           purchase_month, purchase_day_of_week, is_weekend_purchase,
           days_to_approve, days_to_ship, days_to_deliver,
           days_delivery_variance, is_delivered_on_time,
           product_category_name, seller_state, customer_state
    FROM gold.obt_master
    WHERE order_status = 'delivered'
      AND review_score IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    print(f"      → {len(df):,} rows with reviews")

    # ── 2. Feature engineering ────────────────────────────────
    print("\n[2/6] Engineering features ...")
    df["is_delivered_on_time"] = df["is_delivered_on_time"].fillna(0).astype(int)
    df["is_weekend_purchase"]  = df["is_weekend_purchase"].fillna(0).astype(int)

    cat_cols = ["payment_type", "purchase_day_of_week",
                "product_category_name", "seller_state", "customer_state"]
    le = LabelEncoder()
    for c in cat_cols:
        df[c] = df[c].fillna("Unknown")
        df[c + "_enc"] = le.fit_transform(df[c].astype(str))

    feature_cols = [
        "total_items", "total_order_value", "total_freight_value",
        "payment_installments", "purchase_month", "is_weekend_purchase",
        "days_to_approve", "days_to_ship", "days_to_deliver",
        "days_delivery_variance", "is_delivered_on_time",
    ] + [c + "_enc" for c in cat_cols]

    X = df[feature_cols].fillna(0)
    y = df["review_score"].astype(float)

    # ── 3. Train XGBoost Regressor ────────────────────────────
    print("\n[3/6] Training XGBoost Regressor ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators=400, max_depth=6, learning_rate=0.04,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae  = mean_absolute_error(y_test, y_pred)
    r2   = r2_score(y_test, y_pred)
    print(f"      → RMSE: {rmse:.4f} | MAE: {mae:.4f} | R²: {r2:.4f}")

    # ── 4. Score all orders ───────────────────────────────────
    print("\n[4/6] Scoring all orders ...")
    preds = model.predict(X)
    preds = np.clip(preds, 1.0, 5.0)   # clamp to valid range
    df["predicted_review_score"] = np.round(preds * 2) / 2   # round to nearest 0.5
    df["predicted_satisfaction"] = df["predicted_review_score"].apply(satisfaction_label)

    result = df[["order_id", "predicted_review_score", "predicted_satisfaction"]].copy()
    sat_counts = result["predicted_satisfaction"].value_counts()
    print(f"      → Satisfaction distribution:\n{sat_counts.to_string()}")

    if not execute:
        print("\n[DRY-RUN] Pass --execute to write to DB")
        print(result.head(5).to_string())
        return

    # ── 5. Write to gold.obt_master ──────────────────────────
    print("\n[5/6] Writing to gold.obt_master ...")
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('tempdb..#review_stage', 'U') IS NOT NULL DROP TABLE #review_stage;
            CREATE TABLE #review_stage (
                order_id               VARCHAR(50),
                predicted_review_score FLOAT,
                predicted_satisfaction VARCHAR(20)
            );
        """))
        result.to_sql("#review_stage", schema=None, con=conn,
                      if_exists="append", index=False, chunksize=5000)
        conn.execute(text("""
            UPDATE o
            SET o.predicted_review_score = s.predicted_review_score,
                o.predicted_satisfaction = s.predicted_satisfaction
            FROM gold.obt_master o
            JOIN #review_stage s ON o.order_id = s.order_id;
        """))

    print(f"      → {len(result):,} order rows updated ✓")
    print("\n✅ Review prediction complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    engine = get_engine()
    run(engine, execute=args.execute)
