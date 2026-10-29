"""Writes the fictional sample exports into samples/exports/ (same output every run).

Harbor Light Coffee Roasters is made up: a cafe that sells in its shop (Square),
online (Shopify) and wholesale to restaurants (QuickBooks invoices). The files are
messy on purpose, the way real exports are: two Square downloads with overlapping
dates, a byte-order mark, padded headers, money in brackets, blank lines, a totals
row, multi-line Shopify orders with cancelled and unpaid ones, and a QuickBooks
report with title rows, customer headings and subtotal rows.

    python3 samples/make_samples.py
"""

import csv
import os
import random
from datetime import date, datetime, timedelta

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
rng = random.Random(20261030)
START, END = date(2026, 8, 1), date(2026, 10, 31)


def days(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def money(x, brackets=False):
    if brackets and x < 0:
        return "($%.2f)" % -x
    return ("-$%.2f" % -x) if x < 0 else "$%.2f" % x


REGULARS = ["Maria Santos", "Dev Patel", "Lena Okafor", "Tom Brennan", "Aiko Tanaka", "Sam Whitfield",
            "Priya Raman", "Jonah Miller", "Grace Liu", "Owen Harper", "Rosa Delgado", "Ben Carter",
            "Hannah Moss", "Eli Novak", "Nora Quinn"]

SQUARE_MENU = [
    ("Coffee", "Drip Coffee", ["Small", "Large"], [3.25, 3.95], 30),
    ("Coffee", "Latte", ["Regular"], [5.25], 22),
    ("Coffee", "Cappuccino", ["Regular"], [4.75], 12),
    ("Coffee", "Cold Brew", ["Regular"], [4.95], 14),
    ("Pastry", "Butter Croissant", ["Regular"], [3.75], 14),
    ("Pastry", "Blueberry Muffin", ["Regular"], [3.50], 9),
    ("Pastry", "Maple Scone", ["Regular"], [3.95], 7),
    ("Retail Beans", "Harbor House Blend 12 oz", ["Regular"], [17.00], 4),
    ("Retail Beans", "Lighthouse Espresso 12 oz", ["Regular"], [18.50], 3),
    ("Merch", "Harbor Light Mug", ["Regular"], [16.00], 1),
]

SQUARE_HEAD = ["Date", "Time", "Time Zone", "Category", "Item", "Qty", "Price Point Name", "SKU", "Modifiers Applied",
               "Gross Sales", "Discounts", "Net Sales", "Tax", "Transaction ID", "Payment ID", "Device Name", "Notes",
               "Details", "Event Type", "Location", "Dining Option", "Customer ID", "Customer Name", "Customer Reference ID"]


def square_rows():
    rows = []
    weights = [m[4] for m in SQUARE_MENU]
    tx = 0
    for d in days(START, END):
        busy = 1.25 if d.weekday() >= 5 else 1.0
        if d.month == 10:
            busy *= 1.08
        for _ in range(int(rng.randint(9, 14) * busy)):
            tx += 1
            tid = "T%06dHL" % (tx * 37 % 999983)
            t = "%02d:%02d:%02d" % (rng.randint(7, 15), rng.randint(0, 59), rng.randint(0, 59))
            customer = rng.choice(REGULARS) if rng.random() < 0.16 else ""
            for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):
                cat, item, points, prices, _w = rng.choices(SQUARE_MENU, weights)[0]
                k = rng.randrange(len(points))
                qty = 1 if cat != "Pastry" else rng.choice([1, 1, 2])
                gross = round(prices[k] * qty, 2)
                disc = -0.50 if cat == "Coffee" and rng.random() < 0.06 else 0.0
                net = round(gross + disc, 2)
                rows.append([d.strftime("%m/%d/%Y"), t, "Eastern Time (US & Canada)", cat, item, str(qty), points[k],
                             "", "", money(gross), money(disc, True), money(net, True), money(round(net * 0.055, 2)),
                             tid, "P" + tid, "Front Counter", "", "", "Payment", "Harbor Light Coffee Roasters",
                             "For Here" if rng.random() < 0.4 else "To Go", "", customer, ""])
    # Refunds: a wrong order, a cold latte, a returned bag of beans...
    for d, item, cat, amount in [(date(2026, 8, 9), "Latte", "Coffee", 5.25), (date(2026, 8, 27), "Harbor House Blend 12 oz", "Retail Beans", 17.00),
                                 (date(2026, 9, 18), "Cold Brew", "Coffee", 4.95), (date(2026, 10, 4), "Harbor Light Mug", "Merch", 16.00),
                                 (date(2026, 10, 22), "Butter Croissant", "Pastry", 3.75)]:
        tx += 1
        tid = "R%06dHL" % tx
        rows.append([d.strftime("%m/%d/%Y"), "12:10:05", "Eastern Time (US & Canada)", cat, item, "-1", "Regular", "", "",
                     money(-amount, True), "$0.00", money(-amount, True), money(round(-amount * 0.055, 2), True), tid, "P" + tid,
                     "Front Counter", "Customer unhappy", "", "Refund", "Harbor Light Coffee Roasters", "", "", "", ""])
    rows.sort(key=lambda r: (datetime.strptime(r[0], "%m/%d/%Y"), r[1]))
    return rows


def write_square(rows):
    head = [h + ("  " if h in ("Net Sales", "Customer Name") else "") for h in SQUARE_HEAD]  # padded headers
    first = [r for r in rows if datetime.strptime(r[0], "%m/%d/%Y").date() <= date(2026, 9, 30)]
    second = [r for r in rows if datetime.strptime(r[0], "%m/%d/%Y").date() >= date(2026, 9, 15)]
    with open(os.path.join(HERE, "square_items_2026-08-01_2026-09-30.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        for i, r in enumerate(first):
            w.writerow(r)
            if i in (120, 900):
                w.writerow([])                     # stray blank lines
        w.writerow(["Total", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    with open(os.path.join(HERE, "square_items_2026-09-15_2026-10-31.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(second)                        # Sep 15-30 are in both files


SHOP_PRODUCTS = [
    ("Harbor House Blend - 12 oz Whole Bean", "HL-HHB-12", 17.00),
    ("Lighthouse Espresso - 12 oz Whole Bean", "HL-LHE-12", 18.50),
    ("Foghorn Dark Roast - 2 lb Bag", "HL-FDR-2LB", 42.00),
    ("Swiss Water Decaf - 12 oz Ground", "HL-DEC-12", 18.00),
    ("Monthly Coffee Subscription - 2 Bags", "HL-SUB-2", 32.00),
    ("Harbor Light Ceramic Mug", "HL-MUG", 16.00),
    ("Pour-Over Brewing Guide (printed)", "HL-GUIDE", 9.00),
]
ONLINE_BUYERS = ["Maria Santos", "maria santos", "Kevin Roy", "Alicia Gomez", "Peter Lindqvist", "Dana Brooks",
                 "Mei Chen", "Luis Ortega", "Fatima Noor", "Chris Doyle", "Ingrid Berg", "Ravi Shah", "Zoe Adams",
                 "Marcus Hill", "Julia Weber", "Tyler Grant", "Ana Costa", "Sophie Martin"]

SHOP_HEAD = ["Name", "Email", "Financial Status", "Paid at", "Fulfillment Status", "Fulfilled at", "Accepts Marketing",
             "Currency", "Subtotal", "Shipping", "Taxes", "Total", "Discount Code", "Discount Amount", "Shipping Method",
             "Created at", "Lineitem quantity", "Lineitem name", "Lineitem price", "Lineitem compare at price",
             "Lineitem sku", "Lineitem requires shipping", "Lineitem taxable", "Lineitem fulfillment status",
             "Billing Name", "Billing City", "Billing Province", "Shipping Name", "Notes", "Cancelled at",
             "Payment Method", "Refunded Amount", "Vendor", "Id"]


def write_shopify():
    rows = []
    number = 1040
    special = {1052: "refunded", 1077: "partially_refunded", 1101: "refunded", 1063: "cancelled", 1118: "cancelled", 1129: "pending"}
    for d in days(START, END):
        for _ in range(rng.choice([0, 1, 1, 1, 2, 2, 3])):
            number += 1
            ts = datetime(d.year, d.month, d.day, rng.randint(6, 22), rng.randint(0, 59), rng.randint(0, 59))
            stamp = ts.strftime("%Y-%m-%d %H:%M:%S -0400")
            buyer = rng.choice(ONLINE_BUYERS)
            lines = []
            for p in rng.sample(SHOP_PRODUCTS, rng.choice([1, 1, 1, 2, 2, 3])):
                lines.append((p, rng.choice([1, 1, 1, 2])))
            subtotal = round(sum(p[2] * q for p, q in lines), 2)
            code, discount = ("WELCOME10", round(subtotal * 0.10, 2)) if rng.random() < 0.15 else ("", 0.0)
            shipping = 0.0 if subtotal >= 50 else 6.95
            taxes = 0.0
            total = round(subtotal - discount + shipping + taxes, 2)
            status = special.get(number, "paid")
            refunded = {"refunded": total, "partially_refunded": round(lines[0][0][2], 2)}.get(status, 0.0)
            cancelled = stamp if status == "cancelled" else ""
            fin = "voided" if status == "cancelled" else status
            for i, (p, q) in enumerate(lines):
                if i == 0:
                    rows.append(["#%d" % number, buyer.lower().replace(" ", ".") + "@example.com", fin,
                                 "" if fin in ("pending", "voided") else stamp, "fulfilled", stamp, "yes", "USD",
                                 "%.2f" % subtotal, "%.2f" % shipping, "%.2f" % taxes, "%.2f" % total, code,
                                 "%.2f" % discount, "Standard" if shipping else "Free shipping", stamp, str(q), p[0],
                                 "%.2f" % p[2], "", p[1], "true", "true", "fulfilled", buyer, "Portland", "ME", buyer,
                                 "", cancelled, "Shopify Payments", "%.2f" % refunded, "Harbor Light", str(5800000000 + number)])
                else:
                    rows.append(["#%d" % number] + [""] * 15 + [str(q), p[0], "%.2f" % p[2], "", p[1], "true", "true", "fulfilled"]
                                + [""] * 10)
    # Most recent order first, like Shopify's own export (lines stay in order inside each order),
    # plus one order that appears again from a second download.
    blocks = []
    for r in rows:
        if r[2]:
            blocks.append([])
        blocks[-1].append(r)
    rows = [r for b in reversed(blocks) for r in b]
    dup = [r for r in rows if r[0] == "#1090"]
    with open(os.path.join(HERE, "shopify_orders_export.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(SHOP_HEAD)
        w.writerows(rows + dup)


WHOLESALE = ["Bayside Bistro", "Anchor & Oak Kitchen", "Tidewater Market", "Pier 9 Diner", "Saltbox Bakery", "North Cove Inn"]
WHOLESALE_ITEMS = [("Wholesale:House Espresso 5 lb", 62.00), ("Wholesale:Harbor House Blend 5 lb", 58.00),
                   ("Wholesale:Swiss Water Decaf 5 lb", 66.00), ("Wholesale:Cold Brew Concentrate 1 gal", 38.00),
                   ("Equipment:Grinder Rental (monthly)", 45.00)]


def write_quickbooks():
    lines = {c: [] for c in WHOLESALE}
    num = 3100
    for c in WHOLESALE:
        weekday = WHOLESALE.index(c) % 5
        for d in days(START, END):
            if d.weekday() != weekday or rng.random() < 0.25:
                continue
            num += 1
            for name, price in rng.sample(WHOLESALE_ITEMS[:4], rng.choice([1, 2, 2, 3])):
                qty = rng.choice([1, 2, 2, 3, 4])
                lines[c].append((d, "Invoice", str(num), name, "", qty, price, round(qty * price, 2)))
            if d.day <= 7 and c in ("Anchor & Oak Kitchen", "North Cove Inn"):
                lines[c].append((d, "Invoice", str(num), WHOLESALE_ITEMS[4][0], "Monthly rental", 1, 45.00, 45.00))
    lines["Pier 9 Diner"].append((date(2026, 9, 12), "Credit Memo", "CM-14", "Wholesale:House Espresso 5 lb", "Damaged bag", 1, 62.00, -62.00))
    lines["Tidewater Market"].append((date(2026, 10, 20), "Credit Memo", "CM-15", "Wholesale:Cold Brew Concentrate 1 gal", "Short delivery", 2, 38.00, -76.00))

    out = [["Harbor Light Coffee Roasters"], ["Sales by Customer Detail"], ["August 1 - October 31, 2026"], [],
           ["", "Date", "Transaction Type", "Num", "Product/Service", "Memo/Description", "Qty", "Sales Price", "Amount", "Balance"]]
    grand = 0.0
    for c in WHOLESALE:
        out.append([c.upper() if c == "Bayside Bistro" else c])
        bal = 0.0
        for d, t, n, name, memo, qty, price, amount in sorted(lines[c]):
            bal += amount
            out.append(["", d.strftime("%m/%d/%Y"), t, n, name, memo, str(qty), "%.2f" % price, "{:,.2f}".format(amount), "{:,.2f}".format(bal)])
        out.append(["Total for " + c, "", "", "", "", "", "", "", "${:,.2f}".format(bal), ""])
        grand += bal
    out.append(["TOTAL", "", "", "", "", "", "", "", "${:,.2f}".format(grand), ""])
    out.append([])
    out.append(["Accrual Basis Monday, November 2, 2026 09:14 AM GMT-05:00"])
    with open(os.path.join(HERE, "quickbooks_sales_by_customer.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out)


if __name__ == "__main__":
    os.makedirs(HERE, exist_ok=True)
    write_square(square_rows())
    write_shopify()
    write_quickbooks()
    print("Sample exports written to", HERE)
