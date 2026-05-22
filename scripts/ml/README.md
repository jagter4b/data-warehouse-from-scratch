# ML Pipeline Documentation
## Olist Data Warehouse — Machine Learning Layer

### 1. Overview
The Machine Learning (ML) layer transforms the Data Warehouse from a descriptive reporting system into a predictive engine. Sitting atop the Medallion Architecture (Bronze → Silver → Gold), the ML layer consumes highly normalized analytical data from the Gold layer, flattens it into One Big Tables (OBTs), and runs predictive models.

**Architecture Integration:**
1. **Bronze**: Raw JSON/CSV extraction.
2. **Silver**: Cleaned, typed, and deduped tables.
3. **Gold**: Kimball-style Star/Galaxy schemas for Power BI.
4. **ML**: Flattens Gold dimensional data into One Big Tables (OBTs) for predictive modeling.

**Resulting Assets:**
- **3 OBTs**: `gold.obt_customers`, `gold.obt_sellers`, `gold.obt_orders`
- **7 ML Result Tables**: e.g., `gold.ml_customer_segments`, `gold.ml_churn_predictions`, etc.

**Tech Stack:**
- **Python** (Core execution environment)
- **XGBoost & scikit-learn** (Model training)
- **pandas** (Data manipulation and feature engineering)
- **sqlalchemy & pyodbc** (Database connection and ORM)
- **imbalanced-learn** (SMOTE for class imbalance)

---

### 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph Gold Layer (Data Warehouse)
        C_DIM[dim_customer]
        S_DIM[dim_seller]
        P_DIM[dim_product]
        O_DIM[dim_order_status]
        D_DIM[dim_date]
        F_ORD[fact_order_items]
        F_LFC[fact_order_life_cycle]
        F_REV[fact_reviews]
    end

    subgraph OBTs (One Big Tables)
        OBT_C[(gold.obt_customers)]
        OBT_S[(gold.obt_sellers)]
        OBT_O[(gold.obt_orders)]
    end

    C_DIM --> OBT_C
    F_ORD --> OBT_C
    F_REV --> OBT_C

    S_DIM --> OBT_S
    F_ORD --> OBT_S
    
    C_DIM --> OBT_O
    S_DIM --> OBT_O
    F_LFC --> OBT_O

    subgraph ML Scripts
        M1[RFM Segmentation]
        M2[Customer Churn]
        M3[Customer LTV]
        M4[Seller Scoring]
        M5[Seller Churn]
        M6[Delivery Risk]
        M7[Review Prediction]
    end

    OBT_C --> M1
    OBT_C --> M2
    OBT_C --> M3

    OBT_S --> M4
    OBT_S --> M5
    OBT_O -.-> M5

    OBT_O --> M6
    OBT_O --> M7

    subgraph ML Results (Gold Layer)
        R1[(gold.ml_customer_segments)]
        R2[(gold.ml_churn_predictions)]
        R3[(gold.ml_clv_predictions)]
        R4[(gold.ml_seller_scores)]
        R5[(gold.ml_seller_churn)]
        R6[(gold.ml_delivery_risk)]
        R7[(gold.ml_review_predictions)]
    end

    M1 --> R1
    M2 --> R2
    M3 --> R3
    M4 --> R4
    M5 --> R5
    M6 --> R6
    M7 --> R7
```

---

### 3. One Big Tables (OBTs)

#### 3.1 gold.obt_customers
- **Purpose**: A flattened table for all customer-centric metrics, enabling lifetime value, churn, and behavioral clustering models.
- **Grain**: One row = one unique customer (`customer_unique_id`).
- **Source tables joined**: `dim_customer`, `fact_payments`, `fact_order_items`, `dim_product`, `fact_order_life_cycle`, `dim_date`, `fact_reviews`, `review_comments`, `fact_marketing_funnel`, `dim_marketing_channel`.
- **Row count**: 96,097
- **How to refresh**: `python scripts/ml/create_obt_customers.py --execute`

| Column Name | Data Type |
| :--- | :--- |
| `customer_unique_id` | varchar |
| `customer_city` | varchar |
| `customer_state` | char |
| `total_spend` | decimal |
| `avg_order_value` | decimal |
| `max_order_value` | decimal |
| `total_freight_paid` | decimal |
| `avg_installments` | float |
| `preferred_payment_type` | varchar |
| `total_orders` | int |
| `total_items_bought` | int |
| `total_distinct_products` | int |
| `avg_items_per_order` | float |
| `distinct_months_active` | int |
| `first_order_date` | date |
| `last_order_date` | date |
| `customer_tenure_days` | int |
| `days_since_last_order` | int |
| `distinct_categories_bought` | int |
| `top_category` | varchar |
| `avg_days_to_deliver` | float |
| `avg_days_to_approve` | float |
| `pct_late_deliveries` | float |
| `total_late_orders` | int |
| `avg_review_score` | float |
| `total_reviews` | int |
| `pct_1star_reviews` | float |
| `pct_5star_reviews` | float |
| `has_written_review` | int |
| `total_distinct_sellers` | int |
| `any_seller_from_mql` | int |
| `mql_acquisition_channel` | varchar |

#### 3.2 gold.obt_sellers
- **Purpose**: A flattened table for seller performance tracking, scoring, and retention analysis.
- **Grain**: One row = one unique seller (`seller_id`).
- **Source tables joined**: `dim_seller`, `fact_order_items`, `dim_product`, `fact_order_life_cycle`, `dim_date`, `fact_reviews`, `fact_marketing_funnel`.
- **Row count**: 3,096
- **How to refresh**: `python scripts/ml/create_obt_sellers.py --execute`

| Column Name | Data Type |
| :--- | :--- |
| `seller_id` | varchar |
| `seller_city` | varchar |
| `seller_state` | char |
| `total_orders_fulfilled` | int |
| `total_revenue` | decimal |
| `avg_order_value` | decimal |
| `total_items_sold` | int |
| `total_distinct_products_sold` | int |
| `total_distinct_customers_served` | int |
| `total_freight_value` | decimal |
| `avg_days_to_deliver` | float |
| `avg_days_to_approve` | float |
| `pct_late_deliveries` | float |
| `total_late_orders` | int |
| `avg_review_score` | float |
| `total_reviews_received` | int |
| `pct_1star_reviews` | float |
| `pct_5star_reviews` | float |
| `distinct_categories_sold` | int |
| `top_category` | varchar |
| `was_acquired_via_mql` | int |
| `mql_origin` | varchar |
| `business_type` | varchar |
| `lead_type` | varchar |
| `lead_behaviour_profile` | varchar |
| `average_stock` | varchar |
| `declared_monthly_revenue` | decimal |
| `declared_product_catalog_size` | decimal |
| `has_company` | int |
| `has_gtin` | int |
| `days_to_close_deal` | int |

#### 3.3 gold.obt_orders
- **Purpose**: A flattened table for order-level operations such as predicting delays and forecasting customer satisfaction upon delivery.
- **Grain**: One row = one unique order (`order_id`).
- **Source tables joined**: `dim_customer`, `dim_seller`, `dim_product`, `dim_order_status`, `dim_payment_type`, `dim_date`, `fact_order_items`, `fact_order_life_cycle`, `fact_payments`, `fact_reviews`.
- **Row count**: 99,441
- **How to refresh**: `python scripts/ml/create_obt_orders.py --execute`

| Column Name | Data Type |
| :--- | :--- |
| `order_id` | varchar |
| `customer_id` | int |
| `customer_unique_id` | varchar |
| `seller_id` | varchar |
| `order_status` | varchar |
| `total_order_value` | decimal |
| `total_freight_value` | decimal |
| `total_payment_value` | decimal |
| `total_items` | int |
| `total_distinct_products` | int |
| `payment_installments` | int |
| `preferred_payment_type` | varchar |
| `primary_category` | varchar |
| `distinct_categories` | int |
| `avg_product_weight_g` | float |
| `avg_product_photos_qty` | float |
| `purchase_date` | date |
| `approval_date` | date |
| `carrier_date` | date |
| `delivered_date` | date |
| `estimated_date` | date |
| `purchase_year` | smallint |
| `purchase_month` | tinyint |
| `purchase_quarter` | tinyint |
| `purchase_day_of_week` | tinyint |
| `days_to_approve` | int |
| `days_to_carrier` | int |
| `days_to_deliver` | int |
| `c_scheduled_vs_actual_days` | int |
| `is_late` | int |
| `review_score` | float |
| `has_review` | int |
| `has_written_comment` | int |
| `seller_avg_review_score` | float |
| `seller_pct_late_deliveries` | float |
| `seller_was_acquired_via_mql` | int |
| `seller_total_orders_fulfilled` | int |

---

### 4. ML Models

#### 4.1 RFM Segmentation (K-Means Clustering)
- **Business Purpose**: Segments customers based on Recency, Frequency, and Monetary value to tailor marketing strategies.
- **Source OBT**: `gold.obt_customers`
- **Algorithm**: K-Means Clustering (`k=4`)
- **Features Used**:
  - `recency_score`: Quintile bin (1-5) based on days since last order.
  - `frequency_score`: Quintile bin (1-5) based on total orders.
  - `monetary_score`: Quintile bin (1-5) based on total spend.
- **Methodology**: RFM scoring methodology utilizes pandas `qcut` to assign 1-5 quintiles. The sum defines the total RFM score.
- **Cluster Labels**: `Champions` / `Loyal Customers` / `At Risk` / `Lost/Inactive`
- **Output Table**: `gold.ml_customer_segments`
- **Output Columns**: 
  - `customer_unique_id` (varchar)
  - `rfm_recency_score` (bigint)
  - `rfm_frequency_score` (bigint)
  - `rfm_monetary_score` (bigint)
  - `rfm_total_score` (bigint)
  - `cluster_id` (int)
  - `segment_label` (varchar)
  - `scored_at` (datetime)
- **Performance Metric**: Silhouette Score = 0.4788
- **How to retrain and refresh**: `python scripts/ml/ml_customer_segments.py --execute`

#### 4.2 Customer Churn Prediction (Random Forest)
- **Business Purpose**: Identifies customers highly likely to abandon the platform, allowing targeted retention campaigns.
- **Source OBT**: `gold.obt_customers`
- **Algorithm**: Random Forest Classifier
- **Churn Definition**: `days_since_last_order > 120` (anchored dynamically to max global dataset timestamp).
- **Features Used**: `total_orders`, `total_spend`, `avg_order_value`, `avg_review_score`, `pct_late_deliveries`, `customer_tenure_days`, `avg_installments`, `distinct_categories_bought`, `pct_1star_reviews`, `any_seller_from_mql`
- **Class Imbalance Handling**: SMOTE (Balanced from 64k vs 12k to 64k vs 64k).
- **Churn Threshold Logic**: `High` (>0.7), `Medium` (0.4-0.7), `Low` (<0.4).
- **Output Table**: `gold.ml_churn_predictions`
- **Output Columns**: 
  - `customer_unique_id` (varchar)
  - `churn_probability` (real)
  - `churn_predicted` (bigint)
  - `risk_tier` (varchar)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metrics**: AUC-ROC = 0.6829
- **Top Predictor**: `total_spend`
- **How to retrain and refresh**: `python scripts/ml/ml_churn_predictions.py --execute`

#### 4.3 Customer LTV Prediction (XGBoost Regressor)
- **Business Purpose**: Predicts the total lifetime monetary value of a customer to guide acquisition budgets (CAC vs LTV).
- **Source OBT**: `gold.obt_customers`
- **Algorithm**: XGBoost Regressor
- **Target Variable**: `total_spend`
- **Features Used**: `total_orders`, `customer_tenure_days`, `distinct_months_active`, `avg_installments`, `distinct_categories_bought`, `pct_late_deliveries`, `avg_review_score`, `any_seller_from_mql`. *(Note: `avg_order_value` and `max_order_value` explicitly excluded to prevent data leakage).*
- **CLV Tier Methodology**: `Platinum` (top 10%), `Gold` (10-30%), `Silver` (30-60%), `Bronze` (bottom 40%).
- **Output Table**: `gold.ml_clv_predictions`
- **Output Columns**:
  - `customer_unique_id` (varchar)
  - `predicted_clv` (real)
  - `clv_tier` (varchar)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metrics**: R² = 0.1710, RMSE ~130 BRL.
- **Note on R²**: CLV prediction is inherently difficult due to chaotic consumer behavior; an R² of 0.17 is honest, realistic, and completely devoid of synthetic target leakage.
- **Top Predictors**: `avg_installments`, `total_orders`
- **How to retrain and refresh**: `python scripts/ml/ml_clv_predictions.py --execute`

#### 4.4 Seller Performance Scoring (K-Means)
- **Business Purpose**: Identifies underperforming sellers for auditing and highlights top performers for promotional algorithms.
- **Source OBT**: `gold.obt_sellers`
- **Algorithm**: Weighted Composite Scoring + K-Means (`k=3`)
- **Composite Score Methodology**: 
  - 40% `avg_review_score` (normalized)
  - 30% `pct_on_time`
  - 20% `total_revenue` (log-scaled)
  - 10% `pct_5star_reviews`
- **Cluster Labels**: `Top Performer`, `Average Seller`, `Underperformer`
- **Output Table**: `gold.ml_seller_scores`
- **Output Columns**:
  - `seller_id` (varchar)
  - `composite_score` (float)
  - `performance_tier` (varchar)
  - `cluster_id` (int)
  - `cluster_label` (varchar)
  - `avg_review_score` (float)
  - `pct_late_deliveries` (float)
  - `total_revenue` (float)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metric**: Silhouette Score = 0.5679
- **How to retrain and refresh**: `python scripts/ml/ml_seller_scores.py --execute`

#### 4.5 Seller Churn Risk (XGBoost Classifier)
- **Business Purpose**: Predicts the probability of a seller ceasing operations or migrating off the platform.
- **Source OBT**: `gold.obt_sellers` + `gold.obt_orders`
- **Algorithm**: XGBoost Classifier
- **Churn Definition**: No fulfilled orders in the last 180 days (anchored to max global timestamp in dataset, not `GETDATE()`, due to 2018 data drift).
- **Features Used**: `total_orders_fulfilled`, `total_revenue`, `avg_review_score`, `pct_late_deliveries`, `avg_days_to_deliver`, `distinct_categories_sold`, `total_distinct_customers_served`, `was_acquired_via_mql`, `declared_monthly_revenue`, `has_company`, `has_gtin`.
- **Class Imbalance Handling**: Dynamic SMOTE (Automatically adjusts `k_neighbors` to account for exceptionally small minority class bounds).
- **Output Table**: `gold.ml_seller_churn`
- **Output Columns**:
  - `seller_id` (varchar)
  - `churn_probability` (real)
  - `churn_predicted` (bigint)
  - `risk_tier` (varchar)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metric**: AUC-ROC = 0.7846
- **Rows scored**: 3,096 (all sellers)
- **How to retrain and refresh**: `python scripts/ml/ml_seller_churn.py --execute`

#### 4.6 Delivery Delay Risk (XGBoost Classifier)
- **Business Purpose**: Predicts whether an order will miss its estimated delivery date before it ships.
- **Source OBT**: `gold.obt_orders`
- **Algorithm**: XGBoost Classifier
- **Target**: `is_late = 1`
- **Features Used**: `total_order_value`, `total_items`, `total_distinct_products`, `avg_product_weight_g`, `payment_installments`, `days_to_approve`, `seller_avg_review_score`, `seller_pct_late_deliveries`, `purchase_day_of_week`, `purchase_month`, `distinct_categories`, and the label encoded `primary_category_encoded`.
- **Class Imbalance Handling**: SMOTE
- **Risk Tier Logic**: `High` (>0.7), `Medium` (0.4-0.7), `Low` (<0.4).
- **Output Table**: `gold.ml_delivery_risk`
- **Output Columns**:
  - `order_id` (varchar)
  - `delay_probability` (real)
  - `delay_predicted` (bigint)
  - `risk_tier` (varchar)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metric**: AUC-ROC = 0.7483
- **Rows Scored**: 98,651
- **How to retrain and refresh**: `python scripts/ml/ml_delivery_risk.py --execute`

#### 4.7 Review Score Prediction (XGBoost Regressor)
- **Business Purpose**: Forecasts the expected customer satisfaction (1-5 stars) upon order completion.
- **Source OBT**: `gold.obt_orders`
- **Algorithm**: XGBoost Regressor
- **Target**: `review_score` (1-5)
- **Features Used**: `c_scheduled_vs_actual_days`, `is_late`, `total_items`, `total_freight_value`, `total_order_value`, `payment_installments`.
- **Satisfaction Tier Methodology**: `Excellent` (4.5-5), `Good` (3.5-4.5), `Poor` (2.5-3.5), `Very Poor` (<2.5).
- **Output Table**: `gold.ml_review_predictions`
- **Output Columns**:
  - `order_id` (varchar)
  - `predicted_review_score` (real)
  - `satisfaction_tier` (varchar)
  - `model_version` (varchar)
  - `scored_at` (datetime)
- **Performance Metric**: RMSE = 1.1311
- **Note**: Predictions rounded to nearest 0.5
- **Rows Scored**: 96,460
- **How to retrain and refresh**: `python scripts/ml/ml_review_predictions.py --execute`

---

### 5. Result Tables Reference

| Table Name | Grain | Rows | Key Metric | Value | Refresh Script |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gold.ml_customer_segments` | Customer | 96,097 | Silhouette | 0.4788 | `ml_customer_segments.py` |
| `gold.ml_churn_predictions` | Customer | 96,096 | AUC-ROC | 0.6829 | `ml_churn_predictions.py` |
| `gold.ml_clv_predictions` | Customer | 95,135 | R² Score | 0.1710 | `ml_clv_predictions.py` |
| `gold.ml_seller_scores` | Seller | 3,096 | Silhouette | 0.5679 | `ml_seller_scores.py` |
| `gold.ml_seller_churn` | Seller | 3,096 | AUC-ROC | 0.7846 | `ml_seller_churn.py` |
| `gold.ml_delivery_risk` | Order | 98,651 | AUC-ROC | 0.7483 | `ml_delivery_risk.py` |
| `gold.ml_review_predictions` | Order | 96,460 | RMSE | 1.1311 | `ml_review_predictions.py` |

---

### 6. Safety & Data Governance

- **Read-Only Tables**: All foundational dimensional tables and fact tables in the `gold` schema are strictly read-only within the ML environment.
- **Write Tables**: Execution is strictly limited to the creation and truncation/population of the 3 OBTs and the 7 `ml_` prefixed result tables in the `gold` schema.
- **Transaction Safety**: Every ML Python script utilizes the exact same Idempotent Transaction Pattern:
  ```sql
  BEGIN TRY
      BEGIN TRAN;
      TRUNCATE TABLE gold.[target_table];
      -- Bulk Insert via Pandas / SQL
      COMMIT TRAN;
  END TRY
  BEGIN CATCH
      ROLLBACK TRAN;
  END CATCH
  ```
- **Execution Flags**: All scripts are dry-run by default. They simply query the data in memory, run standard ML diagnostic printing (e.g. `print(roc_auc_score())`), and exit. To commit to the database, you must explicitly invoke the `--execute` flag.

---

### 7. Full Refresh Order

To rebuild the entire ML Pipeline (e.g., as part of an Airflow DAG) from scratch, run the following sequence:

Step 1: `python scripts/ml/create_obt_customers.py --execute`
Step 2: `python scripts/ml/create_obt_sellers.py --execute`
Step 3: `python scripts/ml/create_obt_orders.py --execute`
Step 4: `python scripts/ml/ml_customer_segments.py --execute`
Step 5: `python scripts/ml/ml_churn_predictions.py --execute`
Step 6: `python scripts/ml/ml_clv_predictions.py --execute`
Step 7: `python scripts/ml/ml_seller_scores.py --execute`
Step 8: `python scripts/ml/ml_seller_churn.py --execute`
Step 9: `python scripts/ml/ml_delivery_risk.py --execute`
Step 10: `python scripts/ml/ml_review_predictions.py --execute`

---

### 8. Known Limitations
- Dataset is from 2018 — churn anchored to max timestamp not current date.
- Customer LTV R² = 0.17 is intentionally honest — leakage features were removed.
- Review prediction RMSE = 1.1311 — acceptable given the subjectivity of review scores.
- Seller churn model covers all 3,096 sellers including non-MQL sellers.

---

### 9. Streamlit App Integration
The 7 ML result tables are the primary data source for the Streamlit dashboard. The app connects read-only to the Gold layer and visualizes predictions across three domains:
- **Customer Intelligence** (Segments, Churn, CLV)
- **Seller Intelligence** (Performance, Churn Risk)
- **Order Intelligence** (Delivery Risk, Review Prediction)

**Streamlit app location:** `streamlit/app.py`
**To run locally:** `streamlit run streamlit/app.py`
