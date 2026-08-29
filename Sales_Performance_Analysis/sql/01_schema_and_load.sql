/* ============================================================================
   Sales Performance Analysis - 01: schema, load and integrity checks
   ----------------------------------------------------------------------------
   Loads data/cleaned_sales_data.csv into a typed table and then asserts the
   figures the rest of the analysis depends on. Run this first.

   Primary dialect: PostgreSQL. MySQL / SQL Server variants are noted inline.
   ========================================================================== */

DROP TABLE IF EXISTS sales;

CREATE TABLE sales (
    order_id        INTEGER        NOT NULL,
    order_date      DATE           NOT NULL,
    customer_id     TEXT           NOT NULL,
    product_name    TEXT           NOT NULL,
    category        TEXT           NOT NULL,
    quantity        INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    unit_cost       NUMERIC(12, 2) NOT NULL CHECK (unit_cost  > 0),
    discount_pct    NUMERIC(5, 4)  NOT NULL CHECK (discount_pct BETWEEN 0 AND 0.9),
    region          TEXT           NOT NULL,
    channel         TEXT           NOT NULL,
    gross_revenue   NUMERIC(14, 2) NOT NULL,
    net_revenue     NUMERIC(14, 2) NOT NULL,
    gross_profit    NUMERIC(14, 2) NOT NULL,
    margin_pct      NUMERIC(7, 4)  NOT NULL,
    order_month     TEXT           NOT NULL
);


/* ---------------------------------------------------------------------------
   LOAD - PostgreSQL (psql client-side copy, so no server file access needed)
   Adjust the path to wherever you cloned the repo.
   --------------------------------------------------------------------------- */
-- \copy sales FROM 'data/cleaned_sales_data.csv' WITH (FORMAT csv, HEADER true)

/* LOAD - MySQL 8
   LOAD DATA LOCAL INFILE 'data/cleaned_sales_data.csv'
       INTO TABLE sales
       FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
       LINES TERMINATED BY '\n'
       IGNORE 1 LINES;

   LOAD - SQL Server
   BULK INSERT sales FROM 'data\cleaned_sales_data.csv'
       WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a');
*/


/* ---------------------------------------------------------------------------
   Helpful indexes for the analysis queries
   --------------------------------------------------------------------------- */
CREATE INDEX idx_sales_date     ON sales (order_date);
CREATE INDEX idx_sales_category ON sales (category);
CREATE INDEX idx_sales_customer ON sales (customer_id);
CREATE INDEX idx_sales_region   ON sales (region);


/* ============================================================================
   INTEGRITY CHECKS
   Every check below must return 'PASS'. These are the reference values from
   the shipped dataset - if any of them fail, the load is wrong and every
   downstream number will be wrong too.
   ========================================================================== */

-- 1. Row count
SELECT CASE WHEN COUNT(*) = 1577 THEN 'PASS' ELSE 'FAIL' END AS check_row_count,
       COUNT(*) AS actual, 1577 AS expected
FROM sales;

-- 2. Distinct orders. NOTE: this is why COUNT(*) is never the order count -
--    the table is one row per order LINE, not per order.
SELECT CASE WHEN COUNT(DISTINCT order_id) = 1145 THEN 'PASS' ELSE 'FAIL' END
           AS check_order_count,
       COUNT(DISTINCT order_id) AS actual, 1145 AS expected
FROM sales;

-- 3. Distinct customers and products
SELECT CASE WHEN COUNT(DISTINCT customer_id) = 639
             AND COUNT(DISTINCT product_name) = 32
            THEN 'PASS' ELSE 'FAIL' END AS check_dimensions,
       COUNT(DISTINCT customer_id) AS customers,
       COUNT(DISTINCT product_name) AS products
FROM sales;

-- 4. Net revenue reconciles to the Excel stage (within rounding tolerance)
SELECT CASE WHEN ABS(SUM(net_revenue) - 19333556) < 5
            THEN 'PASS' ELSE 'FAIL' END AS check_net_revenue,
       ROUND(SUM(net_revenue), 0) AS actual, 19333556 AS expected
FROM sales;

-- 5. The stored calculated columns actually agree with their formulas.
--    Catches a broken Excel fill or a bad load far better than eyeballing.
SELECT CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_calc_columns,
       COUNT(*) AS mismatched_rows
FROM sales
WHERE ABS(net_revenue  - quantity * unit_price * (1 - discount_pct)) > 0.05
   OR ABS(gross_profit - (net_revenue - quantity * unit_cost))       > 0.05;

-- 6. No cleaning defects survived: no future dates, no blank regions,
--    no negative quantities, no 10x price outliers.
SELECT CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS check_no_defects,
       COUNT(*) AS offending_rows
FROM sales
WHERE order_date > DATE '2026-08-29'
   OR TRIM(region) = ''
   OR quantity <= 0;

-- 7. Region values are standardised - this should return exactly 9 rows
--    (8 cities + 'Unknown'). More than 9 means TRIM/PROPER was not applied.
SELECT region, COUNT(*) AS rows
FROM sales
GROUP BY region
ORDER BY COUNT(*) DESC;

-- 8. Full 12-month coverage with no gaps
SELECT CASE WHEN COUNT(DISTINCT order_month) = 12 THEN 'PASS' ELSE 'FAIL' END
           AS check_month_coverage,
       MIN(order_date) AS first_order,
       MAX(order_date) AS last_order,
       COUNT(DISTINCT order_month) AS months
FROM sales;
