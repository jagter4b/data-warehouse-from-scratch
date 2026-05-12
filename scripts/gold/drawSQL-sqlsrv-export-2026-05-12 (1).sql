CREATE TABLE "dim_date"(
    "date_key" INT NOT NULL,
    "full_date" DATE NOT NULL,
    "day_of_week" VARCHAR(10) NOT NULL,
    "day_of_month" TINYINT NOT NULL,
    "month_name" VARCHAR(10) NOT NULL,
    "quarter" CHAR(2) NOT NULL,
    "year" SMALLINT NOT NULL,
    "is_weekend" BIT NOT NULL
);
ALTER TABLE
    "dim_date" ADD CONSTRAINT "dim_date_date_key_primary" PRIMARY KEY("date_key");
CREATE UNIQUE INDEX "dim_date_full_date_unique" ON
    "dim_date"("full_date");
CREATE TABLE "dim_customer"(
    "customer_sk" INT NOT NULL,
    "customer_unique_id_bk" VARCHAR(32) NOT NULL,
    "customer_zip_code_prefix" VARCHAR(5) NOT NULL,
    "customer_city" VARCHAR(50) NOT NULL,
    "customer_state" CHAR(2) NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "dim_customer" ADD CONSTRAINT "dim_customer_customer_sk_primary" PRIMARY KEY("customer_sk");
CREATE UNIQUE INDEX "dim_customer_customer_unique_id_bk_unique" ON
    "dim_customer"("customer_unique_id_bk");
CREATE TABLE "dim_product"(
    "product_sk" INT NOT NULL,
    "product_id_bk" VARCHAR(32) NOT NULL,
    "product_category_name" VARCHAR(50) NOT NULL DEFAULT 'Unknown',
    "product_name_length" INT NULL,
    "product_description_length" INT NULL,
    "product_photos_qty" INT NULL,
    "product_weight_g" INT NULL,
    "product_length_cm" DECIMAL(6, 1) NULL,
    "product_height_cm" DECIMAL(6, 1) NULL,
    "product_width_cm" DECIMAL(6, 1) NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "dim_product" ADD CONSTRAINT "dim_product_product_sk_primary" PRIMARY KEY("product_sk");
CREATE UNIQUE INDEX "dim_product_product_id_bk_unique" ON
    "dim_product"("product_id_bk");
CREATE TABLE "dim_seller"(
    "seller_sk" INT NOT NULL,
    "seller_id_bk" VARCHAR(32) NOT NULL,
    "seller_zip_code_prefix" VARCHAR(5) NOT NULL,
    "seller_city" VARCHAR(50) NOT NULL,
    "seller_state" CHAR(2) NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "dim_seller" ADD CONSTRAINT "dim_seller_seller_sk_primary" PRIMARY KEY("seller_sk");
CREATE UNIQUE INDEX "dim_seller_seller_id_bk_unique" ON
    "dim_seller"("seller_id_bk");
CREATE TABLE "dim_order_status"(
    "order_status_sk" INT NOT NULL,
    "order_status" VARCHAR(15) NOT NULL
);
ALTER TABLE
    "dim_order_status" ADD CONSTRAINT "dim_order_status_order_status_sk_primary" PRIMARY KEY("order_status_sk");
CREATE UNIQUE INDEX "dim_order_status_order_status_unique" ON
    "dim_order_status"("order_status");
CREATE TABLE "dim_payment_type"(
    "payment_type_sk" INT NOT NULL,
    "payment_type" VARCHAR(15) NOT NULL
);
ALTER TABLE
    "dim_payment_type" ADD CONSTRAINT "dim_payment_type_payment_type_sk_primary" PRIMARY KEY("payment_type_sk");
CREATE UNIQUE INDEX "dim_payment_type_payment_type_unique" ON
    "dim_payment_type"("payment_type");
CREATE TABLE "dim_marketing_channel"(
    "mql_key" INT NOT NULL,
    "mql_id" INT NOT NULL,
    "origin" VARCHAR(255) NOT NULL,
    "business_segment" VARCHAR(255) NOT NULL,
    "lead_type" VARCHAR(255) NOT NULL,
    "business_type" VARCHAR(255) NOT NULL,
    "has_company" BINARY(16) NOT NULL,
    "has_GTIN" BINARY(16) NOT NULL
);
ALTER TABLE
    "dim_marketing_channel" ADD CONSTRAINT "dim_marketing_channel_mql_key_primary" PRIMARY KEY("mql_key");
CREATE UNIQUE INDEX "dim_marketing_channel_mql_id_unique" ON
    "dim_marketing_channel"("mql_id");
CREATE TABLE "fact_order_items"(
    "order_item_sk" INT NOT NULL,
    "purchase_date_key" INT NOT NULL,
    "customer_sk" INT NOT NULL,
    "product_sk" INT NOT NULL,
    "seller_sk" INT NOT NULL,
    "order_id_bk" VARCHAR(32) NOT NULL,
    "order_item_id_bk" INT NOT NULL,
    "shipping_limit_date" DATETIME2 NULL,
    "price" DECIMAL(10, 2) NOT NULL,
    "freight_value" DECIMAL(10, 2) NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "fact_order_items" ADD CONSTRAINT "fact_order_items_order_item_sk_primary" PRIMARY KEY("order_item_sk");
CREATE TABLE "fact_payments"(
    "payment_sk" INT NOT NULL,
    "purchase_date_key" INT NOT NULL,
    "customer_sk" INT NOT NULL,
    "payment_type_sk" INT NOT NULL,
    "order_id_bk" VARCHAR(32) NOT NULL,
    "payment_sequential_bk" INT NOT NULL,
    "payment_value" DECIMAL(10, 2) NOT NULL,
    "payment_installments" INT NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "fact_payments" ADD CONSTRAINT "fact_payments_payment_sk_primary" PRIMARY KEY("payment_sk");
CREATE TABLE "fact_reviews"(
    "review_sk" INT NOT NULL,
    "review_creation_date_key" INT NOT NULL,
    "review_answer_date_key" INT NOT NULL,
    "customer_sk" INT NOT NULL,
    "review_id_bk" VARCHAR(32) NOT NULL,
    "order_id_bk" VARCHAR(32) NOT NULL,
    "review_score" INT NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_ecommerce');
ALTER TABLE
    "fact_reviews" ADD CONSTRAINT "fact_reviews_review_sk_primary" PRIMARY KEY("review_sk");
CREATE TABLE "review_comments"(
    "review_sk" INT NOT NULL,
    "review_comment_title" VARCHAR(200) NULL,
    "review_comment_message" VARCHAR(255) NULL
);
ALTER TABLE
    "review_comments" ADD CONSTRAINT "review_comments_review_sk_primary" PRIMARY KEY("review_sk");
CREATE TABLE "fact_order_life_cycle"(
    "order_fulfillment_sk" INT NOT NULL,
    "customer_sk" INT NOT NULL,
    "order_status_sk" INT NOT NULL,
    "order_id_bk" VARCHAR(32) NOT NULL,
    "purchase_date_key" INT NOT NULL,
    "approval_date_key" INT NOT NULL,
    "carrier_date_key" INT NOT NULL,
    "delivery_date_key" INT NOT NULL,
    "estimated_delivery_date_key" INT NOT NULL,
    "days_to_approve" INT NULL,
    "days_to_ship" INT NULL,
    "days_to_deliver" INT NULL,
    "days_purchase_to_delivery" INT NULL,
    "days_delivery_variance" INT NULL,
    "is_delivered_on_time" BIT NULL,
    "total_items" INT NOT NULL,
    "total_distinct_products" INT NOT NULL,
    "total_distinct_sellers" INT NOT NULL,
    "total_order_value" DECIMAL(10, 2) NOT NULL,
    "total_freight_value" DECIMAL(10, 2) NOT NULL,
    "total_payment_value" DECIMAL(10, 2) NOT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(255) NOT NULL);
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_order_fulfillment_sk_primary" PRIMARY KEY("order_fulfillment_sk");
CREATE TABLE "fact_marketing_funnel"(
    "closed_sk" INT NOT NULL,
    "MQL_FK" INT NOT NULL,
    "first_contact_date" DATE NOT NULL,
    "won_date" INT NOT NULL,
    "seller_sk" INT NOT NULL,
    "mql_id_bk" VARCHAR(32) NOT NULL,
    "sdr_id" VARCHAR(32) NULL,
    "sr_id" VARCHAR(32) NULL,
    "lead_type" VARCHAR(20) NULL,
    "declared_monthly_revenue" DECIMAL(15, 2) NULL,
    "declared_product_catalog_size" DECIMAL(10, 2) NULL,
    "days_to_close" INT NULL,
    "load_timestamp" DATETIME2 NOT NULL DEFAULT GETDATE(), "source_system" VARCHAR(20) NOT NULL DEFAULT 'olist_marketing');
ALTER TABLE
    "fact_marketing_funnel" ADD CONSTRAINT "fact_marketing_funnel_closed_sk_primary" PRIMARY KEY("closed_sk");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_order_status_sk_foreign" FOREIGN KEY("order_status_sk") REFERENCES "dim_order_status"("order_status_sk");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_approval_date_key_foreign" FOREIGN KEY("approval_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_order_items" ADD CONSTRAINT "fact_order_items_product_sk_foreign" FOREIGN KEY("product_sk") REFERENCES "dim_product"("product_sk");
ALTER TABLE
    "fact_marketing_funnel" ADD CONSTRAINT "fact_marketing_funnel_mql_fk_foreign" FOREIGN KEY("MQL_FK") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_order_items" ADD CONSTRAINT "fact_order_items_seller_sk_foreign" FOREIGN KEY("seller_sk") REFERENCES "dim_seller"("seller_sk");
ALTER TABLE
    "fact_marketing_funnel" ADD CONSTRAINT "fact_marketing_funnel_won_date_foreign" FOREIGN KEY("won_date") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "dim_seller" ADD CONSTRAINT "dim_seller_seller_sk_foreign" FOREIGN KEY("seller_sk") REFERENCES "fact_marketing_funnel"("seller_sk");
ALTER TABLE
    "fact_reviews" ADD CONSTRAINT "fact_reviews_review_creation_date_key_foreign" FOREIGN KEY("review_creation_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "review_comments" ADD CONSTRAINT "review_comments_review_sk_foreign" FOREIGN KEY("review_sk") REFERENCES "fact_reviews"("review_sk");
ALTER TABLE
    "fact_payments" ADD CONSTRAINT "fact_payments_purchase_date_key_foreign" FOREIGN KEY("purchase_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_customer_sk_foreign" FOREIGN KEY("customer_sk") REFERENCES "dim_customer"("customer_sk");
ALTER TABLE
    "fact_order_items" ADD CONSTRAINT "fact_order_items_customer_sk_foreign" FOREIGN KEY("customer_sk") REFERENCES "dim_customer"("customer_sk");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_purchase_date_key_foreign" FOREIGN KEY("purchase_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_reviews" ADD CONSTRAINT "fact_reviews_customer_sk_foreign" FOREIGN KEY("customer_sk") REFERENCES "dim_customer"("customer_sk");
ALTER TABLE
    "fact_reviews" ADD CONSTRAINT "fact_reviews_review_answer_date_key_foreign" FOREIGN KEY("review_answer_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_order_items" ADD CONSTRAINT "fact_order_items_purchase_date_key_foreign" FOREIGN KEY("purchase_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_payments" ADD CONSTRAINT "fact_payments_customer_sk_foreign" FOREIGN KEY("customer_sk") REFERENCES "dim_customer"("customer_sk");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_estimated_delivery_date_key_foreign" FOREIGN KEY("estimated_delivery_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "dim_marketing_channel" ADD CONSTRAINT "dim_marketing_channel_mql_key_foreign" FOREIGN KEY("mql_key") REFERENCES "fact_marketing_funnel"("MQL_FK");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_carrier_date_key_foreign" FOREIGN KEY("carrier_date_key") REFERENCES "dim_date"("date_key");
ALTER TABLE
    "fact_payments" ADD CONSTRAINT "fact_payments_payment_type_sk_foreign" FOREIGN KEY("payment_type_sk") REFERENCES "dim_payment_type"("payment_type_sk");
ALTER TABLE
    "fact_order_life_cycle" ADD CONSTRAINT "fact_order_life_cycle_delivery_date_key_foreign" FOREIGN KEY("delivery_date_key") REFERENCES "dim_date"("date_key");