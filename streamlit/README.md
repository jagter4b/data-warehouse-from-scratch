# Olist ML Analytics — Streamlit Dashboard

🚀 **Live Demo:** [https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/](https://data-warehouse-from-scratch-gfmb6jraqdszq6tfzrm38q.streamlit.app/)

A multi-page Streamlit application visualizing the 7 predictive ML models built on the Olist Data Warehouse.  
Reads exclusively from pre-exported CSV snapshots (`data/*.csv`) in cloud mode — zero database required.

---

## Pages

| Page | Tabs | Models |
|:---|:---|:---|
| **Home** | Overview · Model Registry | All 7 |
| **Customer Intelligence** | RFM Segments · Churn Prediction · Lifetime Value | Models 1–3 |
| **Seller Intelligence** | Performance Scoring · Churn Risk | Models 4–5 |
| **Order Intelligence** | Delivery Risk · Review Prediction | Models 6–7 |

---

## Running Locally

```bash
# From the project root
cd streamlit
pip install -r requirements.txt
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Deploying to Streamlit Community Cloud

### Prerequisites
- The code is pushed to a **public GitHub repository** (or a private repo with a connected Streamlit account).
- The `streamlit/data/*.csv` files **must be committed** to the repository (see below).

### Step 1 — Force-commit the CSV data files

The root `.gitignore` excludes `*.csv`. Override this **only for the data folder**:

```bash
# From the project root
git add -f streamlit/data/*.csv
git commit -m "feat: add CSV data snapshots for Streamlit Cloud deployment"
git push
```

> **Why?** Streamlit Cloud has no access to your local SQL Server. The `db.py` loader
> automatically falls back to these CSVs when no DB connection is configured.

### Step 2 — Sign in to Streamlit Cloud

Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.

### Step 3 — Create a new app

Click **"New app"** and fill in:

| Field | Value |
|:---|:---|
| **Repository** | `your-github-username/data-warehouse-from-scratch` |
| **Branch** | `main` |
| **Main file path** | `streamlit/app.py` |
| **App URL** | Choose a custom slug (e.g. `olist-ml-analytics`) |

Click **"Deploy"**.

### Step 4 — No secrets needed

Because the app automatically uses the CSV fallback when no DB host is configured,
**you do not need to add any Streamlit secrets**. The app will work out of the box.

If you ever want to connect a live database (e.g. Azure SQL), add these under  
**Settings → Secrets** in the Streamlit Cloud dashboard:

```toml
DB_HOST = "your-server.database.windows.net"
DB_PORT = "1433"
DB_NAME = "olist_dw"
```

### Step 5 — Done

After the build finishes (~1–2 min), your app is live at:

```
https://<your-slug>.streamlit.app/
```

---

## Refreshing the Data

When you re-run the ML pipeline and want to update the live dashboard:

```bash
# 1. Re-run export (from project root)
python export_csv.py

# 2. Force-add and push
git add -f streamlit/data/*.csv
git commit -m "chore: refresh ML data snapshots"
git push
```

Streamlit Cloud automatically redeploys on every push to `main`.

---

## File Structure

```
streamlit/
├── app.py                        # Home page — KPIs, model registry, nav cards
├── pages/
│   ├── 1_Customer_Intelligence.py
│   ├── 2_Seller_Intelligence.py
│   └── 3_Order_Intelligence.py
├── components/
│   ├── db.py                     # DB loader → CSV fallback
│   ├── charts.py                 # Plotly chart factory (semantic palettes)
│   └── filters.py                # Sidebar helpers
├── assets/
│   └── style.css                 # Premium dark-mode design system
├── data/                         # Pre-exported CSVs (10 files, ~90 MB)
│   ├── obt_customers.csv
│   ├── obt_sellers.csv
│   ├── obt_orders.csv
│   ├── ml_customer_segments.csv
│   ├── ml_churn_predictions.csv
│   ├── ml_clv_predictions.csv
│   ├── ml_seller_scores.csv
│   ├── ml_seller_churn.csv
│   ├── ml_delivery_risk.csv
│   └── ml_review_predictions.csv
├── requirements.txt              # Streamlit Cloud dependencies
└── .streamlit/
    └── config.toml               # Dark theme configuration
```
