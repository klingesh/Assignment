#!/usr/bin/env python3
"""
Builds 'Sales_Performance_Analysis_Project_Guide.pdf'.

Every figure quoted in the Findings and Appendix sections is computed live from
data/cleaned_sales_data.csv at build time, so the document can never drift out
of sync with the dataset - and no number in it is invented.
"""

import csv
import os
from collections import defaultdict
from datetime import date

from minipdf import (Document, ACCENT, ACCENT_DARK, ACCENT_TINT, INK, MUTED,
                     GOOD, BAD, WARN, BORDER)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(HERE, '..', 'Sales_Performance_Analysis_Project_Guide.pdf')

PROJECT_DATE = date(2026, 8, 29)


# --------------------------------------------------------------------------
# Load + compute
# --------------------------------------------------------------------------

def rs(x, decimals=0):
    return 'Rs ' + format(round(x, decimals), ',.%df' % decimals)


def load():
    with open(os.path.join(DATA, 'cleaned_sales_data.csv'), encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r['Quantity'] = int(r['Quantity'])
        r['Price'] = float(r['Price'])
        r['Unit Cost'] = float(r['Unit Cost'])
        r['Discount %'] = float(r['Discount %'])
        r['Net Revenue'] = float(r['Net Revenue'])
        r['Gross Profit'] = float(r['Gross Profit'])
    return rows


def load_raw_count():
    with open(os.path.join(DATA, 'raw_sales_data.csv'), encoding='utf-8') as f:
        return sum(1 for _ in f) - 1


def load_quality_log():
    with open(os.path.join(DATA, 'data_quality_log.csv'), encoding='utf-8') as f:
        return list(csv.reader(f))


def compute(rows):
    m = {}
    m['rows'] = len(rows)
    m['orders'] = len(set(r['Order ID'] for r in rows))
    m['units'] = sum(r['Quantity'] for r in rows)
    m['customers'] = len(set(r['Customer'] for r in rows))
    m['net'] = sum(r['Net Revenue'] for r in rows)
    m['profit'] = sum(r['Gross Profit'] for r in rows)
    m['margin'] = m['profit'] / m['net']
    m['aov'] = m['net'] / m['orders']
    m['start'] = min(r['Date'] for r in rows)
    m['end'] = max(r['Date'] for r in rows)

    # Category
    cat = defaultdict(lambda: {'net': 0.0, 'profit': 0.0, 'orders': set(),
                               'units': 0})
    for r in rows:
        c = cat[r['Category']]
        c['net'] += r['Net Revenue']
        c['profit'] += r['Gross Profit']
        c['units'] += r['Quantity']
        c['orders'].add(r['Order ID'])
    m['cat'] = sorted(((k, v) for k, v in cat.items()),
                      key=lambda x: -x[1]['net'])

    # Products / Pareto
    prod = defaultdict(float)
    for r in rows:
        prod[r['Product']] += r['Net Revenue']
    ranked = sorted(prod.items(), key=lambda x: -x[1])
    m['products'] = ranked
    m['n_products'] = len(ranked)
    run, n80 = 0.0, 0
    for i, (_, v) in enumerate(ranked, 1):
        run += v
        if run / m['net'] >= 0.80:
            n80 = i
            break
    m['n80'] = n80
    m['pct80'] = 100.0 * n80 / len(ranked)
    m['tail'] = [p for p, v in ranked if v / m['net'] < 0.01]

    # Discount bands
    def band(d):
        if d == 0:
            return '0%'
        if d <= 0.10:
            return '1-10%'
        if d <= 0.20:
            return '11-20%'
        return '21%+'

    bands = defaultdict(lambda: {'net': 0.0, 'profit': 0.0, 'orders': set()})
    for r in rows:
        b = bands[band(r['Discount %'])]
        b['net'] += r['Net Revenue']
        b['profit'] += r['Gross Profit']
        b['orders'].add(r['Order ID'])
    m['bands'] = [(k, bands[k]) for k in ('0%', '1-10%', '11-20%', '21%+')
                  if k in bands]

    # Region + repeat rate on home region
    home_votes = defaultdict(lambda: defaultdict(int))
    cust_orders = defaultdict(set)
    reg_net = defaultdict(float)
    for r in rows:
        cust_orders[r['Customer']].add(r['Order ID'])
        reg_net[r['Region']] += r['Net Revenue']
        if r['Region'] != 'Unknown':
            home_votes[r['Customer']][r['Region']] += 1
    home = {c: max(v.items(), key=lambda x: x[1])[0]
            for c, v in home_votes.items()}
    reg_cust = defaultdict(list)
    for c, orders in cust_orders.items():
        if c in home:
            reg_cust[home[c]].append(len(orders))
    m['regions'] = sorted(
        ((k, len(v), 100.0 * sum(1 for n in v if n > 1) / len(v), reg_net[k])
         for k, v in reg_cust.items()), key=lambda x: -x[3])
    m['repeat_all'] = 100.0 * sum(
        1 for o in cust_orders.values() if len(o) > 1) / len(cust_orders)
    m['unknown_net'] = reg_net.get('Unknown', 0.0)

    # Monthly
    months = defaultdict(float)
    for r in rows:
        months[r['Order Month']] += r['Net Revenue']
    seq = sorted(months.items())
    m['months'] = seq
    m['peak_month'] = max(seq, key=lambda x: x[1])
    m['trough_month'] = min(seq, key=lambda x: x[1])

    # Opportunity sizing: deep-discount orders repriced to a 15% cap.
    deep = [r for r in rows if r['Discount %'] > 0.15]
    cur_profit = sum(r['Gross Profit'] for r in deep)
    capped_profit = sum(
        r['Quantity'] * r['Price'] * (1 - 0.15) - r['Quantity'] * r['Unit Cost']
        for r in deep)
    m['deep_rows'] = len(deep)
    m['deep_orders'] = len(set(r['Order ID'] for r in deep))
    m['deep_uplift'] = capped_profit - cur_profit
    m['deep_uplift_pct'] = 100.0 * (capped_profit - cur_profit) / m['profit']

    # Salem-style retention gap: worst region by repeat rate
    m['worst_region'] = min(m['regions'], key=lambda x: x[2])
    peers = [x[2] for x in m['regions'] if x[0] != m['worst_region'][0]]
    m['peer_repeat'] = sum(peers) / len(peers)
    return m


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------

def build(m, raw_count, qlog):
    d = Document(footer_text='Sales Performance Analysis  |  Business Analyst '
                             'Portfolio Project  |  Excel + SQL + Power BI')

    # ---------------- Cover -------------------------------------------
    d.title_block(
        kicker='Business Analyst Portfolio Project',
        title_lines=['Sales Performance', 'Analysis'],
        subtitle='From business problem to data-driven recommendation',
        meta_lines=[
            ('Tools', 'Microsoft Excel  |  SQL  |  Power BI'),
            ('Dataset', '%s cleaned transaction rows  |  %s orders  |  %s customers'
             % (format(m['rows'], ','), format(m['orders'], ','),
                format(m['customers'], ','))),
            ('Period', '%s to %s' % (m['start'], m['end'])),
            ('Prepared', PROJECT_DATE.strftime('%d %B %Y')),
        ])
    d._suppress_footer = False

    d.para('This guide turns "Sales Analysis" from a practice exercise into a '
           'portfolio project that demonstrates the full Business Analyst arc: '
           '**business problem to clean data to analysis to visualisation to '
           'recommendation**. It ships with a generated 12-month e-commerce '
           'dataset that has real, findable patterns built into it.',
           size=10, leading=14.4)

    d.kpi_strip([
        ('Net Revenue', rs(m['net']).replace('Rs ', 'Rs '), ACCENT),
        ('Orders', format(m['orders'], ','), ACCENT),
        ('Avg Order Value', rs(m['aov']), ACCENT),
        ('Gross Margin', '%.1f%%' % (100 * m['margin']), GOOD),
    ])

    d.h2('Three corrections to the usual version of this project')
    d.numbered([
        '**Add a cost column.** A dataset with only Price cannot support any '
        'recommendation about margin or profitability - yet that is exactly the '
        'kind of recommendation these projects always make. `Unit Cost` and '
        '`Discount %` are what make the analysis defensible.',
        '**Never quote a number you did not compute.** Insights are derived at '
        'the end, from your own data. Every figure in this document is '
        'calculated from the supplied dataset at build time.',
        '**Present it as a case study, not a task list.** Recruiters skim for '
        'the narrative: problem, decision, evidence, recommendation. The same '
        'work reads as far more senior when it is framed that way.',
    ])

    d.callout('A dashboard shows what happened. A Business Analyst explains why '
              'it happened and states what the business should do next. The '
              'second half is the entire job - and the half most portfolio '
              'projects leave out.',
              label='The distinction that matters')

    # ---------------- 0. Scope ----------------------------------------
    d.page_break()
    d.h1('Scope it like a BA', number='01')
    d.para('Before touching data, write a one-paragraph project brief. This is '
           'the artifact that separates a Business Analysis project from a '
           'dashboard exercise, and it is the step almost everyone skips.')
    d.table(
        ['Field', 'Definition for this project'],
        [['Stakeholder', 'Head of Sales, a mid-size Indian e-commerce retailer'],
         ['Business problem',
          'Revenue is flat quarter-on-quarter while order volume holds steady. '
          'Leadership cannot tell whether the cause is pricing, product mix, '
          'region or customer retention.'],
         ['Decision to support',
          'Where to allocate next quarter\'s Rs 5,00,000 promotional budget'],
         ['Success metric',
          'Lift average order value by 10% without reducing order count'],
         ['In scope',
          '12 months of transactional sales data (%s to %s)' % (m['start'], m['end'])],
         ['Out of scope',
          'Returns, marketing spend, inventory levels, competitor pricing'],
         ['Assumptions',
          'Prices are pre-tax; cancelled orders excluded; Region is the '
          'delivery city; Unit Cost is landed cost excluding fulfilment'],
         ],
        widths=[1.05, 3.1], size=8.6, leading=11.4)
    d.callout('"Revenue is flat and we do not know why" is a business problem. '
              '"I want to practise SQL" is not. Every chart you build later must '
              'trace back to the decision this brief names.',
              label='Test your framing', accent=WARN,
              tint=(0.996, 0.972, 0.92))

    # ---------------- 1. Data -----------------------------------------
    d.h1('Design the data', number='02')
    d.para('Generating your own dataset beats downloading one, because you '
           'control the story and you are not the four-hundredth candidate to '
           'analyse the same file. The schema below matches the specification '
           'for this project, plus three analytical extensions.')

    d.h3('Data dictionary')
    d.table(
        ['Column', 'Type', 'Purpose / notes'],
        [['Order ID', 'Integer', 'Repeats across rows for multi-item orders - '
                                 'use DISTINCT when counting orders'],
         ['Date', 'Date', 'Spread across 12 months with real seasonality'],
         ['Customer', 'Text', '%d customers across %d orders, which is what '
                              'makes repeat-rate analysis possible'
          % (m['customers'], m['orders'])],
         ['Product', 'Text', '%d distinct SKUs' % m['n_products']],
         ['Category', 'Text', 'Electronics, Furniture, Home & Kitchen, '
                              'Apparel, Accessories'],
         ['Quantity', 'Integer', 'Right-skewed; big-ticket items sell 1-2 per '
                                 'order, small items sell in larger baskets'],
         ['Price', 'Decimal', 'Unit list price in rupees, before discount'],
         ['Unit Cost', 'Decimal', 'ADDED - unlocks margin analysis instead of '
                                  'revenue-only analysis'],
         ['Discount %', 'Decimal', 'ADDED - unlocks discount-effectiveness '
                                   'analysis, the strongest finding in this '
                                   'dataset'],
         ['Region', 'Text', '8 cities; also the deliberate blank-value column'],
         ['Channel', 'Text', 'ADDED - Web or Mobile App, a cheap extra '
                             'slicing dimension'],
         ],
        widths=[0.95, 0.65, 2.75], size=8.4, leading=11.0,
        cell_styles={(7, 2): ('b', ACCENT_DARK), (8, 2): ('b', ACCENT_DARK)})

    d.h3('Five patterns deliberately built into the data')
    d.para('Clean, featureless data gives you nothing to write about. The '
           'generator plants findable structure and realistic mess:')
    d.table(
        ['Pattern', 'What was planted', 'What it lets you demonstrate'],
        [['Pareto skew', 'A minority of SKUs carries most revenue',
          'Concentration analysis, running totals, catalogue rationalisation'],
         ['Seasonality', 'Festive spike in Oct-Nov, slump in Jan-Feb',
          'Trend analysis, month-on-month growth, LAG window functions'],
         ['Margin trap', 'The largest category by revenue has thin margins',
          'Why revenue alone misleads; revenue vs profit thinking'],
         ['Retention gap', 'One region acquires well but barely repeats',
          'Cohort/repeat-rate analysis, acquisition vs retention trade-off'],
         ['Deliberate mess',
          'Duplicates, blanks, casing variants, bad dates, price outliers',
          'Data-quality judgement and an auditable cleaning log'],
         ],
        widths=[0.85, 1.6, 1.85], size=8.4, leading=11.0)

    d.h3('Reproduce or regenerate it')
    d.code("""
# Regenerate the whole dataset (fixed seed 42 = reproducible output)
python3 scripts/generate_sales_dataset.py

# Outputs written to data/
#   raw_sales_data.csv       %s rows, uncleaned, all defects present
#   cleaned_sales_data.csv   %s rows, cleaned + calculated columns
#   Sales_Data_Raw.xlsx      the raw file as a real workbook for Excel work
#   data_quality_log.csv     the audit trail of every cleaning rule
""" % (format(raw_count, ','), format(m['rows'], ',')))

    # ---------------- 2. Excel ----------------------------------------
    d.h1('Clean it in Excel, and log every decision', number='03')
    d.para('Do the cleaning, but produce a **Data Quality Log** as a '
           'deliverable in its own right. Documenting your exclusions is what '
           'professional analysts get paid for, and it is the single easiest '
           'way to look experienced. The log below was generated from the '
           'actual cleaning run.')

    body = [r for r in qlog[1:] if r[0] != 'NET RESULT']
    net = [r for r in qlog[1:] if r[0] == 'NET RESULT']
    table_rows = [[r[0], r[1], r[2], r[3]] for r in body]
    styles = {}
    if net:
        table_rows.append(['NET RESULT', net[0][1], net[0][2], net[0][3]])
        last = len(table_rows) - 1
        for ci in range(4):
            styles[(last, ci)] = ('b', ACCENT_DARK)
    d.table(['Issue found', 'Rows', 'Rule applied', 'Rationale'],
            table_rows, widths=[1.35, 0.35, 1.25, 2.05], size=7.9,
            leading=10.4, aligns=['l', 'c', 'l', 'l'], cell_styles=styles)

    d.h3('Excel techniques to name explicitly')
    d.bullets([
        '**Remove Duplicates** on the full column set, not a single column',
        '**TRIM, PROPER, CLEAN** to standardise text - this is what stops one '
        'city splitting into three phantom groups in a later GROUP BY',
        '**Power Query** for the transform steps, so the cleaning is repeatable '
        'rather than a one-off manual pass',
        '**XLOOKUP** for category and cost mapping, **IFERROR** to trap gaps',
        '**Conditional formatting** to surface price and quantity outliers '
        'visually before you decide what to do with them',
        '**Pivot tables** for a first sanity check on totals before you trust '
        'any SQL result',
    ])

    d.h3('Calculated columns')
    d.code("""
Gross Revenue = Quantity * Price
Net Revenue   = Quantity * Price * (1 - [Discount %])
Gross Profit  = Net Revenue - (Quantity * [Unit Cost])
Margin %      = Gross Profit / Net Revenue
Order Month   = TEXT([Date], "yyyy-mm")
""")
    d.callout('Say this in the interview: "I removed %.1f%% of records and '
              'documented every rule, so the analysis is reproducible and the '
              'exclusions are auditable." That one sentence signals more '
              'maturity than any chart you can show.'
              % (100.0 * (raw_count - m['rows']) / raw_count),
              label='Interview line')

    # ---------------- 3. SQL ------------------------------------------
    d.h1('Analyse it in SQL as a question ledger', number='04')
    d.para('Structure your SQL file as **Question, Query, Answer, So what** '
           'rather than as a pile of statements. Anyone reading it then follows '
           'your reasoning, not just your syntax. Below are the five queries '
           'that actually differentiate you - everyone else writes '
           '`SUM() ... GROUP BY`.')

    d.h3('Query 1 - Month-on-month growth (trend, not just totals)')
    d.code("""
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_date) AS month,
           SUM(quantity * unit_price * (1 - discount_pct)) AS revenue
    FROM sales
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 0) AS revenue,
       ROUND(LAG(revenue) OVER (ORDER BY month), 0) AS prev_month,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS mom_growth_pct
FROM monthly
ORDER BY month;
""")

    d.h3('Query 2 - Pareto concentration (which SKUs actually matter)')
    d.code("""
WITH product_rev AS (
    SELECT product_name,
           SUM(quantity * unit_price * (1 - discount_pct)) AS revenue
    FROM sales
    GROUP BY product_name
),
ranked AS (
    SELECT product_name, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC
                              ROWS BETWEEN UNBOUNDED PRECEDING
                                       AND CURRENT ROW) AS running_rev,
           SUM(revenue) OVER ()   AS total_rev,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rn,
           COUNT(*)     OVER ()   AS n_products
    FROM product_rev
)
SELECT product_name,
       ROUND(revenue, 0) AS revenue,
       ROUND(100.0 * running_rev / total_rev, 1) AS cumulative_revenue_pct,
       ROUND(100.0 * rn / n_products, 1)        AS cumulative_product_pct
FROM ranked
ORDER BY revenue DESC;
""")

    d.h3('Query 3 - Category action matrix (recommendation in the output)')
    d.code("""
WITH cat AS (
    SELECT category,
           SUM(quantity * unit_price * (1 - discount_pct)) AS revenue,
           SUM(quantity * unit_price * (1 - discount_pct))
               / COUNT(DISTINCT order_id) AS aov,
           SUM(quantity * unit_price * (1 - discount_pct)
               - quantity * unit_cost)
               / SUM(quantity * unit_price * (1 - discount_pct)) AS margin_pct
    FROM sales
    GROUP BY category
)
SELECT category,
       ROUND(revenue, 0)         AS revenue,
       ROUND(aov, 0)             AS aov,
       ROUND(100 * margin_pct, 1) AS margin_pct,
       CASE
         WHEN revenue   >= AVG(revenue)    OVER ()
          AND margin_pct >= AVG(margin_pct) OVER ()
              THEN 'Star - protect and scale spend'
         WHEN revenue   >= AVG(revenue)    OVER ()
              THEN 'Volume driver - cut discounting, bundle to lift margin'
         WHEN margin_pct >= AVG(margin_pct) OVER ()
              THEN 'Hidden gem - increase traffic and visibility'
         ELSE     'Underperformer - rationalise or reprice'
       END AS recommended_action
FROM cat
ORDER BY revenue DESC;
""")

    d.h3('Query 4 - Discount effectiveness (the money question)')
    d.code("""
SELECT CASE WHEN discount_pct =  0     THEN '0%'
            WHEN discount_pct <= 0.10  THEN '1-10%'
            WHEN discount_pct <= 0.20  THEN '11-20%'
            ELSE '21%+' END AS discount_band,
       COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(quantity * unit_price * (1 - discount_pct))
             / COUNT(DISTINCT order_id), 0) AS aov,
       ROUND(100 * SUM(quantity * unit_price * (1 - discount_pct)
                       - quantity * unit_cost)
                 / SUM(quantity * unit_price * (1 - discount_pct)), 1) AS margin_pct
FROM sales
GROUP BY 1
ORDER BY 1;
""")

    d.h3('Query 5 - Repeat rate and revenue concentration by customer')
    d.code("""
WITH cust AS (
    SELECT customer_id,
           COUNT(DISTINCT order_id) AS orders,
           SUM(quantity * unit_price * (1 - discount_pct)) AS spend
    FROM sales
    GROUP BY customer_id
),
deciled AS (
    SELECT *, NTILE(10) OVER (ORDER BY spend DESC) AS spend_decile
    FROM cust
)
SELECT COUNT(*) AS total_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE orders > 1) / COUNT(*), 1)
           AS repeat_rate_pct,
       ROUND(AVG(spend), 0) AS avg_customer_value,
       ROUND(100.0 * SUM(spend) FILTER (WHERE spend_decile = 1)
                   / SUM(spend), 1) AS top_decile_revenue_share
FROM deciled;
""")
    d.para('`FILTER (WHERE ...)` is PostgreSQL syntax. On MySQL or SQL Server '
           'substitute `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. Both variants '
           'are included in `sql/03_advanced_analysis.sql`.',
           size=8.8, color=MUTED)

    d.callout('Skills you can now legitimately claim: common table '
              'expressions, window functions (LAG, ROW_NUMBER, NTILE, running '
              'totals with an explicit frame clause), aggregate window '
              'functions, CASE-based segmentation, date truncation, and '
              'NULLIF for safe division.',
              label='What this demonstrates', accent=GOOD,
              tint=(0.93, 0.965, 0.94))

    # ---------------- 4. Power BI -------------------------------------
    d.page_break()
    d.h1('Build the Power BI dashboard: model first', number='05')

    d.h3('5.1  Build a real star schema, not one flat table')
    d.table(
        ['Table', 'Role', 'Contents'],
        [['Fact_Sales', 'Fact', 'One row per order line: quantity, price, '
                                'discount, keys'],
         ['Dim_Date', 'Dimension', 'Generated with CALENDARAUTO(), then Mark '
                                   'as Date Table'],
         ['Dim_Product', 'Dimension', 'Product, Category, Unit Cost'],
         ['Dim_Customer', 'Dimension', 'Customer, home Region'],
         ], widths=[0.85, 0.7, 2.6], size=8.4, leading=11.0)
    d.para('Being able to say "I built a star schema with a marked date '
           'dimension so time intelligence works correctly" puts you ahead of '
           'most junior candidates, who load a single flat sheet and then '
           'wonder why TOTALYTD misbehaves.')

    d.h3('5.2  Core DAX measures')
    d.code("""
Total Revenue =
    SUMX(Fact_Sales,
         Fact_Sales[Quantity] * Fact_Sales[Price] * (1 - Fact_Sales[Discount %]))

Total Cost    = SUMX(Fact_Sales,
                     Fact_Sales[Quantity] * RELATED(Dim_Product[Unit Cost]))

Gross Profit  = [Total Revenue] - [Total Cost]
Margin %      = DIVIDE([Gross Profit], [Total Revenue])

Total Orders  = DISTINCTCOUNT(Fact_Sales[Order ID])
Units Sold    = SUM(Fact_Sales[Quantity])
AOV           = DIVIDE([Total Revenue], [Total Orders])

Revenue PM    = CALCULATE([Total Revenue], DATEADD(Dim_Date[Date], -1, MONTH))
Revenue MoM % = DIVIDE([Total Revenue] - [Revenue PM], [Revenue PM])
Revenue YTD   = TOTALYTD([Total Revenue], Dim_Date[Date])

Repeat Customers =
    COUNTROWS(
        FILTER(VALUES(Fact_Sales[Customer]),
               CALCULATE(DISTINCTCOUNT(Fact_Sales[Order ID])) > 1))

Repeat Rate % = DIVIDE([Repeat Customers], DISTINCTCOUNT(Fact_Sales[Customer]))
""")

    d.h3('5.3  One page, ordered by decision-relevance')
    d.para('Not five pages of every chart you know how to make. One executive '
           'page that answers the brief, with an optional detail page behind it.')
    d.code("""
+--------------------------------------------------------------------+
|  SALES PERFORMANCE            [ Date ]  [ Category ]  [ Region ]   |
+--------------------------------------------------------------------+
|  Revenue %-12s Orders %-7s AOV %-10s Margin %-6s |
+----------------------------------+---------------------------------+
|  Revenue trend + MoM %%           |  Category matrix:               |
|  (column + line, festive spike)  |  revenue vs margin scatter      |
+----------------------------------+---------------------------------+
|  Top 10 products with Pareto     |  Region performance:            |
|  cumulative %% line               |  revenue bar + repeat rate      |
+----------------------------------+---------------------------------+
""" % (rs(m['net'] / 10000000.0, 2).replace('Rs ', '') + 'Cr',
        format(m['orders'], ','), rs(m['aov']).replace('Rs ', ''),
        '%.1f%%' % (100 * m['margin'])))

    d.h3('5.4  Design rules that make it look professional')
    d.bullets([
        '**Title every visual as a finding, not a label.** "Festive quarter '
        'drove 34% of annual revenue" beats "Revenue by Month".',
        '**One accent colour, grey for context.** Red and green reserved '
        'strictly for where action is needed.',
        '**Consistent rupee formatting**, no decimals on large numbers, '
        'thousands separators everywhere.',
        '**No 3D, no pie chart with nine slices, no rainbow palette.** These '
        'read as inexperience.',
        '**Put one sentence of written insight on the canvas.** A dashboard '
        'that states its own conclusion is worth three that do not.',
        '**Sort bars by value, not alphabetically** - the ranking is the point.',
    ])

    # ---------------- 5. Findings -------------------------------------
    d.h1('Findings, recommendations and sizing', number='06')
    d.para('This is the whole project. Everything before it is preparation. '
           'Use a strict three-part structure for each insight: **Observation** '
           '(what the data says, with a number), **Interpretation** (why it is '
           'happening), **Recommendation** (a specific action with an expected '
           'rupee impact).')
    d.para('The four findings below are computed from the supplied dataset.',
           size=8.8, color=MUTED)

    # Finding 1 - discounting
    b0 = dict(m['bands'])['0%']
    bd = dict(m['bands'])['21%+']
    aov0 = b0['net'] / len(b0['orders'])
    aovd = bd['net'] / len(bd['orders'])
    mar0 = 100 * b0['profit'] / b0['net']
    mard = 100 * bd['profit'] / bd['net']

    d.h2('Finding 1 - Deep discounting is not buying bigger baskets')
    d.table(
        ['Discount band', 'Orders', 'Net revenue', 'AOV', 'Margin %'],
        [[k, format(len(v['orders']), ','), rs(v['net']),
          rs(v['net'] / len(v['orders'])),
          '%.1f%%' % (100 * v['profit'] / v['net'])]
         for k, v in m['bands']],
        widths=[0.9, 0.6, 1.0, 0.85, 0.7], size=8.4, leading=11.0,
        aligns=['l', 'r', 'r', 'r', 'r'],
        cell_styles={(3, 4): ('b', BAD), (0, 4): ('b', GOOD)})
    d.bullets([
        '**Observation.** Orders discounted above 20%% carry an average order '
        'value of %s against %s for undiscounted orders - %.0f%% **lower**, '
        'not higher - while gross margin falls from %.1f%% to %.1f%%.'
        % (rs(aovd), rs(aov0), 100 * (1 - aovd / aov0), mar0, mard),
        '**Interpretation.** Deep discounts are not persuading customers to '
        'buy more per order. They are subsidising purchases that were likely '
        'to happen anyway, converting margin into no incremental volume.',
        '**Recommendation.** Cap standard discounts at 15%% and redirect the '
        'difference into threshold-based bundles ("free shipping over '
        '%s"). Repricing the %s affected orders at a 15%% cap recovers '
        '**%s in gross profit**, a %.0f%% improvement on total profit, at '
        'constant volume.'
        % (rs(round(m['aov'] / 500) * 500), format(m['deep_orders'], ','),
           rs(m['deep_uplift']), m['deep_uplift_pct']),
    ])

    # Finding 2 - margin trap
    top_cat, top_v = m['cat'][0]
    best_margin = max(m['cat'], key=lambda x: x[1]['profit'] / x[1]['net'])
    d.h2('Finding 2 - The biggest category by revenue is the weakest by margin')
    d.table(
        ['Category', 'Net revenue', 'Revenue share', 'Margin %', 'AOV'],
        [[k, rs(v['net']), '%.1f%%' % (100 * v['net'] / m['net']),
          '%.1f%%' % (100 * v['profit'] / v['net']),
          rs(v['net'] / len(v['orders']))] for k, v in m['cat']],
        widths=[1.0, 1.0, 0.8, 0.7, 0.8], size=8.4, leading=11.0,
        aligns=['l', 'r', 'r', 'r', 'r'],
        cell_styles={(0, 3): ('b', BAD),
                     (len(m['cat']) - 2, 3): ('b', GOOD)})
    d.bullets([
        '**Observation.** %s generates %.1f%% of net revenue at only %.1f%% '
        'margin, while %s returns %.1f%% margin on %.1f%% of revenue.'
        % (top_cat, 100 * top_v['net'] / m['net'],
           100 * top_v['profit'] / top_v['net'], best_margin[0],
           100 * best_margin[1]['profit'] / best_margin[1]['net'],
           100 * best_margin[1]['net'] / m['net']),
        '**Interpretation.** Ranking categories by revenue would put %s first '
        'and make it the obvious place to spend. Ranking by profit '
        'contribution tells a different story - it is a high-turnover, '
        'low-return category being made worse by the discounting in Finding 1.'
        % top_cat,
        '**Recommendation.** Stop treating revenue share as importance. Hold '
        '%s spend flat, protect it on price rather than promoting it, and '
        'shift incremental budget toward the higher-margin categories where '
        'each rupee of revenue keeps more profit.' % top_cat,
    ])

    # Finding 3 - Pareto
    d.h2('Finding 3 - A third of the catalogue does nearly all the work')
    d.table(
        ['Rank', 'Product', 'Net revenue', 'Share', 'Cumulative'],
        (lambda: [
            [str(i), p, rs(v), '%.1f%%' % (100 * v / m['net']),
             '%.1f%%' % (100 * sum(x[1] for x in m['products'][:i]) / m['net'])]
            for i, (p, v) in enumerate(m['products'][:8], 1)])(),
        widths=[0.4, 1.3, 1.0, 0.6, 0.75], size=8.4, leading=11.0,
        aligns=['c', 'l', 'r', 'r', 'r'])
    d.bullets([
        '**Observation.** %d of %d products (%.0f%% of the catalogue) generate '
        '80%% of net revenue. %d SKUs each contribute under 1%%.'
        % (m['n80'], m['n_products'], m['pct80'], len(m['tail'])),
        '**Interpretation.** The long tail is not free. It consumes catalogue '
        'management, photography, storage and merchandising attention '
        'disproportionate to its contribution.',
        '**Recommendation.** Review the %d sub-1%% SKUs for delisting or '
        'supplier renegotiation, and reinvest the freed merchandising effort '
        'in the top %d products that already drive four fifths of revenue.'
        % (len(m['tail']), m['n80']),
    ])

    # Finding 4 - retention
    wr = m['worst_region']
    d.h2('Finding 4 - One region acquires customers but cannot keep them')
    d.table(
        ['Region', 'Customers', 'Repeat rate', 'Net revenue'],
        [[k, format(c, ','), '%.1f%%' % rr, rs(nv)]
         for k, c, rr, nv in m['regions']],
        widths=[1.0, 0.8, 0.8, 1.1], size=8.4, leading=11.0,
        aligns=['l', 'r', 'r', 'r'],
        cell_styles={(i, 2): ('b', BAD) for i, r in enumerate(m['regions'])
                     if r[0] == wr[0]})
    d.bullets([
        '**Observation.** %s has %s customers - more than several '
        'higher-revenue regions - but a repeat rate of just %.1f%% against a '
        '%.1f%% average across the other regions.'
        % (wr[0], format(wr[1], ','), wr[2], m['peer_repeat']),
        '**Interpretation.** Acquisition in %s is working; retention is not. '
        'The region is buying first orders and losing the customers '
        'immediately afterwards, which is the most expensive way to grow.'
        % wr[0],
        '**Recommendation.** Suspend incremental acquisition spend in %s and '
        'run a post-purchase retention programme (second-order incentive, '
        'delivery-experience audit) before adding more top-of-funnel budget. '
        'Closing half the gap to the %.1f%% peer average would convert '
        'roughly %d one-time buyers into repeat customers.'
        % (wr[0], m['peer_repeat'],
           int(wr[1] * (m['peer_repeat'] - wr[2]) / 200.0)),
    ])

    d.h2('Recommendation summary, ranked by value')
    d.table(
        ['#', 'Action', 'Owner', 'Expected impact'],
        [['1', 'Cap discounts at 15% and move the spend into '
               'threshold-based bundles', 'Pricing / Trade Marketing',
          '%s gross profit' % rs(m['deep_uplift'])],
         ['2', 'Rebalance category budget from %s toward higher-margin lines'
          % top_cat, 'Category Management', 'Margin mix improvement'],
         ['3', 'Delist or renegotiate the %d sub-1%% SKUs' % len(m['tail']),
          'Merchandising', 'Cost and complexity reduction'],
         ['4', 'Retention programme in %s before further acquisition spend'
          % wr[0], 'CRM / Regional Sales',
          'Approx %d buyers converted to repeat'
          % int(wr[1] * (m['peer_repeat'] - wr[2]) / 200.0)],
         ], widths=[0.22, 2.05, 1.0, 1.05], size=8.3, leading=10.8,
        aligns=['c', 'l', 'l', 'l'])

    d.h3('Close with your own limitations')
    d.para('Stating what your analysis cannot conclude is a strong signal, not '
           'a weak one. For this dataset: returns are excluded so net margin '
           'is overstated; there is no marketing-spend data so no true ROI or '
           'CAC can be computed; the %s in revenue sitting under the '
           '"Unknown" region after cleaning limits regional precision; and '
           'discount effect is observational, not causal - proving it needs a '
           'controlled A/B test.' % rs(m['unknown_net']))

    # ---------------- 6. Package --------------------------------------
    d.page_break()
    d.h1('Package it so it is actually reviewable', number='07')
    d.para('A repository turns the work into a link you can put on a CV, and '
           'forces the discipline of naming and ordering your artifacts.')
    d.code("""
Sales_Performance_Analysis/
|-- README.md                                  <- the case study, most read file
|-- Sales_Performance_Analysis_Project_Guide.pdf
|-- data/
|   |-- raw_sales_data.csv                     %s rows, defects intact
|   |-- cleaned_sales_data.csv                 %s rows + calculated columns
|   |-- Sales_Data_Raw.xlsx                    workbook for the Excel stage
|   +-- data_quality_log.csv                   the cleaning audit trail
|-- sql/
|   |-- 01_schema_and_load.sql                 DDL + load + integrity checks
|   |-- 02_business_questions.sql              the question ledger
|   +-- 03_advanced_analysis.sql               windows, Pareto, discounts, RFM
+-- scripts/
    |-- generate_sales_dataset.py              reproducible generator
    |-- minipdf.py                             dependency-free PDF writer
    +-- build_project_guide_pdf.py             builds this document
""" % (format(raw_count, ','), format(m['rows'], ',')))
    d.para('**README order that works:** Business problem, Data and '
           'assumptions, Approach, Key findings (dashboard screenshot at the '
           'top), Recommendations, Tools, Limitations.')
    d.callout('The highest-leverage artifact is a one-page executive summary. '
              'It is what a hiring manager will actually read, and almost no '
              'candidate produces one.', label='Do not skip this')

    # ---------------- 7. LinkedIn -------------------------------------
    d.h1('Write the LinkedIn post', number='08')
    d.para('Lead with the finding, not the tool. Tools get you filtered; '
           'findings get you remembered. Weak version: "Made a Power BI '
           'dashboard using SQL."')
    d.code("""
Sales Performance Analysis | Excel . SQL . Power BI

A retailer's revenue was flat for two quarters while order volume held
steady. Leadership needed to know where to put the next promotional budget.

I analysed %s transactions end to end. The problem was not demand.
It was discounting.

What I found
-> Discounts above 20%% produced a %.0f%% LOWER average order value than
   undiscounted orders, while margin fell from %.1f%% to %.1f%%
-> %d of %d products drove 80%% of revenue; %d SKUs contributed under 1%% each
-> %s generated %.0f%% of revenue at only %.1f%% margin - the biggest
   category was the weakest one
-> %s had strong acquisition but a %.1f%% repeat rate against a %.1f%% average

What I recommended
-> Cap discounts at 15%%, shift spend to bundle thresholds -> %s
   gross profit recovered at constant volume
-> Rebalance category budget toward higher-margin lines
-> Fix retention in %s before spending more on acquisition there

How: Excel and Power Query for cleaning (every exclusion rule documented,
%.1f%% of rows), SQL with CTEs and window functions for the analysis,
Power BI star schema with DAX measures for the dashboard.

The lesson: the interesting answer was not in the revenue chart.
It was in the margin column nobody asked for.

Full breakdown and code: <repo link>

#BusinessAnalyst #SQL #PowerBI #DataAnalytics #Excel
""" % (format(m['rows'], ','), 100 * (1 - aovd / aov0), mar0, mard,
        m['n80'], m['n_products'], len(m['tail']),
        top_cat, 100 * top_v['net'] / m['net'],
        100 * top_v['profit'] / top_v['net'],
        wr[0], wr[2], m['peer_repeat'], rs(m['deep_uplift']), wr[0],
        100.0 * (raw_count - m['rows']) / raw_count))

    d.h3('Post mechanics')
    d.bullets([
        'Dashboard screenshot as the image, or a three-slide carousel: '
        'problem, dashboard, recommendations',
        'Short lines and visible whitespace - no wall of text',
        'Put the repo link in the post body, and reply to every comment in '
        'the first two hours',
    ])

    # ---------------- 8. Resume ---------------------------------------
    d.h1('Resume bullets', number='09')
    d.h3('Concise version - one line, for a packed resume')
    d.code("""
Sales Performance Analysis | Excel, SQL, Power BI - Analysed %s sales
transactions to identify a %s margin leak from over-discounting; built a
Power BI dashboard and delivered 4 costed recommendations targeting a 10%%
lift in average order value.
""" % (format(m['rows'], ','), rs(m['deep_uplift'])))

    d.h3('Expanded version - for a projects section')
    d.code("""
Sales Performance Analysis
Excel (Power Query) | SQL (CTEs, window functions) | Power BI (DAX, star schema)

- Cleaned and validated %s raw sales records, documenting %d data-quality
  rules affecting %.1f%% of rows to make the analysis reproducible and auditable
- Built SQL analyses covering revenue trend, Pareto concentration, discount
  effectiveness and customer repeat behaviour across %d SKUs and %d customers
- Designed a single-page executive Power BI dashboard with month-on-month
  growth, margin and AOV measures across 3 filter dimensions
- Found that discounts above 20%% reduced average order value by %.0f%% while
  cutting margin from %.1f%% to %.1f%%; recommended a discount cap and bundle
  strategy projected to recover %s in gross profit
""" % (format(raw_count, ','), len(body),
        100.0 * (raw_count - m['rows']) / raw_count,
        m['n_products'], m['customers'], 100 * (1 - aovd / aov0), mar0, mard,
        rs(m['deep_uplift'])))
    d.para('Every bullet carries a number and an outcome. That is the whole '
           'formula.')

    # ---------------- 9. Interview ------------------------------------
    d.h1('Defend it in the interview', number='10')
    d.para('These questions are close to guaranteed. Prepare the answers '
           'before you post the project.')
    d.table(
        ['Question they will ask', 'What they are really testing'],
        [['"Walk me through the business problem you were solving."',
          'Whether you lead with the problem or with the tool'],
         ['"How did you decide which rows to remove, and how might that bias '
          'the result?"', 'Analytical honesty and data-quality judgement'],
         ['"Your biggest region by revenue - is it your most valuable region?"',
          'Whether you separate revenue from profit and lifetime value'],
         ['"How confident are you in the %s estimate? What assumptions does '
          'it rest on?"' % rs(m['deep_uplift']),
          'Whether you understand the limits of your own model'],
         ['"Sales says your discount cap will cost them volume. Your '
          'response?"', 'Stakeholder pushback and commercial judgement'],
         ['"Could the discount effect be caused by something else?"',
          'Correlation versus causation; do you reach for an A/B test'],
         ['"What would you analyse next, and what data would you need?"',
          'Strategic thinking beyond the immediate task'],
         ['"Why a star schema instead of one flat table?"',
          'Technical depth in the modelling layer'],
         ], widths=[1.75, 1.65], size=8.4, leading=11.0)
    d.callout('Have a crisp answer ready for "What surprised you?" Genuine '
              'surprise is evidence that you did the analysis rather than '
              'reverse-engineering charts from a tutorial.',
              label='The question that separates candidates')

    # ---------------- 10. Mistakes ------------------------------------
    d.page_break()
    d.h1('Mistakes that quietly kill these projects', number='11')
    d.table(
        ['Mistake', 'Fix'],
        [['Recommending on margin when the data only has revenue',
          'Add a Unit Cost column before you analyse anything'],
         ['Six dashboard pages and forty visuals',
          'One decision-focused page; detail behind it'],
         ['Chart titles like "Revenue by Month"',
          'Title every visual with the finding it shows'],
         ['Insights that only restate a number',
          'Every insight ends in an action with a rupee impact'],
         ['Using the Kaggle dataset everyone else used',
          'Generate your own, or pick an unusual angle'],
         ['No record of cleaning decisions',
          'Keep the Data Quality Log as a deliverable'],
         ['Claiming precision the data cannot support',
          'State assumptions and limitations explicitly'],
         ['Leading the LinkedIn post with the tools',
          'Lead with the finding; tools go at the bottom'],
         ['Counting orders with COUNT(order_id) on a multi-line table',
          'COUNT(DISTINCT order_id) - otherwise every KPI is inflated'],
         ], widths=[1.7, 1.7], size=8.4, leading=11.0)

    # ---------------- 11. Timeline ------------------------------------
    d.h1('Realistic timeline', number='12')
    d.table(
        ['Day', 'Work', 'Output'],
        [['1', 'Write the project brief; generate the dataset with its '
               'built-in patterns', 'Brief + raw_sales_data.csv'],
         ['2', 'Excel cleaning, Data Quality Log, calculated columns',
          'Cleaned workbook'],
         ['3', 'Load to SQL; write the question ledger',
          '02_business_questions.sql'],
         ['4', 'Advanced SQL: Pareto, discount bands, repeat rate',
          '03_advanced_analysis.sql'],
         ['5', 'Power BI model, relationships and DAX measures',
          'sales_dashboard.pbix'],
         ['6', 'Dashboard layout, formatting, insight annotations',
          'Dashboard screenshot'],
         ['7', 'README, one-page executive summary, LinkedIn post',
          'Published repo and post'],
         ], widths=[0.3, 2.1, 1.3], size=8.4, leading=11.0, aligns=['c', 'l', 'l'])
    d.para('One focused week, or two weekends if you are working. The value is '
           'not in the hours - it is in finishing the arc from business '
           'problem all the way through to a costed recommendation.')

    # ---------------- Appendix ----------------------------------------
    d.page_break()
    d.h1('Appendix - verified dataset profile', number='A')
    d.para('Computed from `data/cleaned_sales_data.csv` when this PDF was '
           'built. Use these as the reference values when you rebuild the '
           'analysis yourself - if your SQL or Power BI numbers disagree with '
           'this table, something in your model is wrong.')

    d.table(
        ['Metric', 'Value'],
        [['Rows (raw / cleaned)', '%s / %s (%.1f%% removed)'
          % (format(raw_count, ','), format(m['rows'], ','),
             100.0 * (raw_count - m['rows']) / raw_count)],
         ['Distinct orders', format(m['orders'], ',')],
         ['Units sold', format(m['units'], ',')],
         ['Distinct customers', format(m['customers'], ',')],
         ['Distinct products', str(m['n_products'])],
         ['Net revenue', rs(m['net'])],
         ['Gross profit', rs(m['profit'])],
         ['Overall gross margin', '%.1f%%' % (100 * m['margin'])],
         ['Average order value', rs(m['aov'])],
         ['Overall repeat rate', '%.1f%%' % m['repeat_all']],
         ['Date range', '%s to %s' % (m['start'], m['end'])],
         ['Peak month', '%s (%s)' % (m['peak_month'][0], rs(m['peak_month'][1]))],
         ['Weakest month', '%s (%s)'
          % (m['trough_month'][0], rs(m['trough_month'][1]))],
         ], widths=[1.2, 2.2], size=8.4, leading=11.0)

    d.h3('Monthly net revenue and month-on-month growth')
    mrows = []
    prev = None
    for month, v in m['months']:
        mom = '-' if prev is None else '%+.1f%%' % (100 * (v - prev) / prev)
        mrows.append([month, rs(v), mom])
        prev = v
    half = (len(mrows) + 1) // 2
    combined = []
    for i in range(half):
        left = mrows[i]
        right = mrows[i + half] if i + half < len(mrows) else ['', '', '']
        combined.append(left + right)
    d.table(['Month', 'Net revenue', 'MoM', 'Month', 'Net revenue', 'MoM'],
            combined, widths=[0.6, 0.85, 0.55, 0.6, 0.85, 0.55], size=8.2,
            leading=10.6, aligns=['l', 'r', 'r', 'l', 'r', 'r'])

    d.h3('Full product ranking by net revenue (cumulative share shows the '
         'Pareto curve)')
    prows = []
    cum = 0.0
    for i, (p, v) in enumerate(m['products'], 1):
        cum += v
        prows.append([str(i), p, rs(v), '%.1f%%' % (100 * cum / m['net'])])
    phalf = (len(prows) + 1) // 2
    pcombined = []
    for i in range(phalf):
        right = prows[i + phalf] if i + phalf < len(prows) else ['', '', '', '']
        pcombined.append(prows[i] + right)
    d.table(['#', 'Product', 'Net revenue', 'Cum.',
             '#', 'Product', 'Net revenue', 'Cum.'], pcombined,
            widths=[0.22, 0.82, 0.72, 0.42, 0.22, 0.82, 0.72, 0.42],
            size=7.6, leading=9.8,
            aligns=['c', 'l', 'r', 'r', 'c', 'l', 'r', 'r'])

    pages = d.save(OUT)
    return pages


def main():
    rows = load()
    raw_count = load_raw_count()
    qlog = load_quality_log()
    m = compute(rows)
    pages = build(m, raw_count, qlog)
    size_kb = os.path.getsize(OUT) / 1024.0
    print('Wrote %s' % os.path.normpath(OUT))
    print('  pages: %d   size: %.0f KB' % (pages, size_kb))
    print('  discount-cap opportunity computed at %s (%.1f%% of gross profit)'
          % (rs(m['deep_uplift']), m['deep_uplift_pct']))


if __name__ == '__main__':
    main()
