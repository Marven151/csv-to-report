"""The single self-contained HTML report."""

from collections import Counter
from datetime import date
from html import escape

from .charts import horizontal_bars, stacked_columns
from .parsing import format_money, month_label

# Categorical slots in fixed order (validated: light and dark, first three all-pairs).
SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
CHANNEL_ORDER = ["In-store", "Online", "Wholesale"]

CSS = """
:root {
  color-scheme: light;
  --bg: #f4f4f1; --surface: #fcfcfb; --step: #ecebe6;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #6f6d68;
  --grid: #e1e0d9; --base: #b9b7ae; --warn-bg: #fff4d6;
%(light)s
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #111110; --surface: #1a1a19; --step: #242422;
    --ink: #f0efec; --ink-2: #c3c2b7; --muted: #9b998f;
    --grid: #2c2c2a; --base: #4a4945; --warn-bg: #3a3215;
%(dark)s
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #111110; --surface: #1a1a19; --step: #242422;
  --ink: #f0efec; --ink-2: #c3c2b7; --muted: #9b998f;
  --grid: #2c2c2a; --base: #4a4945; --warn-bg: #3a3215;
%(dark)s
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  -webkit-text-size-adjust: 100%%; }
main { max-width: 1040px; margin: 0 auto; padding: 40px 20px 64px; }
h1 { font-size: clamp(28px, 4.4vw, 44px); line-height: 1.1; letter-spacing: -0.02em; margin: 0; }
h2 { font-size: 22px; line-height: 1.25; margin: 0 0 4px; }
.sub { color: var(--ink-2); margin: 8px 0 0; font-size: 17px; }
.note { display: inline-block; margin: 14px 0 0; padding: 6px 12px; border-radius: 6px; background: var(--warn-bg); font-size: 15px; }
.tiles { display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr; gap: 12px; margin: 32px 0; }
.tile { background: var(--surface); border-radius: 12px; padding: 18px 20px; }
.tile-label { color: var(--ink-2); font-size: 15px; margin: 0; }
.tile-value { font-size: 30px; font-weight: 650; letter-spacing: -0.01em; margin: 4px 0 0; font-variant-numeric: tabular-nums; }
.tile-hero .tile-value { font-size: 48px; line-height: 1.1; }
.tile-note { color: var(--muted); font-size: 14px; margin: 4px 0 0; }
section.card { background: var(--surface); border-radius: 12px; padding: 24px; margin-top: 16px; }
.card-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px 24px; margin-bottom: 16px; }
.card-head p { margin: 0; color: var(--ink-2); }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-2 section.card { margin-top: 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0; padding: 0; list-style: none; font-size: 15px; color: var(--ink-2); }
.legend li { display: flex; align-items: center; gap: 8px; }
.legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.chart-columns { display: flex; }
.chart-columns svg { display: block; overflow: visible; }
.chart-columns .axis { flex: none; }
.chart-columns .plot { flex: 1 1 auto; min-width: 0; }
.axis text { fill: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.plot .grid { stroke: var(--grid); stroke-width: 1; }
.plot .baseline { stroke: var(--base); stroke-width: 1; }
.plot .value { fill: var(--ink); font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
.plot .label { fill: var(--ink-2); font-size: 14px; }
.mark { outline: none; cursor: default; }
.mark:hover rect, .mark:focus-visible rect { opacity: 0.8; }
.mark:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
.bars { display: grid; gap: 10px; }
.bar-row { display: grid; grid-template-columns: minmax(96px, 34%%) 1fr 72px; align-items: center; gap: 12px; }
.bar-label { font-size: 15px; overflow-wrap: anywhere; line-height: 1.25; }
.bar-track { width: 100%%; display: block; }
.bar-value { text-align: right; font-variant-numeric: tabular-nums; font-size: 15px; font-weight: 600; }
table { width: 100%%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 15px; }
th, td { text-align: left; padding: 8px 10px; }
th { color: var(--ink-2); font-weight: 600; border-bottom: 1px solid var(--grid); }
td { border-bottom: 1px solid var(--grid); }
td.num, th.num { text-align: right; }
tfoot td { font-weight: 650; border-bottom: 0; }
.table-wrap { overflow-x: auto; margin-top: 20px; }
details { margin-top: 16px; }
summary { cursor: pointer; color: var(--ink-2); }
.notes { color: var(--ink-2); font-size: 15px; max-width: 70ch; }
.notes li + li { margin-top: 6px; }
.flag { background: var(--warn-bg); padding: 2px 6px; border-radius: 4px; }
footer { color: var(--muted); font-size: 14px; margin-top: 32px; }
footer a { color: inherit; }
#tip { position: fixed; pointer-events: none; background: var(--ink); color: var(--surface); font-size: 14px;
  padding: 6px 10px; border-radius: 6px; white-space: nowrap; opacity: 0; transition: opacity .1s; z-index: 5; }
@media (max-width: 760px) {
  main { padding: 28px 16px 48px; }
  .tiles { grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .tile-hero { grid-column: 1 / -1; }
  .tile { padding: 14px; }
  .tile-label { font-size: 14px; }
  .tile-value { font-size: 22px; }
  .grid-2 { grid-template-columns: 1fr; }
  section.card { padding: 18px 16px; }
  .bar-row { grid-template-columns: minmax(84px, 38%%) 1fr 64px; gap: 8px; }
}
@media (prefers-reduced-motion: reduce) { #tip { transition: none; } }
@media print { #tip { display: none; } body { background: #fff; } section.card, .tile { break-inside: avoid; } }
"""

SCRIPT = """
(function () {
  var tip = document.getElementById('tip');
  function show(el, x, y) {
    tip.textContent = el.getAttribute('data-tip');
    tip.style.opacity = 1;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(x - w / 2, window.innerWidth - w - 8)) + 'px';
    tip.style.top = Math.max(8, y - h - 12) + 'px';
  }
  function hide() { tip.style.opacity = 0; }
  document.querySelectorAll('.mark').forEach(function (el) {
    el.addEventListener('mousemove', function (e) { show(el, e.clientX, e.clientY); });
    el.addEventListener('mouseleave', hide);
    el.addEventListener('focus', function () { var r = el.getBoundingClientRect(); show(el, r.left + r.width / 2, r.top); });
    el.addEventListener('blur', hide);
  });
})();
"""


def _series_vars(colors):
    return "\n".join("  --series-%d: %s;" % (i + 1, c) for i, c in enumerate(colors))


def _period(summary):
    a, b = summary["first_date"], summary["last_date"]
    if not a:
        return "No sales found"
    if a.year == b.year and a.month == b.month:
        return month_label("%04d-%02d" % (a.year, a.month))
    if a.year == b.year:
        return "%s to %s" % (a.strftime("%B"), b.strftime("%B %Y"))
    return "%s to %s" % (a.strftime("%B %Y"), b.strftime("%B %Y"))


def order_channels(channels):
    known = [c for c in CHANNEL_ORDER if c in channels]
    return known + sorted(c for c in channels if c not in known)


def _tile(label, value, note="", hero=False):
    return ('<div class="tile%s"><p class="tile-label">%s</p><p class="tile-value">%s</p>%s</div>'
            % (" tile-hero" if hero else "", escape(label), escape(value),
               '<p class="tile-note">%s</p>' % escape(note) if note else ""))


def _quality_rows(reports):
    rows = []
    for rep in reports:
        reasons = Counter(reason for _, reason in rep.skipped)
        detail = "; ".join("%s (%d)" % (r, n) for r, n in reasons.most_common()) or "none"
        rows.append("<tr><td>%s</td><td>%s</td><td class=num>%d</td><td class=num>%d</td><td class=num>%d</td><td>%s</td></tr>"
                    % (escape(rep.file), escape(rep.format), rep.rows, rep.kept,
                       rep.duplicates, escape(detail)))
    return "".join(rows)


def render(summary, reports, business="", source_note="", generated=None, note=""):
    generated = generated or date.today()
    channels = order_channels(summary["channels"])
    colors_l = SERIES_LIGHT[:len(channels)]
    colors_d = SERIES_DARK[:len(channels)]
    name = business.strip()
    title = "%s sales report" % name if name else "Sales report"
    months = summary["months"]

    legend = "".join('<li><i style="background:var(--series-%d)"></i>%s</li>' % (i + 1, escape(c)) for i, c in enumerate(channels))
    month_table = "".join(
        "<tr><td>%s</td>%s<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
        % (month_label(m["month"]),
           "".join("<td class=num>%s</td>" % format_money(m["by_channel"][c]) for c in channels),
           format_money(m["refunds"]), format_money(m["net"]), "{:,}".format(m["orders"]), format_money(m["average"]))
        for m in months)
    month_foot = ("<tr><td>Total</td>%s<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td></tr>"
                  % ("".join("<td class=num>%s</td>" % format_money(sum((m["by_channel"][c] for m in months), 0)) for c in channels),
                     format_money(summary["refunds"]), format_money(summary["net"]), "{:,}".format(summary["orders"]),
                     format_money(summary["average"])))

    cats = summary["categories"]
    cat_total = sum((c["sales"] for c in cats), 0) or 1
    cat_table = "".join("<tr><td>%s</td><td class=num>%s</td><td class=num>%.1f%%</td></tr>"
                        % (escape(c["category"]), format_money(c["sales"]), float(c["sales"]) / float(cat_total) * 100) for c in cats)
    custs = summary["customers"]
    cust_table = "".join("<tr><td>%s</td><td>%s</td><td class=num>%d</td><td class=num>%s</td></tr>"
                         % (escape(c["customer"]), escape(c["channels"]), c["orders"], format_money(c["net"])) for c in custs[:25])

    best = max(months, key=lambda m: m["net"]) if months else None
    first, last = (months[0], months[-1]) if months else (None, None)
    change = ""
    if first and last and first is not last and first["net"]:
        pct = (float(last["net"]) - float(first["net"])) / float(first["net"]) * 100
        change = "%s%.0f%% from %s to %s" % ("+" if pct >= 0 else "", pct, month_label(first["month"], True), month_label(last["month"], True))
    uncategorized = next((c for c in cats if c["category"] == "Uncategorized"), None)
    skipped_total = sum(len(r.skipped) for r in reports)
    dupes_total = sum(r.duplicates for r in reports)

    notes = [
        "Sales are net of discounts and before sales tax, tips and shipping. Refunds are subtracted in the month they appear in the export.",
        "Orders counts each receipt, online order or invoice once, however many items it has.",
        "Duplicates are lines that appear twice in the same system's exports (for example two downloads with overlapping dates); %d were removed." % dupes_total,
        "%d rows were left out because they were not sales: cancelled or unpaid orders, total rows, or rows without a date or amount. Each one is listed by file below." % skipped_total,
    ]
    if any(r.format == "Shopify" for r in reports):
        notes.append("Shopify's order export shows one refunded total per order and no refund date, so Shopify refunds are counted on the order date and capped at the order's product value.")
    if uncategorized:
        notes.append('<span class="flag">%s of sales has no category</span>. Add rules to a categories file to sort these lines.' % format_money(uncategorized["sales"]))

    skipped_list = "".join(
        "<tr><td>%s</td><td class=num>%d</td><td>%s</td></tr>" % (escape(rep.file), line, escape(reason))
        for rep in reports for line, reason in rep.skipped[:200])

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s, %(period)s</title>
<style>%(css)s</style>
</head>
<body>
<main>
<header>
  <h1>%(title)s</h1>
  <p class="sub">%(period)s, from %(file_count)d exports (%(source_note)s)</p>
  %(note)s
</header>

<div class="tiles">
  %(tile_net)s
  %(tile_orders)s
  %(tile_avg)s
  %(tile_refunds)s
</div>

<section class="card" aria-labelledby="t-month">
  <div class="card-head">
    <div><h2 id="t-month">Net sales by month</h2><p>%(month_note)s</p></div>
    <ul class="legend" aria-label="Sales channels">%(legend)s</ul>
  </div>
  %(month_chart)s
  <div class="table-wrap">
    <table>
      <caption class="sr" style="position:absolute;left:-9999px">Net sales by month and channel</caption>
      <thead><tr><th>Month</th>%(channel_heads)s<th class=num>Refunds</th><th class=num>Net sales</th><th class=num>Orders</th><th class=num>Average order</th></tr></thead>
      <tbody>%(month_table)s</tbody>
      <tfoot>%(month_foot)s</tfoot>
    </table>
  </div>
</section>

<div class="grid-2">
  <section class="card" aria-labelledby="t-cat">
    <div class="card-head"><div><h2 id="t-cat">Sales by category</h2><p>Before refunds</p></div></div>
    %(cat_chart)s
    <details><summary>All categories as a table</summary>
      <div class="table-wrap"><table><thead><tr><th>Category</th><th class=num>Sales</th><th class=num>Share</th></tr></thead><tbody>%(cat_table)s</tbody></table></div>
    </details>
  </section>
  <section class="card" aria-labelledby="t-cust">
    <div class="card-head"><div><h2 id="t-cust">Top customers</h2><p>Named customers only; walk-in sales have no name</p></div></div>
    %(cust_chart)s
    <details><summary>Top 25 customers as a table</summary>
      <div class="table-wrap"><table><thead><tr><th>Customer</th><th>Channel</th><th class=num>Orders</th><th class=num>Net sales</th></tr></thead><tbody>%(cust_table)s</tbody></table></div>
    </details>
  </section>
</div>

<section class="card" aria-labelledby="t-data">
  <div class="card-head"><div><h2 id="t-data">How the numbers were made</h2></div></div>
  <ul class="notes">%(notes)s</ul>
  <div class="table-wrap">
    <table>
      <thead><tr><th>File</th><th>Format</th><th class=num>Rows</th><th class=num>Lines used</th><th class=num>Duplicates</th><th>Left out</th></tr></thead>
      <tbody>%(quality)s</tbody>
    </table>
  </div>
  <details><summary>Every row that was left out</summary>
    <div class="table-wrap"><table><thead><tr><th>File</th><th class=num>Row</th><th>Reason</th></tr></thead><tbody>%(skipped)s</tbody></table></div>
  </details>
</section>

<footer>
  <p>Generated %(generated)s with <a href="https://github.com/Marven151/csv-to-report">csv-to-report</a>. %(lines)s sale lines.</p>
</footer>
</main>
<div id="tip" role="presentation"></div>
<script>%(script)s</script>
</body>
</html>
""" % {
        "title": escape(title),
        "period": escape(_period(summary)),
        "css": CSS % {"light": _series_vars(colors_l), "dark": "  " + _series_vars(colors_d).replace("\n", "\n  ")},
        "file_count": len(reports),
        "source_note": escape(source_note or ", ".join(sorted({r.format for r in reports}))),
        "tile_net": _tile("Net sales", format_money(summary["net"], cents=False), change, hero=True),
        "tile_orders": _tile("Orders", "{:,}".format(summary["orders"])),
        "tile_avg": _tile("Average order", format_money(summary["average"])),
        "tile_refunds": _tile("Refunds", format_money(summary["refunds"], cents=False),
                              "%d refund%s" % (summary["refund_count"], "" if summary["refund_count"] == 1 else "s")),
        "month_note": escape("Best month: %s, %s" % (month_label(best["month"]), format_money(best["net"], cents=False)) if best else ""),
        "legend": legend,
        "month_chart": stacked_columns(months, channels, "t-month"),
        "channel_heads": "".join("<th class=num>%s</th>" % escape(c) for c in channels),
        "month_table": month_table,
        "month_foot": month_foot,
        "cat_chart": horizontal_bars(cats, "category", "sales", "t-cat"),
        "cat_table": cat_table,
        "cust_chart": horizontal_bars(custs, "customer", "net", "t-cust", limit=8, fold=False) if custs else "<p>No customer names in these exports.</p>",
        "cust_table": cust_table,
        "notes": "".join("<li>%s</li>" % n for n in notes),
        "quality": _quality_rows(reports),
        "skipped": skipped_list or '<tr><td colspan="3">None</td></tr>',
        "generated": generated.strftime("%B %d, %Y").replace(" 0", " "),
        "lines": "{:,}".format(summary["lines"]),
        "script": SCRIPT,
        "note": '<p class="note">%s</p>' % escape(note) if note else "",
    }
