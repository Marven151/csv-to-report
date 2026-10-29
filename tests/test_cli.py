import contextlib
import csv
import io
import os
import re
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal

from csv_to_report.charts import nice_ticks
from csv_to_report.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS = os.path.join(ROOT, "samples", "exports")
RULES = os.path.join(ROOT, "samples", "categories.csv")


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_dicts(path, encoding="utf-8"):
    with open(path, newline="", encoding=encoding) as f:
        return list(csv.DictReader(f))


def read_lists(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def money(text):
    text = text.strip()
    negative = text.startswith("(") or text.startswith("-")
    value = Decimal(text.strip("()-$").replace(",", "") or "0")
    return -value if negative else value


def expected_totals():
    """Totals worked out straight from the sample files, without the tool, using what we
    know about them: the second Square file repeats September 15-30 of the first."""
    sq1 = read_dicts(os.path.join(EXPORTS, "square_items_2026-08-01_2026-09-30.csv"), "utf-8-sig")
    sq2 = read_dicts(os.path.join(EXPORTS, "square_items_2026-09-15_2026-10-31.csv"), "utf-8-sig")
    net = next(k for k in sq1[0] if k.strip() == "Net Sales")
    square = sum(money(r[net]) for r in sq1 if r["Date"] not in ("", "Total"))
    square += sum(money(r[net]) for r in sq2 if datetime.strptime(r["Date"], "%m/%d/%Y").date() > date(2026, 9, 30))

    shopify, seen = Decimal(0), set()
    for r in read_dicts(os.path.join(EXPORTS, "shopify_orders_export.csv")):
        if r["Financial Status"] and r["Name"] not in seen:
            seen.add(r["Name"])
            if r["Financial Status"] in ("paid", "partially_refunded", "refunded"):
                value = Decimal(r["Subtotal"]) - Decimal(r["Discount Amount"])
                shopify += value - min(Decimal(r["Refunded Amount"]), value)

    total_row = next(r for r in read_lists(os.path.join(EXPORTS, "quickbooks_sales_by_customer.csv")) if r and r[0] == "TOTAL")
    return square, shopify, money(total_row[8])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.html = os.path.join(self.tmp.name, "report.html")
        self.clean = os.path.join(self.tmp.name, "clean.csv")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sample_report_reconciles_with_the_source_files(self):
        code, out, err = run(EXPORTS, "--categories", RULES, "--business", "Harbor Light Coffee Roasters",
                             "-o", self.html, "--clean-csv", self.clean)
        self.assertEqual(code, 0, err)
        square, shopify, quickbooks = expected_totals()
        total = square + shopify + quickbooks

        html = read_text(self.html)
        self.assertIn("<title>Harbor Light Coffee Roasters sales report, August to October 2026</title>", html)
        self.assertIn("<td>Total</td><td class=num>$%s</td><td class=num>$%s</td><td class=num>$%s</td>"
                      % ("{:,.2f}".format(square), "{:,.2f}".format(shopify), "{:,.2f}".format(quickbooks)), html)
        self.assertIn("$%s" % "{:,.2f}".format(total), html)
        self.assertIn("Net sales $%s" % "{:,.2f}".format(total), out)

        rows = read_dicts(self.clean)
        self.assertEqual(sum(Decimal(r["amount"]) for r in rows), total)
        self.assertEqual(len({(r["source"], r["order_id"]) for r in rows if r["kind"] == "sale"}),
                         int(re.search(r"from (\d+) orders", out).group(1)))
        self.assertTrue(all(re.fullmatch(r"2026-(08|09|10)-\d\d", r["date"]) for r in rows))
        self.assertEqual({r["category"] for r in rows if r["kind"] == "sale"},
                         {"Coffee", "Pastry", "Retail Beans", "Merch", "Subscriptions", "Wholesale", "Equipment", "Uncategorized"})
        self.assertEqual(len({r["customer"] for r in rows if r["customer"].lower() == "maria santos"}), 1)
        self.assertNotIn("BAYSIDE BISTRO", {r["customer"] for r in rows})

    def test_report_is_self_contained(self):
        run(EXPORTS, "-o", self.html)
        html = read_text(self.html)
        self.assertNotRegex(html, r'<(script|link|img)[^>]+(src|href)="https?://', "no external files")
        self.assertEqual(html.count('<svg class="plot"'), 1)
        self.assertGreaterEqual(html.count('class="bar-row mark"'), 8)
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertNotIn("{{", html)
        self.assertNotIn("%(", html)

    def test_single_month(self):
        code, out, _ = run(EXPORTS, "--month", "2026-09", "-o", self.html, "--clean-csv", self.clean)
        self.assertEqual(code, 0)
        rows = read_dicts(self.clean)
        self.assertTrue(rows and all(r["month"] == "2026-09" for r in rows))
        self.assertIn("<title>Sales report, September 2026</title>", read_text(self.html))

    def test_errors(self):
        self.assertEqual(run("nope.csv", "-o", self.html)[0], 2)
        self.assertEqual(run(EXPORTS, "--month", "2026-13", "-o", self.html)[0], 2)
        code, _, err = run(EXPORTS, "--month", "2019-01", "-o", self.html)
        self.assertEqual(code, 1)
        self.assertIn("No sales lines found for 2019-01", err)
        self.assertFalse(os.path.exists(self.html))

    def test_axis_ticks(self):
        self.assertEqual(nice_ticks(11658), [0, 5000, 10000, 15000])
        self.assertEqual(nice_ticks(950), [0, 250, 500, 750, 1000])
        self.assertEqual(nice_ticks(0), [0, 1])


if __name__ == "__main__":
    unittest.main()
