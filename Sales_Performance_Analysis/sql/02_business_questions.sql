/* ============================================================================
   Sales Performance Analysis - 02: the business question ledger
   ----------------------------------------------------------------------------
   Structured as QUESTION -> QUERY -> ANSWER -> SO WHAT, rather than as a pile
   of statements. Anyone reading this file follows the reasoning, not just the
   syntax.

   The ANSWER lines are the verified values from the shipped dataset, so you can
   check your own work as you go.

   Business problem being investigated
   ----------------------------------
   Revenue is flat quarter-on-quarter while order volume holds steady.
   Leadership needs to know whether the cause is pricing, product mix, region
   or customer retention - in order to decide where to place next quarter's
   Rs 5,00,000 promotional budget.
   ========================================================================== */


/* ---------------------------------------------------------------------------
   SECTION A - HEADLINE PERFORMANCE
   --------------------------------------------------------------------------- */

/* Q1. What is our overall sales performance for the period?
   ANSWER: Rs 19,333,556 net revenue, 1,145 orders, 2,553 units,
           639 customers, Rs 16,885 AOV, 23.0% gross margin.
   SO WHAT: This is the baseline every recommendation is measured against.
            Note margin is only 23% - low enough that discounting decisions
            matter more than volume decisions.                                */
SELECT COUNT(DISTINCT order_id)                          AS total_orders,
       COUNT(DISTINCT customer_id)                       AS total_customers,
       SUM(quantity)                                     AS units_sold,
       ROUND(SUM(net_revenue), 0)                        AS net_revenue,
       ROUND(SUM(gross_profit), 0)                       AS gross_profit,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1) AS margin_pct,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0) AS avg_order_value
FROM sales;


/* Q2. How much revenue are we losing to discounts in absolute terms?
   ANSWER: Rs 22,416,850 gross -> Rs 19,333,556 net, so Rs 3,083,294 of list
           value was given away: 13.8% of gross revenue.
   SO WHAT: That giveaway is larger than the entire Furniture category's gross
            profit (Rs 1,657,088). A discount line that big deserves its own
            analysis rather than being treated as a cost of doing business
            (see Q11).                                                       */
SELECT ROUND(SUM(gross_revenue), 0)                        AS gross_revenue,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(SUM(gross_revenue - net_revenue), 0)          AS discount_given,
       ROUND(100 * SUM(gross_revenue - net_revenue)
                 / SUM(gross_revenue), 1)                  AS discount_pct_of_gross
FROM sales;


/* ---------------------------------------------------------------------------
   SECTION B - PRODUCT AND CATEGORY
   --------------------------------------------------------------------------- */

/* Q3. Which category generates the most revenue?
   ANSWER: Electronics, Rs 12,023,186 = 62.2% of net revenue.
   SO WHAT: On revenue alone Electronics looks like the obvious place to
            invest. Q4 shows why that conclusion is wrong.                   */
SELECT category,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(100 * SUM(net_revenue) / SUM(SUM(net_revenue)) OVER (), 1)
                                                           AS revenue_share_pct,
       COUNT(DISTINCT order_id)                            AS orders
FROM sales
GROUP BY category
ORDER BY net_revenue DESC;


/* Q4. Which category is most PROFITABLE - and does that change the ranking?
   ANSWER: Yes, completely. Electronics is 1st on revenue but LAST on margin
           at 14.9%. Apparel earns 49.5% margin on 3.5% of revenue.
   SO WHAT: This is the core finding of the project. Revenue share is not
            importance. Budget allocated on revenue rank would be pointed at
            the least profitable category in the business.                   */
SELECT category,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(SUM(gross_profit), 0)                         AS gross_profit,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1) AS margin_pct,
       RANK() OVER (ORDER BY SUM(net_revenue)  DESC)       AS rank_by_revenue,
       RANK() OVER (ORDER BY SUM(gross_profit)
                             / SUM(net_revenue) DESC)      AS rank_by_margin
FROM sales
GROUP BY category
ORDER BY net_revenue DESC;


/* Q5. What are the top 5 products?
   ANSWER: Laptop (21.7%), Phone (13.9%), Smart TV (13.1%), Sofa Set (7.9%),
           Tablet (5.7%) - together 62.4% of net revenue.
   SO WHAT: Five SKUs out of 32 carry nearly two thirds of the business.
            Any stock-out or price change here is a material revenue event.  */
SELECT product_name,
       category,
       SUM(quantity)                                       AS units,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1) AS margin_pct
FROM sales
GROUP BY product_name, category
ORDER BY net_revenue DESC
LIMIT 5;


/* Q6. Which products perform poorly and should be reviewed?
   ANSWER: 16 of 32 SKUs each contribute under 1% of net revenue.
   SO WHAT: The long tail is not free - it consumes photography, storage,
            merchandising and catalogue attention out of all proportion to
            what it returns. Candidates for delisting or renegotiation.      */
SELECT product_name,
       category,
       SUM(quantity)                                       AS units,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(100 * SUM(net_revenue) / SUM(SUM(net_revenue)) OVER (), 2)
                                                           AS revenue_share_pct
FROM sales
GROUP BY product_name, category
HAVING SUM(net_revenue) < 0.01 * (SELECT SUM(net_revenue) FROM sales)
ORDER BY net_revenue ASC;


/* ---------------------------------------------------------------------------
   SECTION C - CUSTOMERS
   --------------------------------------------------------------------------- */

/* Q7. Who are our top customers by spend, and how concentrated are we?
   SO WHAT: If a small number of accounts carry a large revenue share, that is
            a retention risk that belongs on the dashboard, not a nice fact.  */
SELECT customer_id,
       COUNT(DISTINCT order_id)                            AS orders,
       ROUND(SUM(net_revenue), 0)                          AS lifetime_spend,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0) AS avg_order_value,
       MAX(order_date)                                     AS last_order_date
FROM sales
GROUP BY customer_id
ORDER BY lifetime_spend DESC
LIMIT 10;


/* Q8. How many customers do we have, and how many come back?
   ANSWER: 639 customers, 35.4% place more than one order.
   SO WHAT: Roughly two thirds of customers never return. Retention, not
            acquisition, is the cheaper growth lever.                        */
WITH cust AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS orders
    FROM sales
    GROUP BY customer_id
)
SELECT COUNT(*)                                            AS total_customers,
       SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)         AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)
                   / COUNT(*), 1)                          AS repeat_rate_pct
FROM cust;


/* ---------------------------------------------------------------------------
   SECTION D - TIME
   --------------------------------------------------------------------------- */

/* Q9. Which month had the highest revenue, and is the trend up or down?
   ANSWER: Peak 2025-10 (Rs 2,526,792, +103.7% MoM - festive season).
           Trough 2026-01 (Rs 968,900, -51.1% - post-festive collapse).
   SO WHAT: Revenue is seasonal, not flat. Comparing Q4 with Q1 without
            adjusting for the festive spike would produce a false alarm -
            which is very likely what prompted the original brief.           */
SELECT order_month,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       COUNT(DISTINCT order_id)                            AS orders,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0) AS avg_order_value
FROM sales
GROUP BY order_month
ORDER BY order_month;


/* Q10. Does the sales mix shift between the festive peak and the slump?
   SO WHAT: If big-ticket Electronics is what spikes and then disappears, the
            January problem is a category problem, not a demand problem.     */
SELECT category,
       ROUND(SUM(CASE WHEN order_month IN ('2025-10', '2025-11')
                      THEN net_revenue ELSE 0 END), 0)     AS festive_revenue,
       ROUND(SUM(CASE WHEN order_month IN ('2026-01', '2026-02')
                      THEN net_revenue ELSE 0 END), 0)     AS slump_revenue,
       ROUND(100.0 * SUM(CASE WHEN order_month IN ('2025-10', '2025-11')
                              THEN net_revenue ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN order_month IN ('2026-01', '2026-02')
                                     THEN net_revenue ELSE 0 END), 0), 0)
                                                           AS festive_vs_slump_index
FROM sales
GROUP BY category
ORDER BY festive_revenue DESC;


/* ---------------------------------------------------------------------------
   SECTION E - THE DECISION THE BRIEF ASKED ABOUT
   --------------------------------------------------------------------------- */

/* Q11. Is discounting actually buying us anything?
   ANSWER: No. AOV FALLS from Rs 15,280 (no discount) to Rs 11,301 (21%+),
           while margin collapses from 36.1% to 5.4%.
   SO WHAT: This is the recommendation. Deep discounts are not producing
            bigger baskets, so the margin is being given away for nothing.
            Full sizing of the fix is in 03_advanced_analysis.sql.           */
SELECT CASE WHEN discount_pct =  0    THEN '0%'
            WHEN discount_pct <= 0.10 THEN '1-10%'
            WHEN discount_pct <= 0.20 THEN '11-20%'
            ELSE '21%+' END                                AS discount_band,
       COUNT(DISTINCT order_id)                            AS orders,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0) AS avg_order_value,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1) AS margin_pct
FROM sales
GROUP BY 1
ORDER BY 1;


/* Q12. Where should the promotional budget NOT go?
   ANSWER: Salem - 104 customers but only 12.5% repeat against a 41.0% peer
           average. Acquisition works there; retention does not.
   SO WHAT: Spending more on acquisition in Salem buys first orders that never
            become second orders. Fix retention first.                       */
WITH home AS (   /* attribute each customer to their most frequent real region */
    SELECT customer_id, region,
           ROW_NUMBER() OVER (PARTITION BY customer_id
                              ORDER BY COUNT(*) DESC) AS rn
    FROM sales
    WHERE region <> 'Unknown'
    GROUP BY customer_id, region
),
cust AS (
    SELECT s.customer_id,
           h.region                        AS home_region,
           COUNT(DISTINCT s.order_id)      AS orders,
           SUM(s.net_revenue)              AS spend
    FROM sales s
    JOIN home h ON h.customer_id = s.customer_id AND h.rn = 1
    GROUP BY s.customer_id, h.region
)
SELECT home_region,
       COUNT(*)                                            AS customers,
       ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)
                   / COUNT(*), 1)                          AS repeat_rate_pct,
       ROUND(SUM(spend), 0)                                AS net_revenue,
       ROUND(AVG(spend), 0)                                AS avg_customer_value
FROM cust
GROUP BY home_region
ORDER BY net_revenue DESC;


/* Q13. Does channel change the picture?
   SO WHAT: A cheap extra cut. If mobile AOV is materially lower, the bundle
            threshold recommendation needs a channel-specific version.       */
SELECT channel,
       COUNT(DISTINCT order_id)                            AS orders,
       ROUND(SUM(net_revenue), 0)                          AS net_revenue,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_id), 0) AS avg_order_value,
       ROUND(100 * SUM(gross_profit) / SUM(net_revenue), 1) AS margin_pct
FROM sales
GROUP BY channel
ORDER BY net_revenue DESC;
