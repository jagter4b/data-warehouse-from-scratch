/* ============================================================
data_validation.sql
Database: BI_AI | Schema: bronze
============================================================ */

USE [BI_AI];
GO

-- 1. Row counts for all 11 Bronze tables
SELECT 'orders' AS [table_name], COUNT(*) AS [row_count] FROM [bronze].[orders]
UNION ALL
SELECT 'customers', COUNT(*) FROM [bronze].[customers]
UNION ALL
SELECT 'sellers', COUNT(*) FROM [bronze].[sellers]
UNION ALL
SELECT 'products', COUNT(*) FROM [bronze].[products]
UNION ALL
SELECT 'order_items', COUNT(*) FROM [bronze].[order_items]
UNION ALL
SELECT 'order_payments', COUNT(*) FROM [bronze].[order_payments]
UNION ALL
SELECT 'order_reviews', COUNT(*) FROM [bronze].[order_reviews]
UNION ALL
SELECT 'product_category_name_translation', COUNT(*) FROM [bronze].[product_category_name_translation]
UNION ALL
SELECT 'geolocation', COUNT(*) FROM [bronze].[geolocation]
UNION ALL
SELECT 'closed_deals', COUNT(*) FROM [bronze].[closed_deals]
UNION ALL
SELECT 'marketing_qualified_leads', COUNT(*) FROM [bronze].[marketing_qualified_leads]
ORDER BY [table_name];

-- 2. Preview Samples
SELECT TOP 10 * FROM [bronze].[orders];
SELECT TOP 10 * FROM [bronze].[customers];
SELECT TOP 10 * FROM [bronze].[geolocation];
