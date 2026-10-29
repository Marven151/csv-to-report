"""Command line: python3 -m csv_to_report exports/*.csv -o report.html"""

import argparse
import glob
import os
import re
import sys

from .report import render
from .sources import read_export
from .summary import clean, load_rules, summarize, write_clean_csv


def build_parser():
    p = argparse.ArgumentParser(
        prog="csv_to_report",
        description="Turn Square, Shopify, QuickBooks or other CSV sales exports into one clean monthly report.")
    p.add_argument("inputs", nargs="+", help="CSV files or folders of CSV files")
    p.add_argument("-o", "--output", default="report.html", help="HTML report to write (default: report.html)")
    p.add_argument("--clean-csv", metavar="FILE", help="also write every cleaned sale line to this CSV")
    p.add_argument("--categories", metavar="FILE", help="CSV of match,category rules for lines without a category")
    p.add_argument("--business", default="", help="business name for the report title")
    p.add_argument("--month", metavar="YYYY-MM", help="only this month")
    p.add_argument("--note", default="", help="a line of text shown under the title")
    return p


def expand(inputs):
    files = []
    for item in inputs:
        if os.path.isdir(item):
            files.extend(sorted(glob.glob(os.path.join(item, "*.csv"))))
        else:
            files.extend(sorted(glob.glob(item)) or [item])
    return files


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.month):
        print("--month must look like 2026-10", file=sys.stderr)
        return 2
    files = expand(args.inputs)
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        print("File not found: " + ", ".join(missing), file=sys.stderr)
        return 2
    if not files:
        print("No CSV files found.", file=sys.stderr)
        return 2

    reports = []
    for f in files:
        try:
            reports.append(read_export(f))
        except (OSError, ValueError) as e:
            print("Cannot read %s: %s" % (f, e), file=sys.stderr)
            return 1
    rules = load_rules(args.categories) if args.categories else []
    records = clean(reports, rules, args.month)
    if not records:
        print("No sales lines found%s." % (" for " + args.month if args.month else ""), file=sys.stderr)
        return 1
    summary = summarize(records)

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(render(summary, reports, business=args.business, note=args.note))
    if args.clean_csv:
        write_clean_csv(records, args.clean_csv)

    for r in reports:
        print("%-28s %-10s %5d rows  %5d used  %4d duplicates  %4d left out"
              % (r.file, r.format, r.rows, r.kept, r.duplicates, len(r.skipped)))
    print("Net sales %s from %d orders, %s to %s -> %s"
          % ("${:,.2f}".format(summary["net"]), summary["orders"], summary["first_date"], summary["last_date"], args.output))
    return 0
