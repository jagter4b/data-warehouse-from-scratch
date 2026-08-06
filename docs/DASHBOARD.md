# 📊 Streamlit Dashboard — Technical Reference

## Overview

A premium 4-page analytics dashboard built with Streamlit + Plotly that visualizes the Olist ML model outputs. Features a dark glassmorphism design system and a **Demo Mode** that works on Streamlit Cloud without a live SQL Server connection.

🚀 **Live:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

---

## Pages

### 🏠 Overview (`app.py`)

**Data source:** `gold.obt_master` aggregated

**Metrics displayed:**
- 6 KPI cards: Total Orders, Total Revenue, Avg Order Value, On-Time Rate, Avg Review Score, Unique Customers
- Orders & Revenue over time (dual-axis line chart)
- Revenue by state (top 12 states, horizontal bar)
- Review score distribution (color-coded bar chart)
- Payment method mix (donut chart)
- Top product categories by revenue (horizontal bar)

---

### 👥 Customer Intelligence (`pages/1_Customer_Intelligence.py`)

**Models visualized:** K-Means RFM Segmentation + Random Forest Churn

**Metrics displayed:**
- 5 KPI cards: Total Customers, Avg Recency (days), Avg Frequency, Avg LTV, High-Churn Count
- RFM Segment Pie: Champions / Loyal / At Risk / Lost/Inactive
- Segment Stats Table: avg order value + review score per segment
- Churn Tier Bar: High / Medium / Low risk counts
- Churn Probability Histogram: distribution curve
- Revenue by Segment + State: stacked bar (top 8 states)
- Customer Acquisition Trend: monthly new customers area chart

**Sidebar filters:** Date range, Customer segment, Churn risk tier

---

### 🚚 Delivery Analytics (`pages/2_Delivery_Analytics.py`)

**Models visualized:** XGBoost Delivery Risk + XGBoost Review Prediction

**Metrics displayed:**
- 5 KPI cards: On-Time Rate, Avg Delivery Days, Avg Variance, Late Orders, High-Risk Count
- Delay Risk Score Histogram (colored by tier)
- Risk Tier Donut: High / Medium / Low breakdown
- On-Time Rate Gauge (with 90% threshold marker)
- Delivery Time Histogram (with mean line overlay)
- Category On-Time Rates: horizontal bar (top 12 categories with ≥100 orders)
- Delivery Variance Over Time: monthly trend area chart
- Predicted vs Actual Review Scatter (colored by delay risk tier)

**Sidebar filters:** Date range, Delay risk tier

---

### 🏪 Seller Intelligence (`pages/3_Seller_Intelligence.py`)

**Models visualized:** Weighted KPI Scoring + K-Means Seller Tiers

**Metrics displayed:**
- 6 KPI cards: Total Sellers, Top Sellers, Avg Score, Avg Revenue/Seller, Avg Review, Via Marketing
- Performance Tier Donut: Top Seller / Average / Underperformer
- Score vs Revenue Scatter (bubble sized by order count, colored by tier)
- Revenue by Seller State: annotated bar chart
- Marketing Acquisition Channels: horizontal bar
- Top 20 Sellers: interactive Streamlit dataframe with all KPIs

**Sidebar filters:** Seller tier, State

---

## File Structure

```
streamlit/
├── app.py                          ← Overview page + entry point
├── requirements.txt                ← Streamlit-specific dependencies
├── README.md                       ← Quick start guide
├── assets/
│   └── style.css                   ← Dark glassmorphism design system
├── components/
│   ├── db.py                       ← DB connection + CSV fallback logic
│   └── filters.py                  ← Sidebar filter widgets
├── pages/
│   ├── 1_Customer_Intelligence.py
│   ├── 2_Delivery_Analytics.py
│   └── 3_Seller_Intelligence.py
└── data/                           ← Auto-generated CSV snapshots (gitignored)
    └── obt_master.csv
```

---

## Data Architecture

```
gold.obt_master (SQL Server)
       │
       ├── Direct DB connection  ──► Live data (local development)
       └── CSV fallback          ──► streamlit/data/obt_master.csv (Streamlit Cloud)
```

### Demo Mode (CSV Fallback)

`components/db.py` tries to connect to SQL Server with a 5-second timeout. If this fails (e.g., on Streamlit Cloud which has no SQL Server), it:

1. Catches the connection error silently
2. Falls back to reading `streamlit/data/obt_master.csv`
3. Displays a blue "📊 Demo Mode — Using static data snapshot" banner

This means the app can be deployed publicly without exposing database credentials.

---

## Design System

**Theme:** Dark glassmorphism with purple-teal gradient accents

### Color Tokens (`assets/style.css`)

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0a0e1a` | Page background |
| Surface | `#111827` | Card backgrounds |
| Border | `rgba(139,92,246,0.2)` | Card borders |
| Accent Primary | `#8b5cf6` | Purple — primary actions, highlights |
| Accent Secondary | `#14b8a6` | Teal — secondary metrics |
| Success | `#22c55e` | Green — positive indicators |
| Warning | `#f59e0b` | Amber — caution states |
| Danger | `#f43f5e` | Rose — alerts, errors |
| Text Primary | `#e2e8f0` | Main text |
| Text Secondary | `#94a3b8` | Subtitles, metadata |

### Typography

| Element | Font | Weight |
|---------|------|--------|
| Body | Inter | 400, 500 |
| Headings/Numbers | Space Grotesk | 600, 700 |

Both fonts loaded from Google Fonts CDN.

### Glass Cards

Cards use the glassmorphism pattern:
```css
.glass-card {
    background: rgba(17, 24, 39, 0.8);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 16px;
}
```

---

## Components

### `components/db.py`

**`load_data()`** — Main data loading function:
1. Attempts SQL Server connection via SQLAlchemy
2. Executes `SELECT * FROM gold.obt_master`
3. On failure, reads `streamlit/data/obt_master.csv`
4. Returns `(DataFrame, is_demo_mode)`

**`get_db_engine()`** — Returns SQLAlchemy engine using `.env` credentials.

---

### `components/filters.py`

**`render_sidebar_filters(df)`** — Renders sidebar filter widgets and returns a filtered DataFrame. Filter types vary by page:

- Date range picker (min/max from data)
- Multi-select dropdowns (customer_segment, delay_risk_tier, seller_tier, etc.)
- State selector
- "Reset Filters" button

All filters use Streamlit session state for persistence across page navigation.

---

## Running Locally

```bash
# Install dependencies (from project root)
pip install -r streamlit/requirements.txt

# Export latest ML results to CSV for demo mode
python export_csv.py

# Launch dashboard
streamlit run streamlit/app.py
```

Dashboard opens at **http://localhost:8501**.

---

## Deploying to Streamlit Cloud

1. Push repository to GitHub (including `streamlit/data/obt_master.csv`)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path** to `streamlit/app.py`
5. No secrets required — app auto-detects Demo Mode via CSV fallback
6. Click **Deploy**

> **Note:** `*.csv` is in `.gitignore` by default. Before deploying, temporarily remove that rule, commit the CSV snapshot (`git add -f streamlit/data/obt_master.csv`), then restore the rule after deployment.

---

## Dependencies (`streamlit/requirements.txt`)

```
streamlit
plotly
pandas
sqlalchemy
pyodbc
python-dotenv
openpyxl
```
