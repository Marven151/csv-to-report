"""Reading Square, Shopify, QuickBooks and generic CSV exports into one list of sale lines."""

import csv
import os
from dataclasses import dataclass, field
from decimal import Decimal

from .parsing import clean_text, normalize_header, parse_date, parse_money, parse_qty


@dataclass
class Record:
    """One line of sales: an item sold, or money given back."""
    date: object
    source: str          # Square, Shopify, QuickBooks or CSV
    channel: str         # In-store, Online, Wholesale, or the file name for generic files
    order_id: str
    customer: str        # "" when the export does not say
    category: str        # "" until categories are filled in
    item: str
    qty: Decimal
    amount: Decimal      # net sales before tax and shipping; negative for refunds
    kind: str            # "sale" or "refund"
    file: str
    line: int


@dataclass
class FileReport:
    """What happened to one input file, for the data-quality section."""
    file: str
    format: str
    rows: int = 0
    records: list = field(default_factory=list)
    skipped: list = field(default_factory=list)   # (line, reason)
    duplicates: int = 0
    kept: int = 0

    def skip(self, line, reason):
        self.skipped.append((line, reason))


CHANNELS = {"Square": "In-store", "Shopify": "Online", "QuickBooks": "Wholesale"}


def read_rows(path):
    """All rows of a CSV as lists of strings. Handles a UTF-8 BOM and Windows-1252 files."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=encoding) as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                return [row for row in csv.reader(f, dialect)]
        except UnicodeDecodeError:
            continue
    raise ValueError("%s: cannot read the file as text" % path)


def _find_header(rows, required):
    """Index of the first row (within the first 20) containing all `required` headers."""
    for i, row in enumerate(rows[:20]):
        names = {normalize_header(c) for c in row}
        if all(r in names for r in required):
            return i
    return None


class Columns:
    """Looks up cells by header name, tolerant of case, spacing and punctuation."""

    def __init__(self, header):
        self.index = {}
        for i, h in enumerate(header):
            key = normalize_header(h)
            if key and key not in self.index:
                self.index[key] = i

    def find(self, *names):
        for n in names:
            key = normalize_header(n)
            if key in self.index:
                return self.index[key]
        return None

    def get(self, row, *names):
        i = self.find(*names)
        return row[i] if i is not None and i < len(row) else ""


def detect_format(rows):
    if _find_header(rows, ["transaction id", "net sales", "event type"]) is not None:
        return "Square"
    if _find_header(rows, ["lineitem name", "financial status"]) is not None:
        return "Shopify"
    if _find_header(rows, ["transaction type", "num", "amount"]) is not None:
        return "QuickBooks"
    return "CSV"


def read_export(path):
    rows = read_rows(path)
    fmt = detect_format(rows)
    report = FileReport(file=os.path.basename(path), format=fmt)
    {"Square": _read_square, "Shopify": _read_shopify,
     "QuickBooks": _read_quickbooks, "CSV": _read_generic}[fmt](rows, report)
    return report


def _blank(row):
    return not any(clean_text(c) for c in row)


def _looks_like_total(row):
    first = next((clean_text(c).lower() for c in row if clean_text(c)), "")
    return first.startswith("total") or first in ("grand total", "totals")


# ---------------- Square: Item Sales export ----------------

def _read_square(rows, report):
    h = _find_header(rows, ["transaction id", "net sales", "event type"])
    cols = Columns(rows[h])
    for n, row in enumerate(rows[h + 1:], start=h + 2):
        if _blank(row):
            continue
        report.rows += 1
        d = parse_date(cols.get(row, "Date"))
        if d is None:
            report.skip(n, "total row" if _looks_like_total(row) else "no readable date")
            continue
        amount = parse_money(cols.get(row, "Net Sales"))
        if amount is None:
            report.skip(n, "no net sales amount")
            continue
        event = clean_text(cols.get(row, "Event Type")).lower()
        kind = "refund" if event == "refund" or amount < 0 else "sale"
        if kind == "refund" and amount > 0:
            amount = -amount
        item = clean_text(cols.get(row, "Item"))
        variant = clean_text(cols.get(row, "Price Point Name"))
        if variant and variant.lower() not in ("regular", "default"):
            item = "%s (%s)" % (item, variant)
        report.records.append(Record(
            date=d, source="Square", channel=CHANNELS["Square"],
            order_id=clean_text(cols.get(row, "Transaction ID")),
            customer=clean_text(cols.get(row, "Customer Name")),
            category=clean_text(cols.get(row, "Category")),
            item=item or "(no item name)",
            qty=abs(parse_qty(cols.get(row, "Qty"))), amount=amount, kind=kind,
            file=report.file, line=n))


# ---------------- Shopify: Orders export ----------------

def _read_shopify(rows, report):
    h = _find_header(rows, ["lineitem name", "financial status"])
    cols = Columns(rows[h])
    orders = []          # [(order_id, first_row, [(line_no, row), ...])]
    by_id = {}
    repeat = None        # order number being skipped because it was already read
    for n, row in enumerate(rows[h + 1:], start=h + 2):
        if _blank(row):
            continue
        report.rows += 1
        oid = clean_text(cols.get(row, "Name"))
        if not oid:
            report.skip(n, "no order number")
            continue
        starts_order = bool(clean_text(cols.get(row, "Financial Status")))
        if starts_order:
            # The same order again (an overlapping second download): skip all of its rows.
            repeat = oid if oid in by_id else None
        if oid == repeat:
            report.duplicates += 1
            continue
        if oid not in by_id:
            by_id[oid] = (oid, row, [])
            orders.append(by_id[oid])
        by_id[oid][2].append((n, row))

    for oid, first, lines in orders:
        status = clean_text(cols.get(first, "Financial Status")).lower()
        first_line = lines[0][0]
        if clean_text(cols.get(first, "Cancelled at")) or status in ("voided", "cancelled"):
            for n, _ in lines:
                report.skip(n, "cancelled order")
            continue
        if status in ("pending", "authorized", "expired"):
            for n, _ in lines:
                report.skip(n, "not paid (%s)" % status)
            continue
        d = parse_date(cols.get(first, "Paid at")) or parse_date(cols.get(first, "Created at"))
        if d is None:
            for n, _ in lines:
                report.skip(n, "no readable date")
            continue
        customer = clean_text(cols.get(first, "Billing Name")) or clean_text(cols.get(first, "Shipping Name"))
        items = []
        for n, row in lines:
            price = parse_money(cols.get(row, "Lineitem price"))
            if price is None:
                report.skip(n, "no line item price")
                continue
            qty = parse_qty(cols.get(row, "Lineitem quantity"))
            items.append((n, clean_text(cols.get(row, "Lineitem name")), qty, (price * qty)))
        if not items:
            continue
        # Order-level discount, shared across lines by value; the last line takes the rounding.
        discount = abs(parse_money(cols.get(first, "Discount Amount")) or Decimal(0))
        gross = sum(i[3] for i in items)
        left = discount
        for idx, (n, name, qty, value) in enumerate(items):
            if idx == len(items) - 1:
                share = left
            else:
                share = (discount * value / gross).quantize(Decimal("0.01")) if gross else Decimal(0)
            left -= share
            report.records.append(Record(
                date=d, source="Shopify", channel=CHANNELS["Shopify"], order_id=oid, customer=customer,
                category="", item=name or "(no item name)", qty=qty, amount=value - share, kind="sale",
                file=report.file, line=n))
        refunded = parse_money(cols.get(first, "Refunded Amount")) or Decimal(0)
        if refunded > 0:
            # The export gives one refunded total (it can include tax and shipping); count at most
            # the product value, on the order date, because the export has no refund date.
            report.records.append(Record(
                date=d, source="Shopify", channel=CHANNELS["Shopify"], order_id=oid, customer=customer,
                category="", item="Refund", qty=Decimal(0), amount=-min(refunded, gross - discount),
                kind="refund", file=report.file, line=first_line))


# ---------------- QuickBooks: Sales by Customer Detail ----------------

_QB_REFUNDS = ("credit memo", "refund receipt", "refund")
_QB_SALES = ("invoice", "sales receipt")


def _read_quickbooks(rows, report):
    h = _find_header(rows, ["transaction type", "num", "amount"])
    cols = Columns(rows[h])
    customer = ""
    for n, row in enumerate(rows[h + 1:], start=h + 2):
        if _blank(row):
            continue
        cells = [clean_text(c) for c in row]
        filled = [c for c in cells if c]
        if _looks_like_total(row):
            continue
        # A customer heading has only its first cell filled; detail rows start empty.
        if cells[0] and len(filled) == 1:
            if not cells[0].lower().startswith(("accrual basis", "cash basis")):
                customer = cells[0]
            continue
        report.rows += 1
        d = parse_date(cols.get(row, "Date"))
        if d is None:
            report.skip(n, "no readable date")
            continue
        ttype = clean_text(cols.get(row, "Transaction Type")).lower()
        amount = parse_money(cols.get(row, "Amount"))
        if amount is None:
            report.skip(n, "no amount")
            continue
        if ttype in _QB_REFUNDS:
            kind, amount = "refund", -abs(amount)
        elif ttype in _QB_SALES:
            kind = "refund" if amount < 0 else "sale"
        else:
            report.skip(n, "not a sale (%s)" % (ttype or "no type"))
            continue
        product = clean_text(cols.get(row, "Product/Service", "Item"))
        parts = [p.strip() for p in product.split(":") if p.strip()]
        category = parts[0] if len(parts) > 1 else ""
        item = parts[-1] if parts else clean_text(cols.get(row, "Memo/Description")) or "(no item name)"
        report.records.append(Record(
            date=d, source="QuickBooks", channel=CHANNELS["QuickBooks"],
            order_id=clean_text(cols.get(row, "Num")),
            customer=clean_text(cols.get(row, "Customer", "Name")) or customer,
            category=category, item=item, qty=abs(parse_qty(cols.get(row, "Qty"))),
            amount=amount, kind=kind, file=report.file, line=n))


# ---------------- Anything else with a date and an amount ----------------

GENERIC = {
    "date": ("date", "order date", "sale date", "transaction date", "invoice date", "paid at", "created at", "created"),
    "amount": ("net sales", "net amount", "amount", "line total", "total", "sales", "revenue", "subtotal", "price"),
    "customer": ("customer", "customer name", "client", "client name", "billing name", "buyer", "name"),
    "category": ("category", "product type", "department", "type"),
    "item": ("item", "product", "product name", "item name", "description", "service"),
    "qty": ("qty", "quantity", "units"),
    "order": ("order id", "order", "order number", "transaction id", "invoice", "invoice number", "receipt", "num", "id"),
}


def _read_generic(rows, report):
    h = None
    for i, row in enumerate(rows[:20]):
        c = Columns(row)
        if c.find(*GENERIC["date"]) is not None and c.find(*GENERIC["amount"]) is not None:
            h = i
            break
    if h is None:
        report.skip(1, "no date and amount columns found")
        return
    cols = Columns(rows[h])
    channel = os.path.splitext(report.file)[0].replace("_", " ").replace("-", " ").strip().capitalize()
    for n, row in enumerate(rows[h + 1:], start=h + 2):
        if _blank(row):
            continue
        report.rows += 1
        d = parse_date(cols.get(row, *GENERIC["date"]))
        if d is None:
            report.skip(n, "total row" if _looks_like_total(row) else "no readable date")
            continue
        amount = parse_money(cols.get(row, *GENERIC["amount"]))
        if amount is None:
            report.skip(n, "no amount")
            continue
        report.records.append(Record(
            date=d, source="CSV", channel=channel,
            order_id=clean_text(cols.get(row, *GENERIC["order"])) or "%s:%d" % (report.file, n),
            customer=clean_text(cols.get(row, *GENERIC["customer"])),
            category=clean_text(cols.get(row, *GENERIC["category"])),
            item=clean_text(cols.get(row, *GENERIC["item"])) or "(no item name)",
            qty=abs(parse_qty(cols.get(row, *GENERIC["qty"]))), amount=amount,
            kind="refund" if amount < 0 else "sale", file=report.file, line=n))
