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

SQL_CTE = """WITH base_orders AS (
    SELECT 
        order_id_bk,
        customer_sk,
        total_order_value,
        total_freight_value,
        total_payment_value,
        total_items,
        total_distinct_products,
        purchase_date_key,
        approval_date_key,
        carrier_date_key,
        delivery_date_key,
        estimated_delivery_date_key,
        days_to_approve,
        days_to_ship as days_to_carrier,
        days_to_deliver,
        days_delivery_variance as c_scheduled_vs_actual_days,
        CASE WHEN is_delivered_on_time = 0 THEN 1 ELSE 0 END as is_late,
        order_status_sk
    FROM gold.fact_order_life_cycle
),
cte_sellers AS (
    SELECT order_id_bk, seller_id_bk as seller_id
    FROM (
        SELECT 
            fi.order_id_bk, 
            ds.seller_id_bk,
            ROW_NUMBER() OVER (PARTITION BY fi.order_id_bk ORDER BY COUNT(*) DESC) as rn
        FROM gold.fact_order_items fi
        JOIN gold.dim_seller ds ON fi.seller_sk = ds.seller_sk
        GROUP BY fi.order_id_bk, ds.seller_id_bk
    ) sq
    WHERE rn = 1
),
cte_payments AS (
    SELECT order_id_bk, MAX(payment_installments) as payment_installments,
           MAX(CASE WHEN rn = 1 THEN payment_type END) as preferred_payment_type
    FROM (
        SELECT 
            fp.order_id_bk, 
            fp.payment_installments,
            pt.payment_type,
            ROW_NUMBER() OVER (PARTITION BY fp.order_id_bk ORDER BY fp.payment_value DESC) as rn
        FROM gold.fact_payments fp
        JOIN gold.dim_payment_type pt ON fp.payment_type_sk = pt.payment_type_sk
    ) sq
    GROUP BY order_id_bk
),
cte_products AS (
    SELECT order_id_bk, 
           MAX(CASE WHEN rn = 1 THEN product_category_name END) as primary_category,
           COUNT(DISTINCT product_category_name) as distinct_categories,
           AVG(CAST(product_weight_g AS FLOAT)) as avg_product_weight_g,
           AVG(CAST(product_photos_qty AS FLOAT)) as avg_product_photos_qty
    FROM (
        SELECT 
            fi.order_id_bk,
            dp.product_category_name,
            dp.product_weight_g,
            dp.product_photos_qty,
            ROW_NUMBER() OVER (PARTITION BY fi.order_id_bk ORDER BY fi.unit_price DESC) as rn
        FROM gold.fact_order_items fi
        JOIN gold.dim_product dp ON fi.product_sk = dp.product_sk
    ) sq
    GROUP BY order_id_bk
),
cte_reviews AS (
    SELECT r.order_id_bk,
           AVG(CAST(r.review_score AS FLOAT)) as review_score,
           MAX(1) as has_review,
           MAX(CASE WHEN rc.review_comment_message IS NOT NULL THEN 1 ELSE 0 END) as has_written_comment
    FROM gold.fact_reviews r
    LEFT JOIN gold.review_comments rc ON r.review_sk = rc.review_sk
    GROUP BY r.order_id_bk
)
"""

SQL_SELECT = """SELECT 
    b.order_id_bk as order_id,
    c.customer_sk as customer_id,
    c.customer_unique_id_bk as customer_unique_id,
    s.seller_id,
    os.order_status,
    
    b.total_order_value,
    b.total_freight_value,
    b.total_payment_value,
    b.total_items,
    b.total_distinct_products,
    p.payment_installments,
    p.preferred_payment_type,
    
    pr.primary_category,
    COALESCE(pr.distinct_categories, 0) as distinct_categories,
    pr.avg_product_weight_g,
    pr.avg_product_photos_qty,
    
    dp.full_date as purchase_date,
    da.full_date as approval_date,
    dcarr.full_date as carrier_date,
    dd.full_date as delivered_date,
    de.full_date as estimated_date,
    dp.year as purchase_year,
    dp.month_num as purchase_month,
    dp.quarter_num as purchase_quarter,
    dp.day_of_week_num as purchase_day_of_week,
    
    b.days_to_approve,
    b.days_to_carrier,
    b.days_to_deliver,
    b.c_scheduled_vs_actual_days,
    b.is_late,
    
    r.review_score,
    COALESCE(r.has_review, 0) as has_review,
    COALESCE(r.has_written_comment, 0) as has_written_comment,
    
    sel.avg_review_score as seller_avg_review_score,
    sel.pct_late_deliveries as seller_pct_late_deliveries,
    sel.was_acquired_via_mql as seller_was_acquired_via_mql,
    sel.total_orders_fulfilled as seller_total_orders_fulfilled

FROM base_orders b
JOIN gold.dim_customer c ON b.customer_sk = c.customer_sk
LEFT JOIN gold.dim_order_status os ON b.order_status_sk = os.order_status_sk
LEFT JOIN cte_sellers s ON b.order_id_bk = s.order_id_bk
LEFT JOIN cte_payments p ON b.order_id_bk = p.order_id_bk
LEFT JOIN cte_products pr ON b.order_id_bk = pr.order_id_bk
LEFT JOIN cte_reviews r ON b.order_id_bk = r.order_id_bk
LEFT JOIN gold.obt_sellers sel ON s.seller_id = sel.seller_id
LEFT JOIN gold.dim_date dp ON b.purchase_date_key = dp.date_key
LEFT JOIN gold.dim_date da ON b.approval_date_key = da.date_key
LEFT JOIN gold.dim_date dcarr ON b.carrier_date_key = dcarr.date_key
LEFT JOIN gold.dim_date dd ON b.delivery_date_key = dd.date_key
LEFT JOIN gold.dim_date de ON b.estimated_delivery_date_key = de.date_key
"""

SQL_QUERY = SQL_CTE + SQL_SELECT

def verify_data():
    conn = get_connection()
    print("--- Verifying gold.obt_orders Query ---\n")
    
    df = pd.read_sql(SQL_QUERY, conn)
    
    print("Sample 5 rows:")
    pd.set_option('display.max_columns', None)
    print(df.head(5).to_string(index=False))
    print("\n--- Summary Stats ---")
    print(f"Total Rows: {len(df)}")
    print(f"Min total_order_value: {df['total_order_value'].min()}")
    print(f"Max total_order_value: {df['total_order_value'].max()}")
    print(f"Min days_to_deliver: {df['days_to_deliver'].min()}")
    print(f"Max days_to_deliver: {df['days_to_deliver'].max()}")
    
    print("\n--- NULL Counts ---")
    null_counts = df.isnull().sum()
    print(null_counts[null_counts > 0].to_string())
    
    print("\nData verification complete. Run with --execute to build the persistent table.")
    conn.close()

def execute_build():
    conn = get_connection()
    cursor = conn.cursor()
    print("Executing persistent build of gold.obt_orders...")
    
    sql_create = SQL_CTE + SQL_SELECT.replace("SELECT ", "SELECT TOP 0 ", 1).replace("FROM base_orders b", "INTO gold.obt_orders FROM base_orders b")
    
    build_sql = f"""
    -- Ensure table exists with correct schema matching the query
    IF OBJECT_ID('gold.obt_orders', 'U') IS NULL
    BEGIN
        EXEC('{sql_create.replace("'", "''")}');
        PRINT 'Created table gold.obt_orders'
    END

    -- Transactional Insert
    BEGIN TRY
        BEGIN TRAN;
        TRUNCATE TABLE gold.obt_orders;
        
        {SQL_CTE}
        INSERT INTO gold.obt_orders
        {SQL_SELECT};
        
        COMMIT TRAN;
        PRINT 'Successfully populated gold.obt_orders within transaction.'
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
