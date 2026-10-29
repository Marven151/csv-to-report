import unittest
from datetime import date
from decimal import Decimal

from csv_to_report.parsing import (format_compact_money, format_money, month_label, normalize_header,
                                   parse_date, parse_money, parse_qty)


class ParseDateTest(unittest.TestCase):
    def test_formats_seen_in_exports(self):
        cases = {
            "10/03/2026": date(2026, 10, 3),
            "10/3/26": date(2026, 10, 3),
            "2026-10-03": date(2026, 10, 3),
            "2026-10-03 14:22:31 -0400": date(2026, 10, 3),
            "2026-10-03T23:59:00-07:00": date(2026, 10, 3),
            "10/03/2026 14:22": date(2026, 10, 3),
            "10/3/2026 2:15 PM": date(2026, 10, 3),
            "Oct 3, 2026": date(2026, 10, 3),
            "October 3, 2026": date(2026, 10, 3),
            "03-Oct-2026": date(2026, 10, 3),
            "  10/03/2026  ": date(2026, 10, 3),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_date(text), expected)

    def test_month_first_for_us_exports(self):
        self.assertEqual(parse_date("03/04/2026"), date(2026, 3, 4))

    def test_not_dates(self):
        for text in ["", None, "Total", "N/A", "13/45/2026", "Accrual Basis"]:
            with self.subTest(text=text):
                self.assertIsNone(parse_date(text))


class ParseMoneyTest(unittest.TestCase):
    def test_amounts(self):
        cases = {
            "$1,234.50": Decimal("1234.50"),
            "1234.5": Decimal("1234.50"),
            "($4.50)": Decimal("-4.50"),
            "(4.50)": Decimal("-4.50"),
            "-$4.50": Decimal("-4.50"),
            "4.50-": Decimal("-4.50"),
            "USD 12": Decimal("12.00"),
            "12.00 USD": Decimal("12.00"),
            "$0.00": Decimal("0.00"),
            ".5": Decimal("0.50"),
            "2.675": Decimal("2.68"),
            "+3": Decimal("3.00"),
            "1,066.00": Decimal("1066.00"),
            "$12,345,678.9": Decimal("12345678.90"),
            "40,00": Decimal("40.00"),
            "-1,5": Decimal("-1.50"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_money(text), expected)

    def test_empty_is_none_not_zero(self):
        self.assertIsNone(parse_money(""))
        self.assertIsNone(parse_money(None))
        self.assertIsNone(parse_money("abc"))
        self.assertIsNone(parse_money("$"))
        self.assertIsNone(parse_money("1,23,4"))
        self.assertIsNone(parse_money("12,3456"))

    def test_numbers_pass_through(self):
        self.assertEqual(parse_money(3), Decimal("3.00"))
        self.assertEqual(parse_money(0.1 + 0.2), Decimal("0.30"))


class FormattingTest(unittest.TestCase):
    def test_money(self):
        self.assertEqual(format_money(Decimal("1234.5")), "$1,234.50")
        self.assertEqual(format_money(Decimal("-12")), "-$12.00")
        self.assertEqual(format_money(Decimal("33370.49"), cents=False), "$33,370")
        self.assertEqual(format_money(Decimal("0.5"), cents=False), "$1")

    def test_compact(self):
        self.assertEqual(format_compact_money(0), "$0")
        self.assertEqual(format_compact_money(950), "$950")
        self.assertEqual(format_compact_money(12000), "$12K")
        self.assertEqual(format_compact_money(2500), "$2.5K")
        self.assertEqual(format_compact_money(1200000), "$1.2M")

    def test_misc(self):
        self.assertEqual(parse_qty("2"), Decimal(2))
        self.assertEqual(parse_qty(""), Decimal(1))
        self.assertEqual(parse_qty("1,000"), Decimal(1000))
        self.assertEqual(parse_qty("abc"), Decimal(1))
        self.assertEqual(normalize_header("﻿Net Sales  "), "net sales")
        self.assertEqual(normalize_header("Product/Service"), "product service")
        self.assertEqual(month_label("2026-10"), "October 2026")
        self.assertEqual(month_label("2026-10", short=True), "Oct 2026")


if __name__ == "__main__":
    unittest.main()
