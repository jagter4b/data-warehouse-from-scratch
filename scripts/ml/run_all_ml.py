"""
run_all_ml.py
─────────────
Orchestrator — runs all ML scripts in order:
  1. ml_customer_segments.py    (K-Means RFM)
  2. ml_churn_prediction.py     (Random Forest)
  3. ml_delivery_risk.py        (XGBoost classifier)
  4. ml_review_prediction.py    (XGBoost regressor)
  5. ml_seller_performance.py   (Weighted KPI + K-Means)

Usage:
    python scripts/ml/run_all_ml.py           # dry-run all
    python scripts/ml/run_all_ml.py --execute # run all and write to DB
"""

import argparse
import importlib
import sys
import os
import time

# Ensure scripts/ml is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

MODULES = [
    ("ml_customer_segments",  "K-Means RFM Segmentation"),
    ("ml_churn_prediction",   "Random Forest Churn"),
    ("ml_delivery_risk",      "XGBoost Delivery Risk"),
    ("ml_review_prediction",  "XGBoost Review Prediction"),
    ("ml_seller_performance", "Seller Performance Scoring"),
]


def get_engine():
    import os
    from sqlalchemy import create_engine
    from dotenv import load_dotenv
    load_dotenv()
    host = os.getenv("DEST_DB_HOST", "localhost")
    port = os.getenv("DEST_DB_PORT", "1433")
    db   = os.getenv("DEST_DB_NAME", "BI_AI").strip()
    return create_engine(
        f"mssql+pyodbc://@{host}:{port}/{db}"
        f"?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes",
        fast_executemany=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Write ML results to DB")
    args = parser.parse_args()

    engine = get_engine()
    total_start = time.time()
    results = []

    print("\n" + "=" * 70)
    print("  Olist ML Pipeline — run_all_ml.py")
    print(f"  Mode: {'EXECUTE (writing to DB)' if args.execute else 'DRY-RUN'}")
    print("=" * 70)

    for module_name, label in MODULES:
        print(f"\n{'─'*70}")
        print(f"  Running: {label}")
        print(f"{'─'*70}")
        t0 = time.time()
        try:
            mod = importlib.import_module(module_name)
            importlib.reload(mod)   # force fresh run
            mod.run(engine, execute=args.execute)
            elapsed = time.time() - t0
            results.append((label, "✅ OK", f"{elapsed:.1f}s"))
        except Exception as e:
            elapsed = time.time() - t0
            results.append((label, f"❌ FAILED: {e}", f"{elapsed:.1f}s"))
            print(f"\n  ERROR in {module_name}: {e}")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}")
    print("  Pipeline Summary")
    print(f"{'='*70}")
    for label, status, elapsed in results:
        print(f"  {status:<40} {label}  ({elapsed})")
    print(f"\n  Total runtime: {total_elapsed:.1f}s")
    print(f"{'='*70}\n")
