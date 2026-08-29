#!/usr/bin/env python3
"""
Sales Performance Analysis - dataset generator
==============================================

Builds a realistic e-commerce transactional dataset matching the column
specification for the project brief:

    Order ID | Date | Customer | Product | Category | Quantity | Price | Region

plus three analytical extensions that make genuine Business Analysis possible:

    Unit Cost   -> enables margin analysis (not just revenue)
    Discount %  -> enables discount-effectiveness analysis
    Channel     -> a cheap extra dimension for slicing

Deliberate structure is baked into the data so there is something real to find:

  1. Pareto skew        - a small share of the catalogue drives most revenue
  2. Seasonality        - festive spike (Oct-Nov), post-festive dip (Jan-Feb)
  3. A margin trap      - a high-revenue category with thin margins
  4. A retention gap    - a region with good acquisition but poor repeat rate
  5. Deliberate dirt    - duplicates, blanks, casing, outliers, bad dates

Outputs (written to ../data/):
    raw_sales_data.csv          uncleaned, with all injected data-quality issues
    cleaned_sales_data.csv      cleaned + calculated revenue/profit columns
    Sales_Data_Raw.xlsx         the raw file as a real .xlsx for Excel work
    data_quality_log.csv        audit log of every cleaning rule applied

Standard library only - no third-party dependencies.
"""

import csv
import os
import random
import zipfile
from datetime import date, timedelta

SEED = 42
random.seed(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

# The analysis window: 12 full months ending at the project date.
START_DATE = date(2025, 9, 1)
END_DATE = date(2026, 8, 29)
TODAY = date(2026, 8, 29)

N_ORDERS = 1150          # orders; multi-item orders push row count to ~1550

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

# product -> (category, list_price, popularity_weight)
# Popularity weight combined with price is what creates the Pareto curve.
PRODUCTS = {
    # Electronics - big ticket, high revenue share, thin margin after discount
    "Laptop":             ("Electronics",     50000, 32),
    "Smart TV":           ("Electronics",     35000, 25),
    "Phone":              ("Electronics",     20000, 54),
    "Tablet":             ("Electronics",     18000, 22),
    "Smartwatch":         ("Electronics",      8000, 30),
    "Bluetooth Speaker":  ("Electronics",      3500, 22),
    "Headphones":         ("Electronics",      2500, 30),
    "Power Bank":         ("Electronics",      1500, 18),
    # Furniture - healthy margin, lower volume
    "Sofa Set":           ("Furniture",       32000, 16),
    "Wardrobe":           ("Furniture",       22000, 14),
    "Bed Frame":          ("Furniture",       18000, 13),
    "Office Chair":       ("Furniture",        7500, 20),
    "Study Table":        ("Furniture",        6000, 16),
    "Bookshelf":          ("Furniture",        4500, 11),
    # Home & Kitchen
    "Water Purifier":     ("Home & Kitchen",  12000, 15),
    "Microwave":          ("Home & Kitchen",   9500, 12),
    "Mixer Grinder":      ("Home & Kitchen",   4200, 20),
    "Cookware Set":       ("Home & Kitchen",   2800, 14),
    "Dinner Set":         ("Home & Kitchen",   1900, 10),
    "Pressure Cooker":    ("Home & Kitchen",   1600, 13),
    # Apparel - long tail, high volume, small value
    "Jacket":             ("Apparel",          2800, 12),
    "Saree":              ("Apparel",          3500,  9),
    "Jeans":              ("Apparel",          1800, 18),
    "Formal Shirt":       ("Apparel",          1400, 14),
    "Kurta":              ("Apparel",          1200, 12),
    "T-Shirt":            ("Apparel",           700, 22),
    # Accessories - the long tail that contributes almost nothing
    "Backpack":           ("Accessories",      1500, 12),
    "Sunglasses":         ("Accessories",      1300,  8),
    "Laptop Sleeve":      ("Accessories",       900,  7),
    "Wallet":             ("Accessories",       800, 10),
    "Belt":               ("Accessories",       600,  8),
    "Phone Case":         ("Accessories",       400, 14),
}

# Cost as a share of list price. Electronics is the margin trap: high revenue,
# high cost base, and it attracts the deepest discounting.
COST_RATIO = {
    "Electronics":    0.72,
    "Home & Kitchen": 0.64,
    "Furniture":      0.56,
    "Accessories":    0.48,
    "Apparel":        0.44,
}

# region -> (order_weight, expected_orders_per_customer)
# Salem is the retention gap: decent acquisition, almost no repeat purchasing.
REGIONS = {
    "Chennai":    (26, 4.4),
    "Bengaluru":  (17, 4.0),
    "Coimbatore": (14, 3.9),
    "Madurai":    (12, 3.7),
    "Hyderabad":  (11, 3.4),
    "Salem":      (10, 1.3),
    "Trichy":      (6, 3.4),
    "Kochi":       (4, 3.1),
}

# Orders-per-customer distributions used to build each region's customer pool.
# This is what actually controls the repeat rate.
REPEAT_PROFILE_NORMAL = ([1, 2, 3, 4, 5, 6, 8], [60, 16, 9, 6, 4, 3, 2])
REPEAT_PROFILE_CHURNY = ([1, 2, 3], [86, 12, 2])

CHANNELS = ["Web", "Mobile App"]

# Monthly demand multipliers: festive spike then a new-year slump.
SEASONALITY = {
    (2025,  9): 1.00,
    (2025, 10): 1.85,   # festive season
    (2025, 11): 1.70,   # festive tail
    (2025, 12): 1.20,
    (2026,  1): 0.68,   # post-festive dip
    (2026,  2): 0.72,
    (2026,  3): 0.95,
    (2026,  4): 1.05,
    (2026,  5): 1.10,
    (2026,  6): 0.98,
    (2026,  7): 1.02,
    (2026,  8): 1.08,
}

COLUMNS = ["Order ID", "Date", "Customer", "Product", "Category",
           "Quantity", "Price", "Unit Cost", "Discount %", "Region", "Channel"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def weighted_choice(mapping):
    """mapping: key -> weight."""
    keys = list(mapping.keys())
    weights = [mapping[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def build_date_pool():
    """All dates in the window, weighted by month seasonality and weekday."""
    days, weights = [], []
    d = START_DATE
    while d <= END_DATE:
        w = SEASONALITY.get((d.year, d.month), 1.0)
        # Weekends run hotter for retail.
        if d.weekday() >= 5:
            w *= 1.35
        days.append(d)
        weights.append(w)
        d += timedelta(days=1)
    return days, weights


def pick_quantity(price):
    """Cheap items sell in larger baskets; big-ticket items sell 1-2 at a time."""
    if price >= 18000:
        return random.choices([1, 2], weights=[92, 8])[0]
    if price >= 6000:
        return random.choices([1, 2, 3], weights=[68, 24, 8])[0]
    if price >= 1500:
        return random.choices([1, 2, 3, 4], weights=[48, 30, 15, 7])[0]
    return random.choices([1, 2, 3, 4, 5], weights=[32, 27, 20, 13, 8])[0]


def pick_discount(category, order_month):
    """
    Discount is applied largely independently of item value, so the
    discount-effectiveness analysis produces an honest finding: deep discounts
    barely lift average order value but cut margin hard.
    Electronics is discounted most aggressively; festive months discount more.
    """
    base = {
        "Electronics":    [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "Home & Kitchen": [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "Furniture":      [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "Apparel":        [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "Accessories":    [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    }[category]

    if category == "Electronics":
        w = [14, 14, 16, 16, 15, 13, 12]
    elif category == "Home & Kitchen":
        w = [20, 18, 18, 15, 12, 9, 8]
    elif category == "Apparel":
        w = [18, 17, 18, 16, 13, 10, 8]
    elif category == "Accessories":
        w = [24, 20, 18, 14, 10, 8, 6]
    else:  # Furniture holds price better
        w = [30, 22, 18, 12, 8, 6, 4]

    if order_month in (10, 11):      # festive discounting is deeper
        w = [max(4, x - 6) for x in w[:3]] + [x + 6 for x in w[3:]]

    return random.choices(base, weights=w)[0]


# --------------------------------------------------------------------------
# Core generation
# --------------------------------------------------------------------------

def build_customer_assignment(order_regions):
    """
    Build a customer pool per region whose orders-per-customer distribution
    produces the intended repeat rate, then return a list of customer IDs
    aligned to order_regions.

    Salem uses the 'churny' profile: lots of one-and-done buyers.
    """
    counts = {}
    for r in order_regions:
        counts[r] = counts.get(r, 0) + 1

    # Build (region -> list of per-customer order counts)
    region_slots = {}
    total_customers = 0
    for region, n_orders in counts.items():
        churny = REGIONS[region][1] < 2.0
        values, weights = (REPEAT_PROFILE_CHURNY if churny
                           else REPEAT_PROFILE_NORMAL)
        slots, running = [], 0
        while running < n_orders:
            k = random.choices(values, weights=weights)[0]
            slots.append(k)
            running += k
        # Trim the last customer so the region total matches exactly.
        overshoot = running - n_orders
        if overshoot:
            slots[-1] -= overshoot
            if slots[-1] <= 0:
                slots.pop()
        region_slots[region] = slots
        total_customers += len(slots)

    # Allocate globally shuffled customer IDs so IDs are not clustered by region.
    ids = ["C%03d" % i for i in range(1, total_customers + 1)]
    random.shuffle(ids)

    region_queue = {}
    cursor = 0
    for region, slots in region_slots.items():
        seq = []
        for k in slots:
            cid = ids[cursor]
            cursor += 1
            seq.extend([cid] * k)
        random.shuffle(seq)
        region_queue[region] = seq

    assigned = []
    for r in order_regions:
        assigned.append(region_queue[r].pop())
    return assigned


def generate_clean_rows():
    day_pool, day_weights = build_date_pool()

    region_weights = {r: REGIONS[r][0] for r in REGIONS}
    order_regions = [weighted_choice(region_weights) for _ in range(N_ORDERS)]
    order_customers = build_customer_assignment(order_regions)

    rows = []
    order_id = 1001

    for region, customer in zip(order_regions, order_customers):
        order_date = random.choices(day_pool, weights=day_weights, k=1)[0]
        channel = random.choices(CHANNELS, weights=[45, 55])[0]

        n_items = random.choices([1, 2, 3], weights=[68, 24, 8])[0]
        chosen = set()
        for _ in range(n_items):
            product = weighted_choice({p: PRODUCTS[p][2] for p in PRODUCTS})
            if product in chosen:
                continue
            chosen.add(product)

            category, list_price, _ = PRODUCTS[product]
            # Small price jitter so the data does not look synthetic.
            price = int(round(list_price * random.uniform(0.96, 1.04) / 10.0) * 10)
            cost_ratio = min(0.93, max(0.40,
                            COST_RATIO[category] + random.uniform(-0.03, 0.03)))
            unit_cost = int(round(price * cost_ratio / 10.0) * 10)

            rows.append({
                "Order ID": order_id,
                "Date": order_date.isoformat(),
                "Customer": customer,
                "Product": product,
                "Category": category,
                "Quantity": pick_quantity(price),
                "Price": price,
                "Unit Cost": unit_cost,
                "Discount %": round(pick_discount(category, order_date.month), 2),
                "Region": region,
                "Channel": channel,
            })
        order_id += 1

    rows.sort(key=lambda r: (r["Date"], r["Order ID"]))
    return rows


def inject_dirt(clean_rows):
    """
    Return (raw_rows, issue_index) where issue_index records which rows carry
    which injected defect, so the cleaning log can be generated from fact.
    """
    rows = [dict(r) for r in clean_rows]
    issues = {
        "duplicates": 0,
        "blank_region": 0,
        "region_casing": 0,
        "negative_quantity": 0,
        "future_date": 0,
        "price_outlier": 0,
        "date_format": 0,
    }

    n = len(rows)
    all_idx = list(range(n))
    random.shuffle(all_idx)
    cursor = 0

    def take(k):
        nonlocal cursor
        picked = all_idx[cursor:cursor + k]
        cursor += k
        return picked

    # 1. Blank regions - applied at ORDER level, because in a real export a
    #    failed address/geo lookup drops the region for the whole order.
    by_order = {}
    for idx, r in enumerate(rows):
        by_order.setdefault(r["Order ID"], []).append(idx)
    blanked_rows = 0
    for oid in random.sample(list(by_order.keys()), len(by_order)):
        if blanked_rows >= 28:
            break
        for idx in by_order[oid]:
            rows[idx]["Region"] = ""
            blanked_rows += 1
            issues["blank_region"] += 1

    # 2. Inconsistent region casing / stray whitespace
    for i in take(63):
        r = rows[i]["Region"]
        if not r:
            continue
        variant = random.choice([r.lower(), r.upper(), " " + r, r + "  ",
                                 r.lower() + " ", r.title() + " "])
        rows[i]["Region"] = variant
        issues["region_casing"] += 1

    # 3. Negative quantities (untagged returns)
    for i in take(5):
        rows[i]["Quantity"] = -abs(int(rows[i]["Quantity"]))
        issues["negative_quantity"] += 1

    # 4. Impossible future dates
    for i in take(3):
        rows[i]["Date"] = (TODAY + timedelta(days=random.randint(20, 120))).isoformat()
        issues["future_date"] += 1

    # 5. Price entered 10x too high
    for i in take(2):
        rows[i]["Price"] = int(rows[i]["Price"]) * 10
        issues["price_outlier"] += 1

    # 6. Mixed date formats (DD-MM-YYYY instead of ISO)
    for i in take(20):
        y, m, d = [int(x) for x in rows[i]["Date"].split("-")]
        rows[i]["Date"] = "%02d-%02d-%04d" % (d, m, y)
        issues["date_format"] += 1

    # 7. Exact duplicate rows appended at random positions
    dup_sources = random.sample(range(len(rows)), 41)
    for i in dup_sources:
        rows.append(dict(rows[i]))
        issues["duplicates"] += 1

    random.shuffle(rows)
    rows.sort(key=lambda r: str(r["Order ID"]))
    return rows, issues


# --------------------------------------------------------------------------
# Cleaning (mirrors exactly what the Excel workflow should do)
# --------------------------------------------------------------------------

def parse_date(value):
    v = value.strip()
    if len(v) == 10 and v[4] == "-":
        y, m, d = [int(x) for x in v.split("-")]
        return date(y, m, d)
    if len(v) == 10 and v[2] == "-":
        d, m, y = [int(x) for x in v.split("-")]
        return date(y, m, d)
    raise ValueError("unparseable date: %r" % value)


def clean(raw_rows):
    log = []
    rows = [dict(r) for r in raw_rows]
    start_count = len(rows)

    # Rule 1 - remove exact duplicate rows
    seen, deduped = set(), []
    for r in rows:
        key = tuple(str(r[c]).strip().lower() for c in COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    removed_dupes = len(rows) - len(deduped)
    rows = deduped
    log.append(("Exact duplicate rows", removed_dupes, "Removed",
                "Identical Order ID + Product + Date = double entry from the "
                "source export"))

    # Rule 2 - standardise region text
    fixed_case = 0
    for r in rows:
        original = r["Region"]
        standard = " ".join(original.split()).title()
        if standard != original and standard != "":
            fixed_case += 1
        r["Region"] = standard
    log.append(("Inconsistent Region casing / whitespace", fixed_case,
                "TRIM + PROPER applied",
                "Prevented duplicate region groups splitting GROUP BY totals"))

    # Rule 3 - blank regions
    blanks = 0
    for r in rows:
        if r["Region"] == "":
            r["Region"] = "Unknown"
            blanks += 1
    log.append(("Blank Region", blanks, 'Set to "Unknown"',
                "Dropping these rows would understate national revenue totals"))

    # Rule 4 - date parsing / normalisation
    reformatted = 0
    for r in rows:
        original = r["Date"]
        parsed = parse_date(str(original))
        if parsed.isoformat() != str(original):
            reformatted += 1
        r["Date"] = parsed.isoformat()
    log.append(("Mixed date formats (DD-MM-YYYY)", reformatted,
                "Parsed and normalised to YYYY-MM-DD",
                "Text-format dates break chronological sorting and date logic"))

    # Rule 5 - negative quantities
    before = len(rows)
    rows = [r for r in rows if int(r["Quantity"]) > 0]
    neg = before - len(rows)
    log.append(("Negative Quantity", neg, "Excluded and flagged",
                "Likely untagged returns; returns are out of scope for this brief"))

    # Rule 6 - future dates
    before = len(rows)
    rows = [r for r in rows if parse_date(r["Date"]) <= TODAY]
    future = before - len(rows)
    log.append(("Order Date later than today", future, "Excluded",
                "Impossible values - cannot represent a completed sale"))

    # Rule 7 - price outliers, corrected against the category median
    by_cat = {}
    for r in rows:
        by_cat.setdefault((r["Category"], r["Product"]), []).append(int(r["Price"]))
    medians = {}
    for k, vals in by_cat.items():
        s = sorted(vals)
        medians[k] = s[len(s) // 2]
    outliers = 0
    for r in rows:
        key = (r["Category"], r["Product"])
        med = medians[key]
        if int(r["Price"]) > med * 4:
            r["Price"] = med
            outliers += 1
    log.append(("Price outliers (10x product median)", outliers,
                "Corrected to product median price",
                "Confirmed data-entry error, not a premium SKU variant"))

    # Calculated columns
    for r in rows:
        qty = int(r["Quantity"])
        price = int(r["Price"])
        cost = int(r["Unit Cost"])
        disc = float(r["Discount %"])
        gross = qty * price
        net = round(gross * (1 - disc), 2)
        profit = round(net - qty * cost, 2)
        r["Gross Revenue"] = round(gross, 2)
        r["Net Revenue"] = net
        r["Gross Profit"] = profit
        r["Margin %"] = round(profit / net, 4) if net else 0.0
        r["Order Month"] = r["Date"][:7]

    rows.sort(key=lambda r: (r["Date"], int(r["Order ID"])))
    end_count = len(rows)
    pct = 100.0 * (start_count - end_count) / start_count
    log.append(("NET RESULT", start_count - end_count,
                "%d rows in -> %d rows out" % (start_count, end_count),
                "%.1f%% of records removed" % pct))
    return rows, log


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------

def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in columns})


def col_letter(idx):
    """1 -> A, 27 -> AA"""
    s = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def write_xlsx(path, rows, columns, sheet_name="Sales"):
    """Minimal but valid .xlsx writer - stdlib zipfile only."""
    numeric = {"Order ID", "Quantity", "Price", "Unit Cost", "Discount %",
               "Gross Revenue", "Net Revenue", "Gross Profit", "Margin %"}

    def cell(ref, value, is_num):
        if is_num:
            return '<c r="%s"><v>%s</v></c>' % (ref, value)
        return ('<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                % (ref, xml_escape(value)))

    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/'
             'spreadsheetml/2006/main"><sheetData>']

    header_cells = "".join(cell("%s1" % col_letter(i + 1), c, False)
                           for i, c in enumerate(columns))
    parts.append('<row r="1">%s</row>' % header_cells)

    for ri, row in enumerate(rows, start=2):
        cells = []
        for ci, c in enumerate(columns):
            v = row[c]
            is_num = c in numeric and str(v).strip() != ""
            cells.append(cell("%s%d" % (col_letter(ci + 1), ri), v, is_num))
        parts.append('<row r="%d">%s</row>' % (ri, "".join(cells)))

    parts.append("</sheetData></worksheet>")
    sheet_xml = "".join(parts)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
        'package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Id="rId1" Type="http://schemas.'
        'openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>')

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>'
        % xml_escape(sheet_name))

    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Id="rId1" Type="http://schemas.'
        'openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>')

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


# --------------------------------------------------------------------------
# Verification summary - prints the REAL findings in the generated data
# --------------------------------------------------------------------------

def summarise(rows):
    def rupees(x):
        return "%,.0f".replace("%,", "{:,").format(x) if False else "{:,.0f}".format(x)

    total_net = sum(r["Net Revenue"] for r in rows)
    total_profit = sum(r["Gross Profit"] for r in rows)
    orders = len(set(r["Order ID"] for r in rows))
    units = sum(int(r["Quantity"]) for r in rows)
    customers = set(r["Customer"] for r in rows)

    print("\n" + "=" * 72)
    print("VERIFIED FINDINGS IN THE GENERATED DATA")
    print("=" * 72)
    print("Rows                : {:,}".format(len(rows)))
    print("Orders              : {:,}".format(orders))
    print("Units sold          : {:,}".format(units))
    print("Customers           : {:,}".format(len(customers)))
    print("Net revenue         : Rs {}".format(rupees(total_net)))
    print("Gross profit        : Rs {}".format(rupees(total_profit)))
    print("Overall margin      : {:.1f}%".format(100 * total_profit / total_net))
    print("Average order value : Rs {}".format(rupees(total_net / orders)))
    print("Date range          : {} to {}".format(rows[0]["Date"], rows[-1]["Date"]))

    # Category
    print("\n-- Revenue and margin by category " + "-" * 38)
    cat = {}
    for r in rows:
        c = cat.setdefault(r["Category"], {"net": 0.0, "profit": 0.0, "orders": set()})
        c["net"] += r["Net Revenue"]
        c["profit"] += r["Gross Profit"]
        c["orders"].add(r["Order ID"])
    print("{:<16}{:>14}{:>8}{:>10}{:>10}".format(
        "Category", "Net Revenue", "Share", "Margin", "AOV"))
    for k, v in sorted(cat.items(), key=lambda x: -x[1]["net"]):
        print("{:<16}{:>14}{:>7.1f}%{:>9.1f}%{:>10}".format(
            k, rupees(v["net"]), 100 * v["net"] / total_net,
            100 * v["profit"] / v["net"], rupees(v["net"] / len(v["orders"]))))

    # Pareto
    print("\n-- Pareto concentration " + "-" * 48)
    prod = {}
    for r in rows:
        prod[r["Product"]] = prod.get(r["Product"], 0.0) + r["Net Revenue"]
    ranked = sorted(prod.items(), key=lambda x: -x[1])
    run = 0.0
    n_at_80 = 0
    for i, (p, v) in enumerate(ranked, 1):
        run += v
        if run / total_net >= 0.80:
            n_at_80 = i
            break
    print("Top 5 products      : {}".format(
        ", ".join(p for p, _ in ranked[:5])))
    print("Products to reach 80% of revenue: {} of {} ({:.0f}% of catalogue)".format(
        n_at_80, len(ranked), 100.0 * n_at_80 / len(ranked)))
    tail = [p for p, v in ranked if v / total_net < 0.01]
    print("SKUs contributing <1% each      : {}".format(len(tail)))

    # Discount bands
    print("\n-- Discount effectiveness " + "-" * 46)

    def band(d):
        if d == 0:
            return "0%"
        if d <= 0.10:
            return "1-10%"
        if d <= 0.20:
            return "11-20%"
        return "21%+"

    bands = {}
    for r in rows:
        b = bands.setdefault(band(float(r["Discount %"])),
                             {"net": 0.0, "profit": 0.0, "orders": set()})
        b["net"] += r["Net Revenue"]
        b["profit"] += r["Gross Profit"]
        b["orders"].add(r["Order ID"])
    print("{:<10}{:>9}{:>14}{:>12}{:>10}".format(
        "Band", "Orders", "Net Revenue", "AOV", "Margin"))
    for k in ["0%", "1-10%", "11-20%", "21%+"]:
        if k not in bands:
            continue
        v = bands[k]
        print("{:<10}{:>9}{:>14}{:>12}{:>9.1f}%".format(
            k, len(v["orders"]), rupees(v["net"]),
            rupees(v["net"] / len(v["orders"])),
            100 * v["profit"] / v["net"]))

    # Region repeat rate.
    # A customer is attributed to their home region = the most frequent
    # non-Unknown region on their orders. This stops the "Unknown" bucket
    # created during cleaning from contaminating retention figures.
    print("\n-- Region repeat rate (customers attributed to home region) " + "-" * 12)
    home_votes = {}
    cust_orders = {}
    for r in rows:
        cust_orders.setdefault(r["Customer"], set()).add(r["Order ID"])
        if r["Region"] != "Unknown":
            v = home_votes.setdefault(r["Customer"], {})
            v[r["Region"]] = v.get(r["Region"], 0) + 1
    home = {c: max(v.items(), key=lambda x: x[1])[0] for c, v in home_votes.items()}

    reg_rev = {}
    for r in rows:
        reg_rev[r["Region"]] = reg_rev.get(r["Region"], 0.0) + r["Net Revenue"]

    reg = {}
    for c, orders_set in cust_orders.items():
        if c not in home:
            continue
        reg.setdefault(home[c], []).append(len(orders_set))

    print("{:<14}{:>11}{:>14}{:>14}".format(
        "Region", "Customers", "Repeat Rate", "Net Revenue"))
    for k, order_counts in sorted(reg.items(),
                                  key=lambda x: -reg_rev.get(x[0], 0)):
        repeat = sum(1 for n in order_counts if n > 1)
        print("{:<14}{:>11}{:>13.1f}%{:>14}".format(
            k, len(order_counts), 100.0 * repeat / len(order_counts),
            rupees(reg_rev.get(k, 0))))
    overall_repeat = sum(1 for o in cust_orders.values() if len(o) > 1)
    print("{:<14}{:>11}{:>13.1f}%{:>14}".format(
        "ALL", len(cust_orders), 100.0 * overall_repeat / len(cust_orders),
        rupees(total_net)))

    # Monthly trend
    print("\n-- Monthly revenue " + "-" * 53)
    months = {}
    for r in rows:
        months[r["Order Month"]] = months.get(r["Order Month"], 0.0) + r["Net Revenue"]
    prev = None
    for m in sorted(months):
        mom = "" if prev is None else "{:+.1f}%".format(100 * (months[m] - prev) / prev)
        print("  {}  {:>14}  {:>8}".format(m, rupees(months[m]), mom))
        prev = months[m]
    print("=" * 72 + "\n")


# --------------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    clean_base = generate_clean_rows()
    raw_rows, _ = inject_dirt(clean_base)
    cleaned_rows, log = clean(raw_rows)

    raw_path = os.path.join(DATA_DIR, "raw_sales_data.csv")
    clean_path = os.path.join(DATA_DIR, "cleaned_sales_data.csv")
    xlsx_path = os.path.join(DATA_DIR, "Sales_Data_Raw.xlsx")
    log_path = os.path.join(DATA_DIR, "data_quality_log.csv")

    clean_columns = COLUMNS + ["Gross Revenue", "Net Revenue", "Gross Profit",
                               "Margin %", "Order Month"]

    write_csv(raw_path, raw_rows, COLUMNS)
    write_csv(clean_path, cleaned_rows, clean_columns)
    write_xlsx(xlsx_path, raw_rows, COLUMNS)

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Issue Found", "Rows Affected", "Rule Applied", "Rationale"])
        for entry in log:
            w.writerow(entry)

    print("Wrote {} raw rows      -> {}".format(len(raw_rows), raw_path))
    print("Wrote {} cleaned rows  -> {}".format(len(cleaned_rows), clean_path))
    print("Wrote raw workbook        -> {}".format(xlsx_path))
    print("Wrote cleaning audit log  -> {}".format(log_path))

    summarise(cleaned_rows)


if __name__ == "__main__":
    main()
