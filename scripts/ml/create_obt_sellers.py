import os
import argparse
import pyodbc
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    conn_str = (
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        rf"SERVER={os.getenv('DEST_DB_HOST')},{os.getenv('DEST_DB_PORT')};"
        rf"DATABASE={os.getenv('DEST_DB_NAME').strip()};"
        r'Trusted_Connection=yes;'
    )
    return pyodbc.connect(conn_str)

SQL_CTE = """WITH base_sellers AS (
    SELECT DISTINCT seller_id_bk, seller_city, seller_state
    FROM gold.dim_seller
),
cte_sales_performance AS (
    SELECT 
        ds.seller_id_bk,
        COUNT(DISTINCT fi.order_id_bk) as total_orders_fulfilled,
        SUM(fi.unit_price) as total_revenue,
        SUM(fi.unit_price) / NULLIF(COUNT(DISTINCT fi.order_id_bk), 0) as avg_order_value,
        COUNT(fi.order_item_sk) as total_items_sold,
        COUNT(DISTINCT fi.product_sk) as total_distinct_products_sold,
        COUNT(DISTINCT fi.customer_sk) as total_distinct_customers_served,
        SUM(fi.unit_freight_value) as total_freight_value,
        (
            SELECT TOP 1 dp.product_category_name
            FROM gold.fact_order_items fi2
            JOIN gold.dim_seller ds2 ON fi2.seller_sk = ds2.seller_sk
            JOIN gold.dim_product dp ON fi2.product_sk = dp.product_sk
            WHERE ds2.seller_id_bk = ds.seller_id_bk
            GROUP BY dp.product_category_name
            ORDER BY COUNT(*) DESC
        ) as top_category,
        COUNT(DISTINCT dp_out.product_category_name) as distinct_categories_sold
    FROM gold.fact_order_items fi
    JOIN gold.dim_seller ds ON fi.seller_sk = ds.seller_sk
    LEFT JOIN gold.dim_product dp_out ON fi.product_sk = dp_out.product_sk
    GROUP BY ds.seller_id_bk
),
cte_delivery AS (
    SELECT 
        o.seller_id_bk,
        AVG(CAST(lc.days_to_deliver AS FLOAT)) as avg_days_to_deliver,
        AVG(CAST(lc.days_to_approve AS FLOAT)) as avg_days_to_approve,
        SUM(CASE WHEN lc.is_delivered_on_time = 0 THEN 1 ELSE 0 END) as total_late_orders,
        COUNT(lc.order_id_bk) as total_delivery_records
    FROM (
        SELECT DISTINCT ds.seller_id_bk, fi.order_id_bk
        FROM gold.fact_order_items fi
        JOIN gold.dim_seller ds ON fi.seller_sk = ds.seller_sk
    ) o
    JOIN gold.fact_order_life_cycle lc ON o.order_id_bk = lc.order_id_bk
    GROUP BY o.seller_id_bk
),
cte_satisfaction AS (
    SELECT 
        o.seller_id_bk,
        AVG(CAST(r.review_score AS FLOAT)) as avg_review_score,
        COUNT(DISTINCT r.review_sk) as total_reviews_received,
        SUM(CASE WHEN r.review_score = 1 THEN 1 ELSE 0 END) as one_star_reviews,
        SUM(CASE WHEN r.review_score = 5 THEN 1 ELSE 0 END) as five_star_reviews
    FROM (
        SELECT DISTINCT ds.seller_id_bk, fi.order_id_bk
        FROM gold.fact_order_items fi
        JOIN gold.dim_seller ds ON fi.seller_sk = ds.seller_sk
    ) o
    JOIN gold.fact_reviews r ON o.order_id_bk = r.order_id_bk
    GROUP BY o.seller_id_bk
),
cte_marketing AS (
    SELECT 
        ds.seller_id_bk,
        MAX(1) as was_acquired_via_mql,
        MAX(mc.origin) as mql_origin,
        MAX(mc.business_type) as business_type,
        MAX(mc.lead_type) as lead_type,
        MAX(mc.lead_behaviour_profile) as lead_behaviour_profile,
        MAX(mc.average_stock) as average_stock,
        MAX(mf.declared_monthly_revenue) as declared_monthly_revenue,
        MAX(mf.declared_product_catalog_size) as declared_product_catalog_size,
        MAX(CASE WHEN mc.has_company = 1 THEN 1 ELSE 0 END) as has_company,
        MAX(CASE WHEN mc.has_gtin = 1 THEN 1 ELSE 0 END) as has_gtin,
        MAX(DATEDIFF(day, d1.full_date, d2.full_date)) as days_to_close_deal
    FROM gold.fact_marketing_funnel mf
    JOIN gold.dim_seller ds ON mf.seller_sk = ds.seller_sk
    LEFT JOIN gold.dim_marketing_channel mc ON mf.mql_channel_sk = mc.mql_channel_sk
    LEFT JOIN gold.dim_date d1 ON mf.first_contact_date_key = d1.date_key
    LEFT JOIN gold.dim_date d2 ON mf.won_date_key = d2.date_key
    GROUP BY ds.seller_id_bk
)
"""

SQL_SELECT = """SELECT 
    b.seller_id_bk as seller_id,
    MAX(b.seller_city) as seller_city,
    MAX(b.seller_state) as seller_state,

    COALESCE(SUM(sp.total_orders_fulfilled), 0) as total_orders_fulfilled,
    COALESCE(SUM(sp.total_revenue), 0) as total_revenue,
    COALESCE(SUM(sp.avg_order_value), 0) as avg_order_value,
    COALESCE(SUM(sp.total_items_sold), 0) as total_items_sold,
    COALESCE(SUM(sp.total_distinct_products_sold), 0) as total_distinct_products_sold,
    COALESCE(SUM(sp.total_distinct_customers_served), 0) as total_distinct_customers_served,
    COALESCE(SUM(sp.total_freight_value), 0) as total_freight_value,

    SUM(d.avg_days_to_deliver) as avg_days_to_deliver,
    SUM(d.avg_days_to_approve) as avg_days_to_approve,
    COALESCE(CAST(SUM(d.total_late_orders) AS FLOAT) / NULLIF(SUM(d.total_delivery_records), 0) * 100, 0) as pct_late_deliveries,
    COALESCE(SUM(d.total_late_orders), 0) as total_late_orders,

    SUM(s.avg_review_score) as avg_review_score,
    COALESCE(SUM(s.total_reviews_received), 0) as total_reviews_received,
    COALESCE(CAST(SUM(s.one_star_reviews) AS FLOAT) / NULLIF(SUM(s.total_reviews_received), 0) * 100, 0) as pct_1star_reviews,
    COALESCE(CAST(SUM(s.five_star_reviews) AS FLOAT) / NULLIF(SUM(s.total_reviews_received), 0) * 100, 0) as pct_5star_reviews,

    COALESCE(SUM(sp.distinct_categories_sold), 0) as distinct_categories_sold,
    MAX(sp.top_category) as top_category,

    COALESCE(SUM(m.was_acquired_via_mql), 0) as was_acquired_via_mql,
    MAX(m.mql_origin) as mql_origin,
    MAX(m.business_type) as business_type,
    MAX(m.lead_type) as lead_type,
    MAX(m.lead_behaviour_profile) as lead_behaviour_profile,
    MAX(m.average_stock) as average_stock,
    SUM(m.declared_monthly_revenue) as declared_monthly_revenue,
    SUM(m.declared_product_catalog_size) as declared_product_catalog_size,
    SUM(m.has_company) as has_company,
    SUM(m.has_gtin) as has_gtin,
    SUM(m.days_to_close_deal) as days_to_close_deal

FROM base_sellers b
LEFT JOIN cte_sales_performance sp ON b.seller_id_bk = sp.seller_id_bk
LEFT JOIN cte_delivery d ON b.seller_id_bk = d.seller_id_bk
LEFT JOIN cte_satisfaction s ON b.seller_id_bk = s.seller_id_bk
LEFT JOIN cte_marketing m ON b.seller_id_bk = m.seller_id_bk
GROUP BY b.seller_id_bk
"""

SQL_QUERY = SQL_CTE + SQL_SELECT

def verify_data():
    conn = get_connection()
    print("--- Verifying gold.obt_sellers Query ---\n")
    
    df = pd.read_sql(SQL_QUERY, conn)
    
    print("Sample 5 rows:")
    pd.set_option('display.max_columns', None)
    print(df.head(5).to_string(index=False))
    print("\n--- Summary Stats ---")
    print(f"Total Rows: {len(df)}")
    print(f"Min total_revenue: {df['total_revenue'].min()}")
    print(f"Max total_revenue: {df['total_revenue'].max()}")
    print(f"Min avg_review_score: {df['avg_review_score'].min()}")
    print(f"Max avg_review_score: {df['avg_review_score'].max()}")
    
    print("\n--- NULL Counts ---")
    null_counts = df.isnull().sum()
    print(null_counts[null_counts > 0].to_string())
    
    print("\nData verification complete. Run with --execute to build the persistent table.")
    conn.close()

def execute_build():
    conn = get_connection()
    cursor = conn.cursor()
    print("Executing persistent build of gold.obt_sellers...")
    
    sql_create = SQL_CTE + SQL_SELECT.replace("SELECT ", "SELECT TOP 0 ", 1).replace("FROM base_sellers b", "INTO gold.obt_sellers FROM base_sellers b")
    
    build_sql = f"""
    -- Ensure table exists with correct schema matching the query
    IF OBJECT_ID('gold.obt_sellers', 'U') IS NULL
    BEGIN
        EXEC('{sql_create.replace("'", "''")}');
        PRINT 'Created table gold.obt_sellers'
    END

    -- Transactional Insert
    BEGIN TRY
        BEGIN TRAN;
        TRUNCATE TABLE gold.obt_sellers;
        
        {SQL_CTE}
        INSERT INTO gold.obt_sellers
        {SQL_SELECT};
        
        COMMIT TRAN;
        PRINT 'Successfully populated gold.obt_sellers within transaction.'
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRAN;
        PRINT 'Error occurred. Transaction rolled back.';
        THROW;
    END CATCH
    """
    
    try:
        cursor.execute(build_sql)
        conn.commit()
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually build the persistent table")
    args = parser.parse_args()
    
    if args.execute:
        execute_build()
    else:
        verify_data()
