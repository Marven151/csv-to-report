"""Inline SVG charts, no libraries.

The charts size themselves with percentages instead of a scaled viewBox, so text
stays at its real size on a phone and bars keep square corners where they should.
Colors come from CSS variables (--series-1...), set in the report for light and dark mode.
"""

from decimal import Decimal
from html import escape

from .parsing import format_compact_money, format_money, month_label

BAR = 24          # column thickness, px
RADIUS = 4        # rounded data end
GAP = 2           # surface gap between stacked segments


def nice_ticks(max_value, count=4):
    """Round axis steps: 0, 5K, 10K, 15K... covering max_value."""
    max_value = float(max_value)
    if max_value <= 0:
        return [0, 1]
    raw = max_value / count
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * magnitude
        if step >= raw:
            break
    ticks = [0]
    while ticks[-1] < max_value:
        ticks.append(ticks[-1] + step)
    return ticks


def _attr(s):
    return escape(str(s), quote=True)


def _column(x_pct, y, height, color_var, tip, rounded):
    """One column segment: rounded at the top when `rounded`, square at the bottom."""
    if height <= 0:
        return ""
    parts = ['<g class="mark" tabindex="0" data-tip="%s">' % _attr(tip)]
    common = 'x="%s%%" width="%d" transform="translate(%d 0)" fill="var(%s)"' % (x_pct, BAR, -BAR // 2, color_var)
    if rounded and height > RADIUS:
        parts.append('<rect %s y="%.1f" height="%.1f" rx="%d"/>' % (common, y, height, RADIUS))
        parts.append('<rect %s y="%.1f" height="%.1f"/>' % (common, y + height - RADIUS, RADIUS))
    else:
        parts.append('<rect %s y="%.1f" height="%.1f"/>' % (common, y, height))
    parts.append("</g>")
    return "".join(parts)


def stacked_columns(months, channels, title_id, height=260):
    """Net sales per month, stacked by channel. `months` rows come from summary.summarize()."""
    top_pad, bottom = 28, 32           # room for the total above, month names below
    plot_h = height - top_pad - bottom
    totals = [sum((max(m["by_channel"][c], Decimal(0)) for c in channels), Decimal(0)) for m in months]
    ticks = nice_ticks(max(totals) if totals else 0)
    top = ticks[-1]
    scale = plot_h / top if top else 0

    def y_of(v):
        return top_pad + plot_h - float(v) * scale

    axis = ['<svg class="axis" width="52" height="%d" aria-hidden="true">' % height]
    grid = []
    for t in ticks:
        y = y_of(t)
        axis.append('<text x="44" y="%.1f" text-anchor="end" dominant-baseline="middle">%s</text>' % (y, format_compact_money(t)))
        grid.append('<line x1="0" x2="100%%" y1="%.1f" y2="%.1f" class="%s"/>' % (y, y, "baseline" if t == 0 else "grid"))
    axis.append("</svg>")

    band = 100.0 / max(len(months), 1)
    cols = []
    for i, m in enumerate(months):
        cx = round(band * i + band / 2, 3)
        base = 0.0
        visible = [c for c in channels if m["by_channel"][c] > 0]
        for j, c in enumerate(channels):
            v = m["by_channel"][c]
            if v <= 0:
                continue
            h_full = float(v) * scale
            y_top = y_of(base + float(v))
            is_top = c == visible[-1]
            # The gap is taken from the top of every segment except the highest one.
            h = h_full - (0 if is_top else GAP)
            y = y_top + (0 if is_top else GAP)
            tip = "%s, %s: %s" % (month_label(m["month"]), c, format_money(v))
            cols.append(_column(cx, y, h, "--series-%d" % (j + 1), tip, is_top))
            base += float(v)
        total_y = y_of(base) - 8
        cols.append('<text class="value" x="%s%%" y="%.1f" text-anchor="middle">%s</text>' % (cx, total_y, format_money(totals[i], cents=False)))
        cols.append('<text class="label" x="%s%%" y="%d" text-anchor="middle">%s</text>' % (cx, height - 10, month_label(m["month"], short=True)))

    plot = ('<svg class="plot" width="100%%" height="%d" role="img" aria-labelledby="%s">%s%s</svg>'
            % (height, title_id, "".join(grid), "".join(cols)))
    return '<div class="chart-columns">%s%s</div>' % ("".join(axis), plot)


def horizontal_bars(rows, label_key, value_key, title_id, series_var="--series-1", limit=8, fold=True):
    """A ranked list as bars: label, bar, value. Rows past `limit` are folded into 'Other'
    (or just cut, with fold=False, for a top-N list)."""
    rows = list(rows)
    if len(rows) > limit and not fold:
        rows = rows[:limit]
    elif len(rows) > limit:
        other = sum((r[value_key] for r in rows[limit - 1:]), Decimal(0))
        rows = rows[:limit - 1] + [{label_key: "Other (%d more)" % (len(rows) - limit + 1), value_key: other}]
    peak = max((float(r[value_key]) for r in rows), default=0) or 1
    out = ['<div class="bars" role="img" aria-labelledby="%s">' % title_id]
    for r in rows:
        v = r[value_key]
        pct = max(float(v), 0) / peak * 100
        label = escape(str(r[label_key]))
        out.append(
            '<div class="bar-row mark" tabindex="0" data-tip="%s">'
            '<span class="bar-label">%s</span>'
            '<svg class="bar-track" height="18" aria-hidden="true">'
            '<rect x="0" y="0" height="18" width="%.2f%%" rx="%d" fill="var(%s)"/>'
            '<rect x="0" y="0" height="18" width="%s" fill="var(%s)"/>'
            "</svg>"
            '<span class="bar-value">%s</span></div>'
            % (_attr("%s: %s" % (r[label_key], format_money(v))), label, pct, RADIUS, series_var,
               "%.2f%%" % min(pct, 2) if pct < 2 else RADIUS, series_var, format_money(v, cents=False)))
    out.append("</div>")
    return "".join(out)
