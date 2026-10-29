"""Cleaning the combined lines (categories, customer names, duplicates) and adding them up."""

import csv
from collections import OrderedDict, defaultdict
from decimal import Decimal

from .parsing import clean_text, month_key

ZERO = Decimal("0.00")
UNCATEGORIZED = "Uncategorized"


def load_rules(path):
    """Category rules CSV with columns `match,category`: the first rule whose `match`
    text appears in the item name (case ignored) sets the category."""
    rules = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            keys = {k.strip().lower(): (v or "") for k, v in row.items() if k}
            match, category = keys.get("match", "").strip().lower(), keys.get("category", "").strip()
            if match and category:
                rules.append((match, category))
    return rules


def tidy_name(name):
    """'  BAYSIDE   BISTRO ' -> 'Bayside Bistro'. Mixed-case names are kept as typed."""
    name = clean_text(name)
    if name and (name.isupper() or name.islower()):
        name = " ".join(w if w.isdigit() else w[:1].upper() + w[1:].lower() for w in name.split(" "))
    return name


def apply_categories(records, rules):
    for r in records:
        if not r.category and r.kind == "sale":
            item = r.item.lower()
            r.category = next((c for m, c in rules if m in item), "")
        r.category = tidy_name(r.category) if r.category else (UNCATEGORIZED if r.kind == "sale" else "Refunds")


def unify_customers(records):
    """Same customer written different ways ('Bayside Bistro', 'BAYSIDE BISTRO ') -> one name:
    the spelling seen most often."""
    seen = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r.customer:
            seen[r.customer.lower().replace(".", "").replace(",", "")][tidy_name(r.customer)] += 1
    best = {k: max(v.items(), key=lambda kv: (kv[1], kv[0]))[0] for k, v in seen.items()}
    for r in records:
        if r.customer:
            r.customer = best[r.customer.lower().replace(".", "").replace(",", "")]


def dedupe_key(r):
    return (r.source, r.order_id, r.date, r.item.lower(), r.qty, r.amount, r.kind, r.customer.lower())


def remove_duplicates(reports):
    """Drops lines that an earlier file of the same system already supplied (exports
    downloaded with overlapping dates). Identical lines inside one file are kept: a receipt
    can really have two separate lattes. So a line kept twice in file A and present three
    times in file B is kept three times in total. Counts what was removed per file."""
    kept_so_far = {}
    kept = []
    for rep in reports:
        in_file = {}
        for r in rep.records:
            key = dedupe_key(r)
            in_file[key] = in_file.get(key, 0) + 1
            if in_file[key] <= kept_so_far.get(key, 0):
                rep.duplicates += 1
                continue
            kept_so_far[key] = in_file[key]
            kept.append(r)
            rep.kept += 1
    return kept


def clean(reports, rules=(), month=None):
    records = remove_duplicates(reports)
    apply_categories(records, list(rules))
    unify_customers(records)
    if month:
        records = [r for r in records if month_key(r.date) == month]
    records.sort(key=lambda r: (r.date, r.source, r.order_id, r.line))
    return records


def _order_key(r):
    return (r.source, r.order_id)


def summarize(records):
    """All the numbers the report shows. Money is Decimal; 'net' = sales minus refunds."""
    months = sorted({month_key(r.date) for r in records})
    channels = sorted({r.channel for r in records})
    by_month = OrderedDict((m, {"sales": ZERO, "refunds": ZERO, "orders": set(), "by_channel": defaultdict(lambda: ZERO)})
                           for m in months)
    categories = defaultdict(lambda: ZERO)
    customers = defaultdict(lambda: {"net": ZERO, "orders": set(), "channels": set()})
    total = {"sales": ZERO, "refunds": ZERO, "orders": set(), "refund_count": 0}

    for r in records:
        m = by_month[month_key(r.date)]
        if r.kind == "sale":
            m["sales"] += r.amount
            m["orders"].add(_order_key(r))
            total["sales"] += r.amount
            total["orders"].add(_order_key(r))
            categories[r.category] += r.amount
        else:
            m["refunds"] += -r.amount
            total["refunds"] += -r.amount
            total["refund_count"] += 1
        m["by_channel"][r.channel] += r.amount
        if r.customer:
            c = customers[r.customer]
            c["net"] += r.amount
            if r.kind == "sale":
                c["orders"].add(_order_key(r))
            c["channels"].add(r.channel)

    month_rows = []
    for key, m in by_month.items():
        net = m["sales"] - m["refunds"]
        count = len(m["orders"])
        month_rows.append({
            "month": key, "sales": m["sales"], "refunds": m["refunds"], "net": net, "orders": count,
            "average": (m["sales"] / count).quantize(Decimal("0.01")) if count else ZERO,
            "by_channel": {ch: m["by_channel"].get(ch, ZERO) for ch in channels},
        })

    category_rows = sorted(({"category": k, "sales": v} for k, v in categories.items()),
                           key=lambda x: (-x["sales"], x["category"]))
    customer_rows = sorted(({"customer": k, "net": v["net"], "orders": len(v["orders"]),
                             "channels": ", ".join(sorted(v["channels"]))} for k, v in customers.items()),
                           key=lambda x: (-x["net"], x["customer"]))
    orders = len(total["orders"])
    return {
        "months": month_rows,
        "channels": channels,
        "categories": category_rows,
        "customers": customer_rows,
        "sales": total["sales"],
        "refunds": total["refunds"],
        "refund_count": total["refund_count"],
        "net": total["sales"] - total["refunds"],
        "orders": orders,
        "average": (total["sales"] / orders).quantize(Decimal("0.01")) if orders else ZERO,
        "lines": len(records),
        "first_date": records[0].date if records else None,
        "last_date": records[-1].date if records else None,
    }


CLEAN_COLUMNS = ["date", "month", "channel", "source", "order_id", "customer", "category", "item", "qty", "amount", "kind", "file", "line"]


def write_clean_csv(records, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CLEAN_COLUMNS)
        for r in records:
            w.writerow([r.date.isoformat(), month_key(r.date), r.channel, r.source, r.order_id, r.customer,
                        r.category, r.item, _plain(r.qty), "%.2f" % r.amount, r.kind, r.file, r.line])


def _plain(d):
    return format(d.normalize(), "f") if d == d.to_integral() else str(d)
