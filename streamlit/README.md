# 📊 Streamlit Dashboard Documentation

## Overview

A 4-page premium analytics dashboard built with **Streamlit + Plotly** visualizing the Olist ML outputs from `gold.obt_master`. Features a dark glassmorphism design system with purple-teal gradient aesthetics.

🚀 **Live at:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

---

## Pages

### 📊 Overview (`app.py`)
Business-level KPIs and trends:
- **6 KPI cards:** orders, revenue, avg order value, on-time rate, avg review score, unique customers
- **Orders over time** — dual-axis line chart (orders + revenue)
- **Revenue by state** — horizontal bar chart (top 12 states)
- **Review score distribution** — color-coded bar chart
- **Payment method mix** — donut chart
- **Top product categories** — horizontal bar by revenue

### 👥 Customer Intelligence (`pages/1_Customer_Intelligence.py`)
K-Means RFM segmentation + Random Forest churn risk:
- **5 KPI cards:** customers, avg recency, avg frequency, avg LTV, high-churn count
- **RFM segment pie** — Champions / Loyal / At Risk / Lost/Inactive
- **Segment stats table** — avg order value + review per segment
- **Churn tier bar chart** — High / Medium / Low
- **Churn probability histogram** — distribution of predicted churn probability
- **Revenue by segment + state** — stacked bar (top 8 states)
- **Customer acquisition trend** — monthly new customers area chart

### 🚚 Delivery Analytics (`pages/2_Delivery_Analytics.py`)
XGBoost delay risk prediction + delivery performance:
- **5 KPI cards:** on-time rate, avg delivery days, avg variance, late orders, high-risk count
- **Delay risk score histogram** — colored by tier (High/Medium/Low)
- **Risk tier donut** — pie breakdown
- **On-time rate gauge** — with 90% threshold marker
- **Delivery time histogram** — with mean line overlay
- **Category on-time rates** — horizontal bar (top 12 categories ≥100 orders)
- **Delivery variance over time** — monthly trend area chart
- **Predicted vs actual review scatter** — colored by delay risk tier

### 🏪 Seller Intelligence (`pages/3_Seller_Intelligence.py`)
Weighted KPI scoring + K-Means seller tiers:
- **6 KPI cards:** total sellers, top sellers, avg score, avg revenue/seller, avg review, via marketing
- **Performance tier donut** — Top Seller / Average / Underperformer
- **Score vs Revenue scatter** — sized by order count, colored by tier
- **Revenue by seller state** — bar chart annotated with seller counts
- **Marketing acquisition channels** — horizontal bar (organic search, paid, social, etc.)
- **Top 20 sellers table** — interactive dataframe with all KPIs

---

## File Structure

```
streamlit/
├── app.py                          # Overview page (entry point)
├── requirements.txt                # Streamlit-specific deps
├── assets/
│   └── style.css                   # Dark glassmorphism design system
├── components/
│   ├── db.py                       # DB connection + CSV fallback
│   └── filters.py                  # Sidebar filter widget
├── pages/
│   ├── 1_Customer_Intelligence.py
│   ├── 2_Delivery_Analytics.py
│   └── 3_Seller_Intelligence.py
└── data/                           # Auto-generated CSV snapshots (gitignored)
    └── obt_master.csv
```

---

## Running Locally

```bash
# From project root
pip install -r streamlit/requirements.txt

# Export latest ML results to CSV (for demo mode)
python export_csv.py

# Launch dashboard
streamlit run streamlit/app.py
```

Dashboard opens at **http://localhost:8501**.

---

## Data Architecture

```
gold.obt_master  (SQL Server)
       │
       ├── Direct DB connection (local)  ──► Live data
       └── CSV fallback (Streamlit Cloud) ──► streamlit/data/obt_master.csv
```

The `components/db.py` module tries SQL Server first (5-second timeout). If it fails (e.g., on Streamlit Cloud), it automatically falls back to the CSV snapshot and displays a "Demo Mode" banner.

---

## Design System

**Theme:** Dark glassmorphism with purple-teal gradient

| Token | Value |
|---|---|
| Background | `#0a0e1a` with radial gradient overlays |
| Surface | `#111827` |
| Accent primary | `#8b5cf6` (purple) |
| Accent secondary | `#14b8a6` (teal) |
| Success | `#22c55e` |
| Warning | `#f59e0b` |
| Danger | `#f43f5e` |
| Typography | Inter (body) + Space Grotesk (headings/numbers) |

---

## Deployment (Streamlit Cloud)

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Set **Main file path** to `streamlit/app.py`
4. No secrets needed — the app auto-detects demo mode via CSV fallback
5. Ensure `streamlit/data/obt_master.csv` is committed (re-export via `python export_csv.py`)

> **Note:** CSVs are gitignored by default. To deploy, temporarily remove `*.csv` from `.gitignore`, commit the snapshot, then restore the rule.
