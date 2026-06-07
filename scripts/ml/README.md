# 🤖 ML Pipeline Documentation

## Overview

The ML pipeline reads from `gold.obt_master` (the One Big Table), trains models, and writes results **back into the same table** as additional columns — a clean, self-contained feature store + inference layer.

---

## Architecture

```
gold layer (facts + dims)
        │
        ▼
create_obt_master.py  ──►  gold.obt_master  (99,441 rows, 47 columns)
                                   │
              ┌────────────────────┼──────────────────────┐
              │                    │                       │
              ▼                    ▼                       ▼
  ml_customer_segments   ml_delivery_risk     ml_seller_performance
  ml_churn_prediction    ml_review_prediction
              │                    │                       │
              └────────────────────▼───────────────────────┘
                          gold.obt_master
                    (ML columns updated in-place)
```

---

## Scripts

### `create_obt_master.py`

Builds `gold.obt_master` by joining all gold-layer facts and dimensions.

**Grain:** one row per order (`order_id` is the PK).

| Column Group | Columns |
|---|---|
| Order | `order_id`, `purchase_date`, `purchase_year/month/day_of_week`, `order_status` |
| Customer | `customer_unique_id`, `customer_state`, `customer_city` |
| Delivery | `days_to_approve/ship/deliver`, `days_delivery_variance`, `is_delivered_on_time` |
| Value | `total_items`, `total_order_value`, `total_freight_value`, `total_payment_value` |
| Payment | `payment_type`, `payment_installments` |
| Product | `product_category_name` |
| Seller | `seller_id`, `seller_state`, `seller_city` |
| Review | `review_score` |
| Marketing | `marketing_origin`, `days_to_close`, `business_segment`, `lead_type`, `business_type` |
| ML Outputs | see below |

**Usage:**
```bash
python scripts/ml/create_obt_master.py           # dry-run
python scripts/ml/create_obt_master.py --execute  # write to DB
```

---

### `ml_customer_segments.py`

**Algorithm:** K-Means (k=4) on RFM features.

| RFM Feature | Description |
|---|---|
| Recency | Days since last purchase (anchor: 2018-10-17) |
| Frequency | Total number of orders |
| Monetary | Total spend (log-transformed for skew) |

**Output columns in OBT:**

| Column | Type | Description |
|---|---|---|
| `recency_days` | INT | Days since last purchase |
| `frequency_orders` | INT | Total orders |
| `monetary_total` | DECIMAL | Total lifetime spend |
| `customer_segment` | VARCHAR | Champions / Loyal / At Risk / Lost/Inactive |

**Usage:**
```bash
python scripts/ml/ml_customer_segments.py --execute
```

---

### `ml_churn_prediction.py`

**Algorithm:** Random Forest Classifier (200 trees, `class_weight='balanced'`).

**Churn definition:** Customer whose last purchase was >180 days before the anchor date (2018-10-17), i.e., inactive for 6+ months.

**Features:** `frequency`, `monetary`, `avg_order_value`, `avg_review_score`, `pct_on_time`, `avg_days_deliver`, `avg_variance`

> **Note:** `recency_days` is deliberately excluded from training features — it is the churn label definition and would cause data leakage.

**Performance:** AUC-ROC = **0.70** on held-out test set (20%).

**Output columns in OBT:**

| Column | Type | Description |
|---|---|---|
| `churn_probability` | FLOAT | Probability of churn (0–1) |
| `churn_risk_tier` | VARCHAR | High / Medium / Low |

**Usage:**
```bash
python scripts/ml/ml_churn_prediction.py --execute
```

---

### `ml_delivery_risk.py`

**Algorithm:** XGBoost Binary Classifier (predicts `is_delivered_on_time = 0`).

**Class imbalance:** 6.8% late orders → handled via `scale_pos_weight`.

**Features:** order size, payment installments, purchase month/day, product category, seller/customer state, days to approve/ship.

**Performance:** AUC-ROC = **0.80**.

**Output columns in OBT:**

| Column | Type | Description |
|---|---|---|
| `delay_risk_score` | FLOAT | Probability of delay (0–1) |
| `delay_risk_tier` | VARCHAR | High (≥40%) / Medium (20–40%) / Low (<20%) |

**Usage:**
```bash
python scripts/ml/ml_delivery_risk.py --execute
```

---

### `ml_review_prediction.py`

**Algorithm:** XGBoost Regressor — predicts review score (1.0–5.0).

**Features:** delivery metrics, order size, payment type, product category, seller/customer state.

**Performance:** RMSE = **1.14**, R² = **0.21**.

**Output columns in OBT:**

| Column | Type | Description |
|---|---|---|
| `predicted_review_score` | FLOAT | Predicted score rounded to nearest 0.5 |
| `predicted_satisfaction` | VARCHAR | Excellent (≥4.5) / Good (≥3.5) / Average (≥2.5) / Poor |

**Usage:**
```bash
python scripts/ml/ml_review_prediction.py --execute
```

---

### `ml_seller_performance.py`

**Algorithm:** Weighted KPI Composite Score (0–100) + K-Means (k=3) for tier assignment.

**KPI Weights:**

| KPI | Weight |
|---|---|
| `avg_review_score` | 35% |
| `pct_on_time` | 30% |
| `total_revenue` | 20% |
| `total_orders` | 15% |

**Output columns in OBT:**

| Column | Type | Description |
|---|---|---|
| `seller_performance_score` | FLOAT | Composite score 0–100 |
| `seller_tier` | VARCHAR | Top Seller / Average / Underperformer |

**Usage:**
```bash
python scripts/ml/ml_seller_performance.py --execute
```

---

### `run_all_ml.py`

Orchestrator — runs all 5 ML scripts in order and prints a summary table.

```bash
python scripts/ml/run_all_ml.py           # dry-run
python scripts/ml/run_all_ml.py --execute  # train + write to DB
```

**Example output:**
```
======================================================================
  Pipeline Summary
======================================================================
  ✅ OK   K-Means RFM Segmentation        (39.6s)
  ✅ OK   Random Forest Churn             (34.4s)
  ✅ OK   XGBoost Delivery Risk           (12.4s)
  ✅ OK   XGBoost Review Prediction       ( 8.1s)
  ✅ OK   Seller Performance Scoring      ( 3.3s)
  Total runtime: ~100s
======================================================================
```

---

## Full Pipeline Execution

```bash
# 1. Build the OBT
python scripts/ml/create_obt_master.py --execute

# 2. Run all ML models
python scripts/ml/run_all_ml.py --execute

# 3. Export CSV snapshot for Streamlit demo mode
python export_csv.py
```
