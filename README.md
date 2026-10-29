# csv-to-report

[![tests](https://github.com/Marven151/csv-to-report/actions/workflows/test.yml/badge.svg)](https://github.com/Marven151/csv-to-report/actions/workflows/test.yml)

Turns the sales exports a small business already downloads (Square, Shopify, QuickBooks, or any CSV with a date and an amount) into one clean monthly report: a single HTML file with the totals by month, channel, category and customer, charts included, that opens in any browser and can be emailed or printed.

**Sample report:** https://marven151.github.io/csv-to-report/ (made from the fictional exports in [`samples/exports`](samples/exports))

Python 3.9 or newer, standard library only. Nothing to install.

## What the client gets

- **One report instead of three dashboards.** In-store, online and wholesale sales side by side, per month, with refunds, order counts and the average order.
- **Clean numbers.** Dates in every format the exports use, amounts like `$1,234.50`, `($4.50)` and `4.50-`, duplicates from overlapping downloads removed, cancelled and unpaid orders, subtotal rows and report headers left out, and the same customer spelled two ways counted once.
- **A visible audit trail.** The report lists every file, how many rows were used, how many duplicates were removed, and every row left out with the reason. The totals can be checked against the source systems.
- **A cleaned spreadsheet** (`--clean-csv`) with one row per sale line, ready for Excel or Google Sheets.
- **Sales by category,** including for systems that do not export one (Shopify orders), through a simple rules file: "if the product name contains *whole bean*, it is *Retail Beans*".

### Suggested pricing

| | Price | Delivery |
|---|---|---|
| Setup: the client's real exports mapped, categories set up, first report for the last 3–12 months | $200–$350 | 2–3 business days |
| Monthly report, run by me from the files the client sends | $40–$60 a month | within 1 business day of receiving the files |
| Or: a short screen recording so the client runs it on their own computer | included in setup | |

## How to run

```bash
python3 -m csv_to_report path/to/exports -o report.html
```

Pass files or folders (every `.csv` in the folder is read). Options:

| Option | What it does |
|---|---|
| `-o FILE` | the HTML report to write (default `report.html`) |
| `--clean-csv FILE` | also write every cleaned sale line as a CSV |
| `--categories FILE` | rules for lines without a category, see below |
| `--business NAME` | business name in the title |
| `--month 2026-10` | only that month |
| `--note TEXT` | a line under the title, for example "Draft, October not closed yet" |

The sample report on GitHub Pages was made with:

```bash
python3 -m csv_to_report samples/exports --categories samples/categories.csv \
  --business "Harbor Light Coffee Roasters" \
  --note "Sample report. Harbor Light Coffee Roasters and all its data are fictional." -o index.html
```

The terminal shows a line per file (rows, lines used, duplicates, rows left out) and the net total.

### Category rules

A CSV with `match` and `category` columns. For each line that has no category, the first rule whose `match` text appears in the item name (upper or lower case) wins:

```csv
match,category
whole bean,Retail Beans
subscription,Subscriptions
mug,Merch
```

Lines that match nothing are reported as Uncategorized, and the report says how much money that is.

## Supported exports

| Export | How it is recognized | What is read |
|---|---|---|
| Square, Item Sales detail | `Transaction ID`, `Net Sales`, `Event Type` columns | each item line; refunds by event type; price point names like "Large" added to the item |
| Shopify, Orders export | `Lineitem name`, `Financial Status` columns | each line item, with the order's discount shared across its lines by value; cancelled, voided and unpaid orders left out; refunds from `Refunded Amount` |
| QuickBooks Online, Sales by Customer Detail | `Transaction Type`, `Num`, `Amount` columns | invoices and sales receipts as sales, credit memos and refund receipts as refunds; title rows, customer headings and `Total for...` rows skipped; `Category:Item` names split into category and item |
| Anything else | a date column and an amount column, by common names (`Date`, `Order Date`, `Created at`... and `Amount`, `Total`, `Net Sales`...) | one sale per row; negative amounts are refunds; commas, semicolons and tabs as separators; UTF-8 or Windows-1252 |

The fixtures and samples follow the column layouts of these exports as the vendors document them; the samples were not downloaded from live accounts. Part of every setup is running the client's first real exports through the tool and checking the totals against what Square, Shopify and QuickBooks show.

### Definitions and known limits

- **Net sales** = item sales after discounts, before sales tax, tips and shipping, minus refunds.
- **Orders** counts each receipt, online order or invoice once. Refund-only transactions are not orders.
- **Duplicates.** A line counts once per system even when it appears in two files with overlapping dates. Identical lines inside one file are kept, because one receipt can really contain two separate, identical items. So if someone pasted the same rows twice into one file, the tool cannot tell, and they are counted twice. For generic CSVs without an order or transaction ID column, duplicates across files cannot be detected either.
- **Shopify refunds.** The orders export has one refunded total per order and no refund date, so a Shopify refund is counted on the order date and capped at the order's product value (the refunded total can include tax and shipping). For exact refund timing, add Shopify's payouts or transactions export as a generic CSV instead.
- **Dates** are read month-first (`03/04/2026` is March 4), as US exports write them.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

23 tests: date and money parsing (including the formats above and the ones that must be refused), each export format from small fixtures, duplicate handling within and across files, discount sharing, refund capping, customer name merging, the summary numbers, and the command line. The main end-to-end test runs the tool on the sample exports and checks its totals against figures worked out directly from the raw files (Square's net sales column, Shopify's order subtotals, and the TOTAL row of the QuickBooks report): they match to the cent, $33,370.00.

The sample exports are generated by [`samples/make_samples.py`](samples/make_samples.py) (fixed random seed, so the output is the same every run). Harbor Light Coffee Roasters, its customers and all numbers are made up.

## Credits

Built by Marcin Świerczyński ([Marven151](https://github.com/Marven151)). MIT License.
