import os
import tempfile
import unittest
from decimal import Decimal

from csv_to_report.sources import detect_format, read_export, read_rows
from csv_to_report.summary import clean, summarize


def write(dirname, name, text, encoding="utf-8"):
    path = os.path.join(dirname, name)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)
    return path


SQUARE = (
    "Date,Time,Category,Item,Qty,Price Point Name,Gross Sales,Discounts,Net Sales  ,Tax,Transaction ID,Event Type,Customer Name\n"
    "10/01/2026,08:00:00,Coffee,Latte,1,Regular,$5.25,$0.00,$5.25,$0.29,T1,Payment,\n"
    "10/01/2026,08:00:00,Coffee,Latte,1,Regular,$5.25,$0.00,$5.25,$0.29,T1,Payment,\n"
    "\n"
    "10/02/2026,09:30:00,Coffee,Drip Coffee,2,Large,$7.90,($0.50),$7.40,$0.41,T2,Payment,  maria   SANTOS \n"
    "10/03/2026,12:00:00,Coffee,Latte,-1,Regular,($5.25),$0.00,($5.25),($0.29),R1,Refund,\n"
    "Total,,,,,,,,,,,,\n"
)

SHOPIFY = (
    "Name,Financial Status,Paid at,Subtotal,Discount Amount,Lineitem quantity,Lineitem name,Lineitem price,Billing Name,Cancelled at,Refunded Amount\n"
    "#1002,paid,2026-10-05 10:00:00 -0400,52.00,5.20,2,Blend - 12 oz Whole Bean,17.00,Maria Santos,,0.00\n"
    "#1002,,,,,1,Ceramic Mug,18.00,,,\n"
    "#1003,refunded,2026-10-06 11:00:00 -0400,17.00,0.00,1,Blend - 12 oz Whole Bean,17.00,Kevin Roy,,23.95\n"
    "#1004,voided,,17.00,0.00,1,Blend - 12 oz Whole Bean,17.00,Ana Costa,2026-10-07 09:00:00 -0400,0.00\n"
    "#1005,pending,,9.00,0.00,1,Brewing Guide,9.00,Ana Costa,,0.00\n"
    "#1002,paid,2026-10-05 10:00:00 -0400,52.00,5.20,2,Blend - 12 oz Whole Bean,17.00,Maria Santos,,0.00\n"
    "#1002,,,,,1,Ceramic Mug,18.00,,,\n"
)

QUICKBOOKS = (
    "Harbor Light Coffee Roasters\n"
    "Sales by Customer Detail\n"
    "\"October 1 - 31, 2026\"\n"
    "\n"
    ",Date,Transaction Type,Num,Product/Service,Memo/Description,Qty,Sales Price,Amount,Balance\n"
    "BAYSIDE BISTRO\n"
    ",10/02/2026,Invoice,3101,Wholesale:House Espresso 5 lb,,2,62.00,124.00,124.00\n"
    ",10/09/2026,Invoice,3102,Wholesale:Decaf 5 lb,,1,\"1,066.00\",\"1,066.00\",\"1,190.00\"\n"
    ",10/12/2026,Credit Memo,CM-1,Wholesale:House Espresso 5 lb,Damaged,1,62.00,62.00,\"1,128.00\"\n"
    ",10/13/2026,Payment,88,,,,,\"-500.00\",628.00\n"
    "Total for BAYSIDE BISTRO,,,,,,,,\"$1,128.00\",\n"
    "Pier 9 Diner\n"
    ",10/03/2026,Sales Receipt,3103,Grinder Rental,,1,45.00,45.00,45.00\n"
    "Total for Pier 9 Diner,,,,,,,,$45.00,\n"
    "TOTAL,,,,,,,,\"$1,173.00\",\n"
    "\n"
    "\"Accrual Basis Monday, November 2, 2026 09:14 AM GMT-05:00\"\n"
)

GENERIC = (
    "Order Date;Customer;Product;Category;Total\n"
    "2026-10-04;Tidewater Market;Gift basket;Gifts;\"40,00\"\n"
    "2026-10-05;;Gift basket;Gifts;40.00\n"
    "not a date;;;;\n"
)


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_formats(self):
        for name, text, fmt in [("sq.csv", SQUARE, "Square"), ("sh.csv", SHOPIFY, "Shopify"),
                                ("qb.csv", QUICKBOOKS, "QuickBooks"), ("other.csv", GENERIC, "CSV")]:
            with self.subTest(fmt=fmt):
                self.assertEqual(detect_format(read_rows(write(self.dir, name, text))), fmt)

    def test_square_reads_refunds_variants_and_skips_totals(self):
        rep = read_export(write(self.dir, "sq.csv", SQUARE, encoding="utf-8-sig"))
        self.assertEqual(rep.rows, 5)
        self.assertEqual(len(rep.records), 4)
        self.assertEqual(rep.skipped, [(7, "total row")])
        drip = rep.records[2]
        self.assertEqual((drip.item, drip.qty, drip.amount, drip.customer), ("Drip Coffee (Large)", Decimal(2), Decimal("7.40"), "maria SANTOS"))
        refund = rep.records[3]
        self.assertEqual((refund.kind, refund.amount, refund.qty), ("refund", Decimal("-5.25"), Decimal(1)))

    def test_identical_lines_in_one_receipt_are_kept(self):
        rep = read_export(write(self.dir, "sq.csv", SQUARE))
        records = clean([rep])
        self.assertEqual(sum(1 for r in records if r.item == "Latte" and r.kind == "sale"), 2)
        self.assertEqual(rep.duplicates, 0)

    def test_overlapping_exports_are_counted_once(self):
        a = read_export(write(self.dir, "a.csv", SQUARE))
        b = read_export(write(self.dir, "b.csv", SQUARE))
        records = clean([a, b])
        self.assertEqual(len(records), 4)
        self.assertEqual((a.duplicates, b.duplicates, a.kept, b.kept), (0, 4, 4, 0))

    def test_shopify_orders(self):
        rep = read_export(write(self.dir, "sh.csv", SHOPIFY))
        sales = [r for r in rep.records if r.kind == "sale"]
        # #1002: 2 x 17 + 18 = 52, 10% discount 5.20 shared by value: 3.40 + 1.80
        self.assertEqual([(r.order_id, r.item, r.amount) for r in sales[:2]],
                         [("#1002", "Blend - 12 oz Whole Bean", Decimal("30.60")), ("#1002", "Ceramic Mug", Decimal("16.20"))])
        self.assertEqual(sales[1].customer, "Maria Santos", "line rows inherit the order's customer")
        refund = [r for r in rep.records if r.kind == "refund"]
        self.assertEqual([(r.order_id, r.amount) for r in refund], [("#1003", Decimal("-17.00"))], "capped at product value")
        reasons = sorted(reason for _, reason in rep.skipped)
        self.assertEqual(reasons, ["cancelled order", "not paid (pending)"])
        self.assertEqual(rep.duplicates, 2, "both rows of the repeated #1002")
        self.assertEqual(sum(r.amount for r in rep.records), Decimal("46.80"))

    def test_quickbooks_report_layout(self):
        rep = read_export(write(self.dir, "qb.csv", QUICKBOOKS))
        got = [(r.customer, r.order_id, r.category, r.item, r.kind, r.amount) for r in rep.records]
        self.assertEqual(got, [
            ("BAYSIDE BISTRO", "3101", "Wholesale", "House Espresso 5 lb", "sale", Decimal("124.00")),
            ("BAYSIDE BISTRO", "3102", "Wholesale", "Decaf 5 lb", "sale", Decimal("1066.00")),
            ("BAYSIDE BISTRO", "CM-1", "Wholesale", "House Espresso 5 lb", "refund", Decimal("-62.00")),
            ("Pier 9 Diner", "3103", "", "Grinder Rental", "sale", Decimal("45.00")),
        ])
        self.assertEqual(rep.skipped, [(10, "not a sale (payment)")])
        # Matches the report's own TOTAL row.
        self.assertEqual(sum(r.amount for r in rep.records), Decimal("1173.00"))

    def test_generic_csv_with_semicolons(self):
        rep = read_export(write(self.dir, "market-stall.csv", GENERIC))
        self.assertEqual(rep.format, "CSV")
        self.assertEqual([(r.channel, r.customer, r.category, r.amount) for r in rep.records],
                         [("Market stall", "Tidewater Market", "Gifts", Decimal("40.00")),
                          ("Market stall", "", "Gifts", Decimal("40.00"))])
        self.assertEqual(rep.skipped, [(4, "no readable date")])

    def test_windows_1252_file(self):
        path = os.path.join(self.dir, "win.csv")
        with open(path, "wb") as f:
            f.write("Date,Customer,Amount\n10/05/2026,Caf\xe9 Rosa,12.00\n".encode("cp1252"))
        rep = read_export(path)
        self.assertEqual(rep.records[0].customer, "Café Rosa")

    def test_summary_numbers(self):
        reports = [read_export(write(self.dir, n, t)) for n, t in [("sq.csv", SQUARE), ("sh.csv", SHOPIFY), ("qb.csv", QUICKBOOKS)]]
        s = summarize(clean(reports))
        self.assertEqual(s["sales"], Decimal("1316.70"))
        self.assertEqual(s["refunds"], Decimal("84.25"))
        self.assertEqual(s["net"], Decimal("1232.45"))
        # Orders: T1, T2, #1002, #1003, 3101, 3102, 3103
        self.assertEqual(s["orders"], 7)
        self.assertEqual([m["month"] for m in s["months"]], ["2026-10"])
        self.assertEqual(s["months"][0]["by_channel"], {"In-store": Decimal("12.65"), "Online": Decimal("46.80"), "Wholesale": Decimal("1173.00")})
        names = [c["customer"] for c in s["customers"]]
        self.assertIn("Bayside Bistro", names, "ALL CAPS names are tidied")
        maria = next(c for c in s["customers"] if c["customer"] == "Maria Santos")
        self.assertEqual((maria["net"], maria["orders"], maria["channels"]), (Decimal("54.20"), 2, "In-store, Online"))


if __name__ == "__main__":
    unittest.main()
