import os
import argparse
import pyodbc
import pandas as pd
from dotenv import load_dotenv

# Load credentials
load_dotenv()

def get_connection():
    conn_str = (
        r'DRIVER={ODBC Driver 17 for SQL Server};'
        rf"SERVER={os.getenv('DEST_DB_HOST')},{os.getenv('DEST_DB_PORT')};"
        rf"DATABASE={os.getenv('DEST_DB_NAME')};"
        r'Trusted_Connection=yes;'
    )
    return pyodbc.connect(conn_str)

SQL_CTE = """WITH base_customers AS (
    SELECT DISTINCT customer_unique_id_bk, customer_city, customer_state
    FROM gold.dim_customer
),
cte_monetary AS (
    SELECT 
        dc.customer_unique_id_bk,
        SUM(fp.payment_value) as total_spend,
        SUM(fp.payment_value) / NULLIF(COUNT(DISTINCT fp.order_id_bk), 0) as avg_order_value,
        AVG(CAST(fp.payment_installments AS FLOAT)) as avg_installments,
        (
            SELECT TOP 1 pt.payment_type
            FROM gold.fact_payments fp2
            JOIN gold.dim_customer dc2 ON fp2.customer_sk = dc2.customer_sk
            JOIN gold.dim_payment_type pt ON fp2.payment_type_sk = pt.payment_type_sk
            WHERE dc2.customer_unique_id_bk = dc.customer_unique_id_bk
            GROUP BY pt.payment_type
            ORDER BY COUNT(*) DESC
        ) as preferred_payment_type
    FROM gold.fact_payments fp
    JOIN gold.dim_customer dc ON fp.customer_sk = dc.customer_sk
    GROUP BY dc.customer_unique_id_bk
),
cte_max_order AS (
    SELECT 
        dc.customer_unique_id_bk,
        MAX(order_total) as max_order_value
    FROM (
        SELECT customer_sk, SUM(payment_value) as order_total 
        FROM gold.fact_payments GROUP BY customer_sk
    ) o
    JOIN gold.dim_customer dc ON o.customer_sk = dc.customer_sk
    GROUP BY dc.customer_unique_id_bk
),
cte_frequency_product AS (
    SELECT 
        dc.customer_unique_id_bk,
        COUNT(DISTINCT fi.order_id_bk) as total_orders,
        COUNT(DISTINCT fi.product_sk) as total_distinct_products,
        COUNT(DISTINCT dp.product_category_name) as distinct_categories_bought,
        (
            SELECT TOP 1 dp2.product_category_name
            FROM gold.fact_order_items fi2
            JOIN gold.dim_customer dc2 ON fi2.customer_sk = dc2.customer_sk
            LEFT JOIN gold.dim_product dp2 ON fi2.product_sk = dp2.product_sk
            WHERE dc2.customer_unique_id_bk = dc.customer_unique_id_bk
            GROUP BY dp2.product_category_name
            ORDER BY COUNT(*) DESC
        ) as top_category
    FROM gold.fact_order_items fi
    JOIN gold.dim_customer dc ON fi.customer_sk = dc.customer_sk
    LEFT JOIN gold.dim_product dp ON fi.product_sk = dp.product_sk
    GROUP BY dc.customer_unique_id_bk
),
cte_recency_delivery AS (
    SELECT 
        dc.customer_unique_id_bk,
        SUM(lc.total_items) as total_items_bought,
        SUM(lc.total_freight_value) as total_freight_paid,
        MIN(d.full_date) as first_order_date,
        MAX(d.full_date) as last_order_date,
        AVG(CAST(lc.days_to_deliver AS FLOAT)) as avg_days_to_deliver,
        AVG(CAST(lc.days_to_approve AS FLOAT)) as avg_days_to_approve,
        SUM(CASE WHEN lc.is_delivered_on_time = 0 THEN 1 ELSE 0 END) as total_late_orders,
        COUNT(lc.order_id_bk) as total_delivery_records,
        COUNT(DISTINCT d.year * 100 + d.month_num) as distinct_months_active
    FROM gold.fact_order_life_cycle lc
    JOIN gold.dim_customer dc ON lc.customer_sk = dc.customer_sk
    LEFT JOIN gold.dim_date d ON lc.purchase_date_key = d.date_key
    GROUP BY dc.customer_unique_id_bk
),
cte_satisfaction AS (
    SELECT 
        dc.customer_unique_id_bk,
        AVG(CAST(r.review_score AS FLOAT)) as avg_review_score,
        COUNT(r.review_sk) as total_reviews,
        SUM(CASE WHEN r.review_score = 1 THEN 1 ELSE 0 END) as one_star_reviews,
        SUM(CASE WHEN r.review_score = 5 THEN 1 ELSE 0 END) as five_star_reviews,
        MAX(CASE WHEN rc.review_comment_message IS NOT NULL THEN 1 ELSE 0 END) as has_written_review
    FROM gold.fact_reviews r
    JOIN gold.dim_customer dc ON r.customer_sk = dc.customer_sk
    LEFT JOIN gold.review_comments rc ON r.review_sk = rc.review_sk
    GROUP BY dc.customer_unique_id_bk
),
cte_seller_marketing AS (
    SELECT 
        dc.customer_unique_id_bk,
        COUNT(DISTINCT fi.seller_sk) as total_distinct_sellers,
        MAX(CASE WHEN mf.mql_id_bk IS NOT NULL THEN 1 ELSE 0 END) as any_seller_from_mql,
        MAX(mc.origin) as mql_acquisition_channel
    FROM gold.fact_order_items fi
    JOIN gold.dim_customer dc ON fi.customer_sk = dc.customer_sk
    LEFT JOIN gold.fact_marketing_funnel mf ON fi.seller_sk = mf.seller_sk
    LEFT JOIN gold.dim_marketing_channel mc ON mf.mql_channel_sk = mc.mql_channel_sk
    GROUP BY dc.customer_unique_id_bk
)
"""

SQL_SELECT = """SELECT 
    b.customer_unique_id_bk as customer_unique_id,
    MAX(b.customer_city) as customer_city,
    MAX(b.customer_state) as customer_state,
    
    COALESCE(SUM(m.total_spend), 0) as total_spend,
    COALESCE(SUM(m.avg_order_value), 0) as avg_order_value,
    COALESCE(SUM(mo.max_order_value), 0) as max_order_value,
    COALESCE(SUM(rd.total_freight_paid), 0) as total_freight_paid,
    COALESCE(SUM(m.avg_installments), 0) as avg_installments,
    MAX(m.preferred_payment_type) as preferred_payment_type,

    COALESCE(SUM(fp.total_orders), 0) as total_orders,
    COALESCE(SUM(rd.total_items_bought), 0) as total_items_bought,
    COALESCE(SUM(fp.total_distinct_products), 0) as total_distinct_products,
    COALESCE(CAST(SUM(rd.total_items_bought) AS FLOAT) / NULLIF(SUM(fp.total_orders), 0), 0) as avg_items_per_order,
    COALESCE(SUM(rd.distinct_months_active), 0) as distinct_months_active,

    MIN(rd.first_order_date) as first_order_date,
    MAX(rd.last_order_date) as last_order_date,
    DATEDIFF(day, MIN(rd.first_order_date), MAX(rd.last_order_date)) as customer_tenure_days,
    DATEDIFF(day, MAX(rd.last_order_date), GETDATE()) as days_since_last_order,

    COALESCE(SUM(fp.distinct_categories_bought), 0) as distinct_categories_bought,
    MAX(fp.top_category) as top_category,

    SUM(rd.avg_days_to_deliver) as avg_days_to_deliver,
    SUM(rd.avg_days_to_approve) as avg_days_to_approve,
    COALESCE(CAST(SUM(rd.total_late_orders) AS FLOAT) / NULLIF(SUM(rd.total_delivery_records), 0) * 100, 0) as pct_late_deliveries,
    COALESCE(SUM(rd.total_late_orders), 0) as total_late_orders,

    SUM(s.avg_review_score) as avg_review_score,
    COALESCE(SUM(s.total_reviews), 0) as total_reviews,
    COALESCE(CAST(SUM(s.one_star_reviews) AS FLOAT) / NULLIF(SUM(s.total_reviews), 0) * 100, 0) as pct_1star_reviews,
    COALESCE(CAST(SUM(s.five_star_reviews) AS FLOAT) / NULLIF(SUM(s.total_reviews), 0) * 100, 0) as pct_5star_reviews,
    COALESCE(SUM(s.has_written_review), 0) as has_written_review,

    COALESCE(SUM(sm.total_distinct_sellers), 0) as total_distinct_sellers,
    COALESCE(SUM(sm.any_seller_from_mql), 0) as any_seller_from_mql,
    MAX(sm.mql_acquisition_channel) as mql_acquisition_channel
FROM base_customers b
LEFT JOIN cte_monetary m ON b.customer_unique_id_bk = m.customer_unique_id_bk
LEFT JOIN cte_max_order mo ON b.customer_unique_id_bk = mo.customer_unique_id_bk
LEFT JOIN cte_frequency_product fp ON b.customer_unique_id_bk = fp.customer_unique_id_bk
LEFT JOIN cte_recency_delivery rd ON b.customer_unique_id_bk = rd.customer_unique_id_bk
LEFT JOIN cte_satisfaction s ON b.customer_unique_id_bk = s.customer_unique_id_bk
LEFT JOIN cte_seller_marketing sm ON b.customer_unique_id_bk = sm.customer_unique_id_bk
GROUP BY b.customer_unique_id_bk
"""

SQL_QUERY = SQL_CTE + SQL_SELECT

def verify_data():
    conn = get_connection()
    print("--- Verifying gold.obt_customers Query ---\n")
    
    df_sample = pd.read_sql(SQL_QUERY + " ORDER BY b.customer_unique_id_bk OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY", conn)
    print("Sample 5 rows:")
    pd.set_option('display.max_columns', None)
    print(df_sample.to_string(index=False))
    print("\n")
    
    cursor = conn.cursor()
    count_sql = SQL_CTE + "SELECT COUNT(DISTINCT customer_unique_id_bk) FROM base_customers"
    cursor.execute(count_sql)
    count = cursor.fetchone()[0]
    print(f"Total Unique Customers (Estimated Rows): {count}")
    print("\nData verification complete. Run with --execute to build the persistent table.")
    conn.close()

def execute_build():
    conn = get_connection()
    cursor = conn.cursor()
    print("Executing persistent build of gold.obt_customers...")
    
    sql_create = SQL_CTE + SQL_SELECT.replace("SELECT ", "SELECT TOP 0 ", 1).replace("FROM base_customers b", "INTO gold.obt_customers FROM base_customers b")
    
    build_sql = f"""
    -- Ensure table exists with correct schema matching the query
    IF OBJECT_ID('gold.obt_customers', 'U') IS NULL
    BEGIN
        EXEC('{sql_create.replace("'", "''")}');
        PRINT 'Created table gold.obt_customers'
    END

    -- Transactional Insert
    BEGIN TRY
        BEGIN TRAN;
        TRUNCATE TABLE gold.obt_customers;
        
        {SQL_CTE}
        INSERT INTO gold.obt_customers
        {SQL_SELECT};
        
        COMMIT TRAN;
        PRINT 'Successfully populated gold.obt_customers within transaction.'
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
