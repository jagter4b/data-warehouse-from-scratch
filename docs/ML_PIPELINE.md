# 🤖 Machine Learning Pipeline Documentation

## Overview

The ML pipeline trains **7 predictive models** across three domains (Customer, Seller, Order) and writes scored predictions back into the Gold schema. All models are trained on the `gold.obt_master` One Big Table feature store and all scripts support a `--dry-run` mode (default) for safe testing.

---

## Architecture

```
gold layer (dims + facts)
        │
        ▼
create_obt_master.py  ──►  gold.obt_master  (99,441 rows, 47 columns)
                                   │
              ┌────────────────────┼──────────────────────────┐
              │                    │                           │
              ▼                    ▼                           ▼
Customer Models           Order Models               Seller Models
ml_customer_segments   ml_delivery_risk        ml_seller_performance
ml_churn_prediction    ml_review_prediction
              │                    │                           │
              └────────────────────▼───────────────────────────┘
                          gold.obt_master
                    (ML columns updated in-place)
```

---

## Model Summary Table

| Domain | Model | Script | Algorithm | Target | Performance |
|--------|-------|--------|-----------|--------|-------------|
| **Customer** | RFM Segmentation | `ml_customer_segments.py` | K-Means (k=4) | `customer_segment` | Silhouette: **0.4788** |
| **Customer** | Churn Prediction | `ml_churn_prediction.py` | Random Forest + SMOTE | `churn_risk_tier` | AUC-ROC: **0.6829** |
| **Customer** | Lifetime Value | `ml_ltv_prediction.py` | XGBoost Regressor | `ltv_segment` | R²: **0.1710** |
| **Seller** | Performance Scoring | `ml_seller_performance.py` | Weighted KPI + K-Means | `seller_tier` | Silhouette: **0.5679** |
| **Seller** | Churn Risk | `ml_seller_churn.py` | XGBoost + Dynamic SMOTE | `seller_churn_probability` | AUC-ROC: **0.7846** |
| **Order** | Delivery Risk | `ml_delivery_risk.py` | XGBoost Binary Classifier | `delay_risk_tier` | AUC-ROC: **0.7483** |
| **Order** | Review Prediction | `ml_review_prediction.py` | XGBoost Regressor | `predicted_review_score` | RMSE: **1.1311** |

---

## Feature Store: `gold.obt_master`

**Script:** `create_obt_master.py`  
**Grain:** One row per order (`order_id` is the primary key)  
**Rows:** 99,441 | **Columns:** 47 (base) + ML output columns

### Column Groups

| Group | Columns |
|-------|---------|
| Order | `order_id`, `purchase_date`, `purchase_year/month/day_of_week`, `order_status` |
| Customer | `customer_unique_id`, `customer_state`, `customer_city` |
| Delivery | `days_to_approve`, `days_to_ship`, `days_to_deliver`, `days_delivery_variance`, `is_delivered_on_time` |
| Value | `total_items`, `total_order_value`, `total_freight_value`, `total_payment_value` |
| Payment | `payment_type`, `payment_installments` |
| Product | `product_category_name` |
| Seller | `seller_id`, `seller_state`, `seller_city` |
| Review | `review_score` |
| Marketing | `marketing_origin`, `days_to_close`, `business_segment`, `lead_type`, `business_type` |
| ML Outputs | All columns added by ML scripts (see below) |

---

## Model Details

### 1. 👥 Customer RFM Segmentation (`ml_customer_segments.py`)

**Algorithm:** K-Means (k=4, StandardScaler)  
**Anchor date:** 2018-10-17 (maximum transaction date in dataset)

**RFM Features:**

| Feature | Transformation | Description |
|---------|---------------|-------------|
| Recency | Days since last purchase | Lower = more recent = better |
| Frequency | Count of orders | Higher = more loyal |
| Monetary | Total spend | Log-transformed (log1p) to handle skew |

**Segments:**

| Segment | Description | Characteristics |
|---------|-------------|-----------------|
| Champions | Best customers | Low recency, high freq & monetary |
| Loyal Customers | Regular buyers | Moderate recency and frequency |
| At Risk | Slipping away | Increasing recency, were active before |
| Lost/Inactive | Churned | Very high recency, low activity |

**Output columns added to OBT:**

| Column | Type | Description |
|--------|------|-------------|
| `recency_days` | INT | Days since last purchase |
| `frequency_orders` | INT | Total orders per customer |
| `monetary_total` | DECIMAL | Total lifetime spend |
| `customer_segment` | VARCHAR | Champions / Loyal / At Risk / Lost/Inactive |

---

### 2. 📉 Customer Churn Prediction (`ml_churn_prediction.py`)

**Algorithm:** Random Forest Classifier (200 trees, `class_weight='balanced'`)  
**Churn definition:** Customer whose last purchase was >180 days before anchor date (2018-10-17)

**Features used for training:**
- `frequency_orders`, `monetary_total`, `avg_order_value`
- `avg_review_score`, `pct_on_time`
- `avg_days_deliver`, `avg_variance`

> ⚠️ **`recency_days` is deliberately excluded** — it directly defines the churn label and would cause data leakage (target leakage).

**SMOTE:** Applied to handle class imbalance in the training set.

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `churn_probability` | FLOAT | Probability of churn (0.0–1.0) |
| `churn_risk_tier` | VARCHAR | High (≥0.6) / Medium (0.3–0.6) / Low (<0.3) |

---

### 3. 💰 Customer Lifetime Value (`ml_ltv_prediction.py`)

**Algorithm:** XGBoost Regressor  
**Target:** Log-transformed total spend binned into 4 LTV tiers

**Important — Data Leakage Note:**
> Initial models showed R² = 0.9982 due to target leakage (direct derivations of total spend like `avg_order_value` were used as features). After removing all columns that directly derive from the target, R² dropped to an honest **0.1710**, which reflects a production-realistic model.

**Leakage-safe features used:**
- Recency, frequency, avg delivery days, avg review score
- Payment installments, on-time rate, product category diversity

**LTV Tiers:**

| Tier | Description |
|------|-------------|
| Platinum | Top 10% spenders |
| Gold | 10–30% |
| Silver | 30–60% |
| Bronze | Bottom 40% |

---

### 4. 🏪 Seller Performance Scoring (`ml_seller_performance.py`)

**Algorithm:** Weighted KPI Composite Score (0–100) + K-Means (k=3) for tier assignment  
**Grain:** Seller-level (aggregated from order data)

**KPI Weights:**

| KPI | Weight | Rationale |
|-----|--------|-----------|
| `avg_review_score` | 35% | Customer satisfaction is the top priority |
| `pct_on_time` | 30% | Delivery reliability |
| `total_revenue` | 20% | Business contribution |
| `total_orders` | 15% | Volume/activity |

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `seller_performance_score` | FLOAT | Composite score 0–100 |
| `seller_tier` | VARCHAR | Top Seller / Average / Underperformer |

---

### 5. 🚚 Delivery Risk Prediction (`ml_delivery_risk.py`)

**Algorithm:** XGBoost Binary Classifier  
**Target:** `is_delivered_on_time = 0` (i.e., predicts delay)  
**Class imbalance:** 6.8% late orders → handled via `scale_pos_weight`

**Features:**
- Order size (`total_items`, `total_order_value`)
- Payment installments
- Purchase month and day of week
- Product category (encoded)
- Seller state, customer state (encoded)
- `days_to_approve`, `days_to_ship`

**Risk Tiers:**

| Tier | Threshold | Interpretation |
|------|-----------|----------------|
| High | ≥ 0.40 | Strong likelihood of delay |
| Medium | 0.20–0.40 | Monitor closely |
| Low | < 0.20 | Low delay risk |

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `delay_risk_score` | FLOAT | Probability of delay (0.0–1.0) |
| `delay_risk_tier` | VARCHAR | High / Medium / Low |

---

### 6. ⭐ Review Score Prediction (`ml_review_prediction.py`)

**Algorithm:** XGBoost Regressor  
**Target:** `review_score` (1.0–5.0 continuous)

**Features:**
- Delivery metrics (`days_to_deliver`, `days_delivery_variance`, `is_delivered_on_time`)
- Order size, payment type, product category
- Seller state, customer state

**Score Interpretation:**

| Predicted Score | Satisfaction Label |
|----------------|-------------------|
| ≥ 4.5 | Excellent |
| ≥ 3.5 | Good |
| ≥ 2.5 | Average |
| < 2.5 | Poor |

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `predicted_review_score` | FLOAT | Predicted score (rounded to nearest 0.5) |
| `predicted_satisfaction` | VARCHAR | Excellent / Good / Average / Poor |

---

## Running the Pipeline

### All models at once

```bash
# Dry run (no DB writes) — default
python scripts/ml/run_all_ml.py

# Full execution
python scripts/ml/run_all_ml.py --execute
```

### Individual scripts

```bash
python scripts/ml/create_obt_master.py --execute
python scripts/ml/ml_customer_segments.py --execute
python scripts/ml/ml_churn_prediction.py --execute
python scripts/ml/ml_delivery_risk.py --execute
python scripts/ml/ml_review_prediction.py --execute
python scripts/ml/ml_seller_performance.py --execute
```

---

## Design Decisions

### Why a single OBT instead of separate feature tables?

The OBT pattern simplifies the ML pipeline by:
1. Avoiding complex multi-table joins in every ML script
2. Ensuring consistent feature engineering across all models
3. Making it easy to add new models without changing the data layer

### Why `--execute` flag pattern?

All scripts support dry-run mode by default (no `--execute`). This lets you:
- Test the training pipeline without risk
- Inspect model performance metrics before committing results to the database
- Run in CI/CD environments safely

### Idempotency strategy

All ML scripts use `TRUNCATE + INSERT` (not UPDATE) when writing predictions:
```python
# In each ML script:
conn.execute(text("TRUNCATE TABLE gold.obt_master_ml_predictions"))
df_results.to_sql("obt_master_ml_predictions", conn, schema="gold", if_exists="append", index=False)
```

This makes every run fully reproducible regardless of previous state.
