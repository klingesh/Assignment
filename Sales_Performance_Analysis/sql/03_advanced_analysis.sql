/* ============================================================================
   Sales Performance Analysis - 03: advanced analysis
   ----------------------------------------------------------------------------
   The queries that differentiate a candidate. Everyone writes SUM/GROUP BY;
   these use window functions, running totals, deciling and scenario sizing.

   Primary dialect: PostgreSQL. Portable rewrites for MySQL 8 / SQL Server are
   given at the bottom of the file where the syntax differs.
   ========================================================================== */


/* ---------------------------------------------------------------------------
   1. MONTH-ON-MONTH GROWTH
      Demonstrates: LAG, NULLIF for safe division, DATE_TRUNC.
      Verified output: peak 2025-10 at +103.7%, trough 2026-01 at -51.1%.
   --------------------------------------------------------------------------- */
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_date)::date AS month,
           SUM(net_revenue)                      AS revenue,
           SUM(gross_profit)                     AS profit,
           COUNT(DISTINCT order_id)              AS orders
    FROM sales
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 0)                                        AS revenue,
       orders,
       ROUND(LAG(revenue) OVER (ORDER BY month), 0)             AS prev_month,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                   / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1)
                                                                AS mom_growth_pct,
       ROUND(AVG(revenue) OVER (ORDER BY month
                                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0)
                                                                AS revenue_3mo_avg,
       ROUND(100.0 * profit / revenue, 1)                       AS margin_pct
FROM monthly
ORDER BY month;


/* ---------------------------------------------------------------------------
   2. PARETO CONCENTRATION
      Demonstrates: running total with an explicit window frame, ROW_NUMBER,
      aggregate window functions.
      Verified output: 10 of 32 products (31% of catalogue) reach 80% of
      revenue; 16 SKUs contribute under 1% each.
   --------------------------------------------------------------------------- */
WITH product_rev AS (
    SELECT product_name, category, SUM(net_revenue) AS revenue
    FROM sales
    GROUP BY product_name, category
),
ranked AS (
    SELECT product_name, category, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC
                              ROWS BETWEEN UNBOUNDED PRECEDING
                                       AND CURRENT ROW)  AS running_revenue,
           SUM(revenue)     OVER ()                      AS total_revenue,
           ROW_NUMBER()     OVER (ORDER BY revenue DESC) AS rn,
           COUNT(*)         OVER ()                      AS n_products
    FROM product_rev
)
SELECT rn                                                AS rank,
       product_name,
       category,
       ROUND(revenue, 0)                                 AS revenue,
       ROUND(100.0 * revenue / total_revenue, 2)         AS revenue_share_pct,
       ROUND(100.0 * running_revenue / total_revenue, 1) AS cumulative_revenue_pct,
       ROUND(100.0 * rn / n_products, 1)                 AS cumulative_product_pct,
       CASE WHEN 100.0 * running_revenue / total_revenue <= 80
            THEN 'Core - the 80% engine'
            ELSE 'Long tail - review' END                AS pareto_segment
FROM ranked
ORDER BY revenue DESC;


/* ---------------------------------------------------------------------------
   3. CATEGORY ACTION MATRIX
      Demonstrates: CASE segmentation driven by aggregate window functions, so
      the recommendation is produced by the query rather than added afterwards.
   --------------------------------------------------------------------------- */
WITH cat AS (
    SELECT category,
           SUM(net_revenue)                                  AS revenue,
           SUM(gross_profit)                                 AS profit,
           SUM(net_revenue) / COUNT(DISTINCT order_id)       AS aov,
           SUM(gross_profit) / SUM(net_revenue)              AS margin_pct,
           AVG(discount_pct)                                 AS avg_discount
    FROM sales
    GROUP BY category
)
SELECT category,
       ROUND(revenue, 0)                                     AS revenue,
       ROUND(100 * revenue / SUM(revenue) OVER (), 1)         AS revenue_share_pct,
       ROUND(aov, 0)                                         AS aov,
       ROUND(100 * margin_pct, 1)                            AS margin_pct,
       ROUND(100 * avg_discount, 1)                          AS avg_discount_pct,
       CASE
         WHEN revenue    >= AVG(revenue)    OVER ()
          AND margin_pct >= AVG(margin_pct) OVER ()
              THEN 'Star - protect and scale spend'
         WHEN revenue    >= AVG(revenue)    OVER ()
              THEN 'Volume driver - cut discounting, bundle to lift margin'
         WHEN margin_pct >= AVG(margin_pct) OVER ()
              THEN 'Hidden gem - increase traffic and visibility'
         ELSE     'Underperformer - rationalise or reprice'
       END                                                   AS recommended_action
FROM cat
ORDER BY revenue DESC;


/* ---------------------------------------------------------------------------
   4. DISCOUNT EFFECTIVENESS - the finding that drives the recommendation
      Verified output:
        0%      240 orders  AOV Rs 15,280  margin 36.1%
        1-10%   461 orders  AOV Rs 13,645  margin 29.4%
        11-20%  418 orders  AOV Rs 13,779  margin 18.8%
        21%+    320 orders  AOV Rs 11,301  margin  5.4%
      AOV FALLS as discount deepens. The margin is being given away for
      nothing - there is no basket-size benefit to pay for it.
   --------------------------------------------------------------------------- */
WITH banded AS (
    SELECT CASE WHEN discount_pct =  0    THEN '0%'
                WHEN discount_pct <= 0.10 THEN '1-10%'
                WHEN discount_pct <= 0.20 THEN '11-20%'
                ELSE '21%+' END        AS discount_band,
           order_id, net_revenue, gross_profit, quantity
    FROM sales
)
SELECT discount_band,
       COUNT(DISTINCT order_id)                                  AS orders,
       SUM(quantity)                                             AS units,
       ROUND(SUM(net_revenue), 0)                                AS net_revenue,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0)      AS aov,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1)       AS margin_pct,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id)
             - FIRST_VALUE(SUM(net_revenue) / COUNT(DISTINCT order_id))
               OVER (ORDER BY discount_band), 0)                  AS aov_vs_no_discount
FROM banded
GROUP BY discount_band
ORDER BY discount_band;


/* ---------------------------------------------------------------------------
   5. SIZING THE FIX - what does capping discounts at 15% actually recover?
      Demonstrates: scenario modelling in SQL with an explicit, stated
      assumption (constant volume).
      Verified output: 496 orders affected, Rs 769,336 additional gross profit,
      a 17.3% improvement on total gross profit.

      ASSUMPTION: volume is held constant. This is the weak point of the
      recommendation and you must say so before anyone asks - proving it needs
      a controlled A/B test, not this dataset.
   --------------------------------------------------------------------------- */
WITH deep AS (
    SELECT order_id, quantity, unit_price, unit_cost, discount_pct,
           gross_profit                                       AS profit_now,
           quantity * unit_price * (1 - 0.15)
             - quantity * unit_cost                            AS profit_capped
    FROM sales
    WHERE discount_pct > 0.15
)
SELECT COUNT(*)                                                AS order_lines,
       COUNT(DISTINCT order_id)                                 AS orders_affected,
       ROUND(SUM(profit_now), 0)                                AS profit_today,
       ROUND(SUM(profit_capped), 0)                             AS profit_at_15pct_cap,
       ROUND(SUM(profit_capped - profit_now), 0)                AS profit_uplift,
       ROUND(100.0 * SUM(profit_capped - profit_now)
                   / (SELECT SUM(gross_profit) FROM sales), 1)  AS uplift_pct_of_total
FROM deep;


/* ---------------------------------------------------------------------------
   6. CUSTOMER VALUE DECILES AND CONCENTRATION
      Demonstrates: NTILE, FILTER, revenue concentration analysis.
   --------------------------------------------------------------------------- */
WITH cust AS (
    SELECT customer_id,
           COUNT(DISTINCT order_id) AS orders,
           SUM(net_revenue)         AS spend,
           MAX(order_date)          AS last_order
    FROM sales
    GROUP BY customer_id
),
deciled AS (
    SELECT *, NTILE(10) OVER (ORDER BY spend DESC) AS spend_decile
    FROM cust
)
SELECT spend_decile,
       COUNT(*)                                        AS customers,
       ROUND(SUM(spend), 0)                            AS revenue,
       ROUND(100.0 * SUM(spend)
                   / SUM(SUM(spend)) OVER (), 1)       AS revenue_share_pct,
       ROUND(AVG(orders), 2)                           AS avg_orders,
       ROUND(AVG(spend), 0)                            AS avg_spend
FROM deciled
GROUP BY spend_decile
ORDER BY spend_decile;

-- Headline concentration figures (PostgreSQL FILTER syntax)
WITH cust AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS orders, SUM(net_revenue) AS spend
    FROM sales GROUP BY customer_id
),
deciled AS (SELECT *, NTILE(10) OVER (ORDER BY spend DESC) AS d FROM cust)
SELECT COUNT(*)                                                  AS customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE orders > 1) / COUNT(*), 1)
                                                                 AS repeat_rate_pct,
       ROUND(AVG(spend), 0)                                      AS avg_customer_value,
       ROUND(100.0 * SUM(spend) FILTER (WHERE d = 1) / SUM(spend), 1)
                                                                 AS top_decile_share_pct
FROM deciled;


/* ---------------------------------------------------------------------------
   7. RFM-LITE SEGMENTATION
      Recency / Frequency / Monetary scored 1-4 on quartiles, then labelled.
      Gives the retention recommendation an actionable target list.
   --------------------------------------------------------------------------- */
WITH cust AS (
    SELECT customer_id,
           MAX(order_date)                                   AS last_order,
           (DATE '2026-08-29' - MAX(order_date))             AS recency_days,
           COUNT(DISTINCT order_id)                          AS frequency,
           SUM(net_revenue)                                  AS monetary
    FROM sales
    GROUP BY customer_id
),
scored AS (
    SELECT customer_id, last_order, recency_days, frequency, monetary,
           NTILE(4) OVER (ORDER BY recency_days ASC)  AS r_score,  -- 4 = recent
           NTILE(4) OVER (ORDER BY frequency   ASC)  AS f_score,
           NTILE(4) OVER (ORDER BY monetary    ASC)  AS m_score
    FROM cust
)
SELECT CASE
         WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
         WHEN r_score >= 3 AND f_score <= 2                  THEN 'New / promising'
         WHEN r_score <= 2 AND f_score >= 3                  THEN 'At risk - win back'
         WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2  THEN 'Lapsed low value'
         ELSE 'Needs attention'
       END                                            AS segment,
       COUNT(*)                                       AS customers,
       ROUND(SUM(monetary), 0)                        AS revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1)
                                                      AS revenue_share_pct,
       ROUND(AVG(frequency), 2)                       AS avg_orders,
       ROUND(AVG(recency_days), 0)                    AS avg_days_since_order
FROM scored
GROUP BY 1
ORDER BY revenue DESC;


/* ---------------------------------------------------------------------------
   8. REGIONAL RETENTION GAP
      Attributes each customer to a home region first, so the 'Unknown' bucket
      created during cleaning cannot contaminate the retention figures. This
      kind of care is exactly what interviewers probe for.
      Verified output: Salem 104 customers, 12.5% repeat vs 41.0% peer average.
   --------------------------------------------------------------------------- */
WITH home AS (
    SELECT customer_id, region,
           ROW_NUMBER() OVER (PARTITION BY customer_id
                              ORDER BY COUNT(*) DESC, region) AS rn
    FROM sales
    WHERE region <> 'Unknown'
    GROUP BY customer_id, region
),
cust AS (
    SELECT h.region                    AS home_region,
           s.customer_id,
           COUNT(DISTINCT s.order_id)  AS orders,
           SUM(s.net_revenue)          AS spend
    FROM sales s
    JOIN home h ON h.customer_id = s.customer_id AND h.rn = 1
    GROUP BY h.region, s.customer_id
)
SELECT home_region,
       COUNT(*)                                                  AS customers,
       SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)               AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)
                   / COUNT(*), 1)                                AS repeat_rate_pct,
       ROUND(SUM(spend), 0)                                      AS net_revenue,
       ROUND(AVG(spend), 0)                                      AS avg_customer_value,
       ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) / COUNT(*)
             - AVG(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)
                         / COUNT(*)) OVER (), 1)                 AS vs_avg_pp
FROM cust
GROUP BY home_region
ORDER BY net_revenue DESC;


/* ============================================================================
   PORTABILITY NOTES
   ============================================================================

   FILTER (WHERE ...) is PostgreSQL only. Everywhere else:
       COUNT(*) FILTER (WHERE orders > 1)
   becomes
       SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)

   DATE_TRUNC('month', order_date):
       MySQL 8     -> DATE_FORMAT(order_date, '%Y-%m-01')
       SQL Server  -> DATEFROMPARTS(YEAR(order_date), MONTH(order_date), 1)
       or just use the pre-computed order_month column in this dataset.

   Date subtraction (DATE '2026-08-29' - MAX(order_date)):
       MySQL 8     -> DATEDIFF('2026-08-29', MAX(order_date))
       SQL Server  -> DATEDIFF(day, MAX(order_date), '2026-08-29')

   ::date cast:
       MySQL / SQL Server -> CAST(x AS DATE)

   All window functions used here (LAG, ROW_NUMBER, NTILE, FIRST_VALUE, running
   SUM with an explicit frame) are supported in PostgreSQL 8.4+, MySQL 8.0+,
   SQL Server 2012+ and SQLite 3.25+.
   ========================================================================== */
