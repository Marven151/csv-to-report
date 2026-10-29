"""Turning the text in export cells into dates and amounts."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")

# Tried in order. US exports put the month first, so 03/04/2026 is March 4.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%Y/%m/%d",
)


def parse_date(value):
    """Reads the date part of a cell: '10/03/2026', '2026-10-03T14:22:00-04:00',
    '2026-10-03 14:22:31 -0400', 'Oct 3, 2026', '10/3/26 2:15 PM'. Returns a date or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().strip('"')
    if not text:
        return None
    # ISO timestamps: keep the local date as written, ignore time and offset.
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]\d{1,2}:\d{2}", text)
    if m:
        text = m.group(1)
    else:
        # "10/03/2026 14:22" or "10/3/26 2:15 PM": drop the time.
        text = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?(\s*[AaPp]\.?[Mm]\.?)?$", "", text)
    text = re.sub(r"\s+", " ", text)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(value):
    """Reads an amount: '$1,234.50', '(4.50)', '-$4.50', 'USD 12', '12.00 USD', '4.50-', '40,00'.
    Returns a Decimal rounded to cents, or None when the cell is not an amount.
    An empty cell is None, not zero, so callers can tell 'missing' from '0'."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    text = str(value).strip()
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    text = re.sub(r"(?i)\b(usd|us\$)\b", "", text).replace("$", "").replace(" ", "")
    if "," in text:
        digits = text.lstrip("+-").rstrip("-")
        if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", digits):
            text = text.replace(",", "")          # 1,234.50
        elif re.fullmatch(r"\d+,\d{1,2}", digits):
            text = text.replace(",", ".")         # 40,00 from a European-style export
        else:
            return None
    if text.endswith("-"):
        negative, text = True, text[:-1]
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if text.startswith("+"):
        text = text[1:]
    if not re.fullmatch(r"\d*\.?\d+", text):
        return None
    try:
        amount = Decimal(text).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def parse_qty(value, default=1):
    """Quantity as a Decimal ('2', '1.5', ''). Empty or unreadable gives the default."""
    text = str(value or "").strip().replace(",", "")
    try:
        return Decimal(text) if text else Decimal(default)
    except InvalidOperation:
        return Decimal(default)


def clean_text(value):
    """Trims, collapses inner whitespace and drops stray quotes."""
    return re.sub(r"\s+", " ", str(value or "").replace("﻿", "")).strip().strip('"').strip()


def normalize_header(value):
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def month_key(d):
    return "%04d-%02d" % (d.year, d.month)


def month_label(key, short=False):
    year, month = key.split("-")
    d = date(int(year), int(month), 1)
    return d.strftime("%b %Y") if short else d.strftime("%B %Y")


def format_money(amount, cents=True):
    """Decimal -> '$1,234.50' / '-$4.50'; cents=False rounds to whole dollars."""
    amount = Decimal(amount)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if cents:
        return "%s$%s" % (sign, "{:,.2f}".format(amount.quantize(CENT, rounding=ROUND_HALF_UP)))
    return "%s$%s" % (sign, "{:,.0f}".format(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def format_compact_money(amount):
    """Axis labels: $0, $950, $12K, $1.2M."""
    amount = float(amount)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000:
        text = ("%.1f" % (amount / 1_000_000)).rstrip("0").rstrip(".") + "M"
    elif amount >= 1000:
        text = ("%.1f" % (amount / 1000)).rstrip("0").rstrip(".") + "K"
    else:
        text = "%d" % round(amount)
    return sign + "$" + text
