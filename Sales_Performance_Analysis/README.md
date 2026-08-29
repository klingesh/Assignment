# Sales Performance Analysis

**Business Analyst portfolio project — Excel · SQL · Power BI**

A twelve-month e-commerce sales analysis that runs the full Business Analyst arc:
business problem → clean data → analysis → visualisation → costed recommendation.

---

## The business problem

A mid-size Indian e-commerce retailer's revenue was flat quarter-on-quarter while
order volume held steady. Leadership could not tell whether the cause was pricing,
product mix, region or customer retention — and needed to decide where to place
next quarter's ₹5,00,000 promotional budget.

| | |
|---|---|
| **Stakeholder** | Head of Sales |
| **Decision to support** | Where to allocate the next promotional budget |
| **Success metric** | Lift average order value 10% without reducing order count |
| **In scope** | 1,577 transaction lines, 2025-09-01 to 2026-08-29 |
| **Out of scope** | Returns, marketing spend, inventory, competitor pricing |
| **Assumptions** | Prices pre-tax; cancelled orders excluded; Region = delivery city; Unit Cost is landed cost excluding fulfilment |

---

## Headline numbers

| Metric | Value |
|---|---|
| Net revenue | ₹1,93,33,556 |
| Gross profit | ₹44,50,106 |
| Gross margin | 23.0% |
| Orders | 1,145 |
| Units sold | 2,553 |
| Customers | 639 |
| Average order value | ₹16,885 |
| Repeat rate | 35.4% |
| Products | 32 across 5 categories |

---

## Key findings

### 1. Deep discounting is not buying bigger baskets

| Discount band | Orders | AOV | Gross margin |
|---|---:|---:|---:|
| 0% | 240 | ₹15,280 | **36.1%** |
| 1–10% | 461 | ₹13,645 | 29.4% |
| 11–20% | 418 | ₹13,779 | 18.8% |
| 21%+ | 320 | ₹11,301 | **5.4%** |

Average order value **falls 26%** as discounting deepens, while margin collapses
from 36.1% to 5.4%. The discounts are not persuading anyone to buy more — the
margin is being given away for nothing. ₹30,83,294 of list value (13.8% of gross
revenue) was discounted away over the period, which is more than the entire
Furniture category's gross profit.

### 2. The biggest category by revenue is the weakest by margin

| Category | Net revenue | Share | Margin | Rank by revenue | Rank by margin |
|---|---:|---:|---:|:---:|:---:|
| Electronics | ₹1,20,23,186 | 62.2% | 14.9% | 1 | **5** |
| Furniture | ₹43,52,378 | 22.5% | 38.1% | 2 | 3 |
| Home & Kitchen | ₹19,78,660 | 10.2% | 26.4% | 3 | 4 |
| Apparel | ₹6,85,250 | 3.5% | **49.5%** | 4 | 1 |
| Accessories | ₹2,94,082 | 1.5% | 46.1% | 5 | 2 |

Electronics ranks **first on revenue and last on margin**. Allocating budget by
revenue rank would point the entire spend at the least profitable category in the
business.

### 3. A third of the catalogue does nearly all the work

10 of 32 products (31% of the catalogue) generate 80% of net revenue. 16 SKUs each
contribute under 1%. Top five: Laptop (21.7%), Phone (13.9%), Smart TV (13.1%),
Sofa Set (7.9%), Tablet (5.7%) — 62.4% of revenue between them.

### 4. One region acquires customers but cannot keep them

| Region | Customers | Repeat rate | Net revenue |
|---|---:|---:|---:|
| Chennai | 153 | 39.2% | ₹53,08,066 |
| Bengaluru | 95 | 38.9% | ₹24,81,696 |
| Coimbatore | 79 | 40.5% | ₹23,97,824 |
| Madurai | 84 | 40.5% | ₹23,05,638 |
| **Salem** | **104** | **12.5%** | ₹21,68,000 |
| Hyderabad | 59 | 42.4% | ₹19,99,276 |
| Trichy | 34 | 44.1% | ₹12,82,820 |
| Kochi | 24 | 41.7% | ₹10,19,430 |

Salem has more customers than four higher-revenue regions but a repeat rate of
12.5% against a 41.0% peer average. Acquisition works there; retention does not.

> Customers are attributed to their most frequent non-Unknown region, so the
> `Unknown` bucket created during cleaning cannot contaminate retention figures.

---

## Recommendations

| # | Action | Owner | Expected impact |
|---|---|---|---|
| 1 | Cap standard discounts at 15%; redirect the difference into threshold-based bundles | Pricing / Trade Marketing | **₹7,69,336 gross profit** (+17.3%) across 496 affected orders |
| 2 | Rebalance category budget away from Electronics toward higher-margin lines | Category Management | Margin mix improvement |
| 3 | Delist or renegotiate the 16 sub-1% SKUs | Merchandising | Cost and complexity reduction |
| 4 | Retention programme in Salem before any further acquisition spend | CRM / Regional Sales | ~14 one-time buyers converted to repeat |

### Limitations

Stated up front rather than waiting to be asked:

- Returns are excluded, so net margin is **overstated**.
- No marketing-spend data, so no true ROI or CAC can be computed.
- ₹3,70,806 of revenue sits under `Unknown` region after cleaning, limiting
  regional precision.
- The discount effect is **observational, not causal**. The ₹7,69,336 figure
  assumes constant volume; proving it requires a controlled A/B test.

---

## What's in this repository

```
Sales_Performance_Analysis/
├── README.md                                     ← this case study
├── Sales_Performance_Analysis_Project_Guide.pdf  ← 12-page project guide
├── data/
│   ├── raw_sales_data.csv          1,626 rows, all data-quality defects intact
│   ├── cleaned_sales_data.csv      1,577 rows + calculated columns
│   ├── Sales_Data_Raw.xlsx         raw data as a workbook for the Excel stage
│   └── data_quality_log.csv        audit trail of every cleaning rule
├── sql/
│   ├── 01_schema_and_load.sql      DDL, load, 8 integrity checks
│   ├── 02_business_questions.sql   13-question ledger with verified answers
│   └── 03_advanced_analysis.sql    windows, Pareto, discount sizing, RFM
└── scripts/
    ├── generate_sales_dataset.py   reproducible generator (seed 42)
    ├── minipdf.py                  dependency-free PDF writer
    └── build_project_guide_pdf.py  builds the PDF from the data
```

### Dataset schema

| Column | Notes |
|---|---|
| `Order ID` | Repeats across rows for multi-item orders — **always use `COUNT(DISTINCT order_id)`** |
| `Date` | 12 months with real seasonality |
| `Customer` | 639 customers across 1,145 orders |
| `Product`, `Category` | 32 SKUs, 5 categories |
| `Quantity`, `Price` | Right-skewed quantity; rupee list price |
| `Unit Cost` | *Added* — makes margin analysis possible |
| `Discount %` | *Added* — drives the strongest finding in the dataset |
| `Region`, `Channel` | 8 cities; Web / Mobile App |

The cleaned file adds `Gross Revenue`, `Net Revenue`, `Gross Profit`, `Margin %`
and `Order Month`.

### Patterns deliberately built into the data

Featureless data gives you nothing to write about. The generator plants findable
structure and realistic mess:

| Pattern | What it lets you demonstrate |
|---|---|
| Pareto skew | Running totals, concentration analysis, catalogue rationalisation |
| Seasonality (Oct–Nov spike, Jan–Feb slump) | Trend analysis, `LAG` month-on-month growth |
| Margin trap (biggest category, thinnest margin) | Revenue vs profit thinking |
| Retention gap (one weak region) | Repeat-rate analysis, acquisition vs retention |
| Deliberate mess | Data-quality judgement and an auditable cleaning log |

### Data quality log

Generated from the actual cleaning run — 1,626 → 1,577 rows, **3.0% removed**:

| Issue found | Rows | Rule applied |
|---|---:|---|
| Exact duplicate rows | 41 | Removed |
| Inconsistent Region casing / whitespace | 62 | `TRIM` + `PROPER` |
| Blank Region | 28 | Set to `Unknown` |
| Mixed date formats (DD-MM-YYYY) | 20 | Normalised to `YYYY-MM-DD` |
| Negative Quantity | 5 | Excluded and flagged |
| Order Date later than today | 3 | Excluded |
| Price outliers (10× product median) | 2 | Corrected to product median |

---

## Reproducing this

```bash
# Regenerate the dataset (fixed seed 42 — deterministic output)
python3 scripts/generate_sales_dataset.py

# Rebuild the PDF guide (recomputes every figure from the CSV)
cd scripts && python3 build_project_guide_pdf.py
```

Both scripts use **only the Python standard library** — no pandas, no reportlab,
nothing to install. `minipdf.py` is a small PDF writer built for this project,
with real Adobe base-14 font metrics so text wrapping is accurate.

Load the data and verify your environment:

```sql
-- PostgreSQL
\i sql/01_schema_and_load.sql   -- all 8 integrity checks must return PASS
\i sql/02_business_questions.sql
\i sql/03_advanced_analysis.sql
```

Every query has been executed against the shipped dataset and every figure quoted
in the SQL comments, the README and the PDF is reproducible from
`data/cleaned_sales_data.csv`. **No number in this project is invented.**

---

## Still to do (the parts worth doing yourself)

The analysis and data layers are complete. Two artifacts are deliberately left
for you to build, because they are what you will be asked about in an interview:

1. **`data_cleaning.xlsx`** — walk the raw CSV through the seven cleaning rules
   in Excel/Power Query yourself, and keep the Data Quality Log as a tab.
2. **`sales_dashboard.pbix`** — a single-page Power BI dashboard. Section 05 of
   the PDF guide gives the star schema, the full DAX measure set and the page
   layout.

Then add a one-page executive summary PDF. It is the artifact a hiring manager
will actually read, and almost no candidate produces one.

---

## Tools

**Excel** (Power Query, `TRIM`/`PROPER`, `XLOOKUP`, pivot tables) ·
**SQL** (CTEs, window functions — `LAG`, `ROW_NUMBER`, `NTILE`, `FIRST_VALUE`,
running totals with explicit frames) ·
**Power BI** (star schema, DAX, time intelligence)
