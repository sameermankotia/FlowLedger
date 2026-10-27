"""Build the static FlowLedger site published on GitHub Pages.

GitHub Pages serves static files only, so the Streamlit dashboard cannot run
there. This renders the same reports and the same chart specifications into
one self-contained HTML page: a snapshot of the database as of the build,
not a live query.

    python scripts/build_site.py              # writes docs/index.html
    python scripts/build_site.py --out site   # somewhere else

The charts are the Altair objects from src/dashboard.py, serialised to
Vega-Lite and embedded, so the page and the dashboard cannot drift apart.
Importing them logs three harmless Streamlit cache warnings, because there is
no Streamlit runtime here; they can be ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from sqlalchemy import text

from src import theme
from src.config import make_engine
from src.dashboard import (
    chart_aging,
    chart_margin,
    chart_monthly,
    chart_rejections,
    chart_top_customers,
)
from src.reports import format_cell, load_queries, run_report

REPO_URL = "https://github.com/sameermankotia/FlowLedger"

# Pinned to the Vega-Lite version Altair 6.3 emits (v6.4.1).
VEGA = "https://cdn.jsdelivr.net/npm/vega@6.4.0/build/vega.min.js"
VEGA_LITE = "https://cdn.jsdelivr.net/npm/vega-lite@6.4.1/build/vega-lite.min.js"
VEGA_EMBED = "https://cdn.jsdelivr.net/npm/vega-embed@7.3.0/build/vega-embed.min.js"

HEADLINE_SQL = """
    SELECT
        (SELECT count(*) FROM customers)                              AS customers,
        (SELECT count(*) FROM projects)                               AS projects,
        (SELECT count(*) FROM invoices)                               AS invoices,
        (SELECT COALESCE(SUM(amount), 0) FROM invoices
          WHERE status <> 'Void')                                     AS total_invoiced,
        (SELECT COALESCE(SUM(amount_paid), 0) FROM invoices
          WHERE status <> 'Void')                                     AS total_collected,
        (SELECT COALESCE(SUM(amount - amount_paid), 0) FROM invoices
          WHERE status NOT IN ('Paid', 'Void'))                       AS outstanding,
        (SELECT COALESCE(SUM(amount - amount_paid), 0) FROM invoices
          WHERE status NOT IN ('Paid', 'Void')
            AND due_date < CURRENT_DATE)                              AS overdue
"""

RUN_SQL = """
    SELECT run_id, status, started_at, rows_extracted, rows_loaded,
           rows_inserted, rows_updated, rows_rejected
      FROM pipeline_runs ORDER BY run_id DESC LIMIT 1
"""


def money(value) -> str:
    return f"${Decimal(value):,.0f}"


def html_table(frame: pd.DataFrame, limit: int | None = None) -> str:
    """Render a report frame as an HTML table, formatted like the CLI does."""
    if frame.empty:
        return '<p class="empty">No rows.</p>'
    shown = frame.head(limit) if limit else frame
    numeric = {
        column
        for column in frame.columns
        if frame[column].map(lambda v: isinstance(v, (Decimal, float, int))).any()
    }
    head = "".join(
        f'<th class="{"num" if c in numeric else ""}">{escape(c.replace("_", " "))}</th>'
        for c in shown.columns
    )
    rows = []
    for _, row in shown.iterrows():
        cells = "".join(
            f'<td class="{"num" if c in numeric else ""}">'
            f"{escape(format_cell(c, row[c]))}</td>"
            for c in shown.columns
        )
        rows.append(f"<tr>{cells}</tr>")
    note = ""
    if limit and len(frame) > limit:
        note = f'<p class="note">Showing {limit} of {len(frame):,} rows.</p>'
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>{note}"
    )


def chart_div(slot: str, chart) -> str:
    return f'<div class="chart" id="{slot}"></div>'


def build(out_dir: Path) -> Path:
    engine = make_engine()
    theme.register()

    with engine.connect() as conn:
        kpi = dict(conn.execute(text(HEADLINE_SQL)).mappings().one())
        run_row = conn.execute(text(RUN_SQL)).mappings().first()
    if run_row is None:
        raise SystemExit(
            "The database has no pipeline runs. Run `make pipeline` first."
        )
    run = dict(run_row)

    queries = load_queries()

    def rpt(name: str) -> pd.DataFrame:
        return run_report(engine, queries[name])

    reports = {
        name: rpt(name)
        for name in (
            "revenue_by_month", "ar_aging_summary", "overdue_invoices",
            "customer_balances", "customer_revenue_rank", "project_profitability",
            "projects_over_budget", "rejection_summary",
            "rejected_records_detail", "pipeline_run_history", "load_audit_detail",
        )
    }

    specs = {
        "chart-monthly": chart_monthly(reports["revenue_by_month"]).to_dict(),
        "chart-aging": chart_aging(reports["ar_aging_summary"]).to_dict(),
        "chart-customers": chart_top_customers(
            reports["customer_revenue_rank"]
        ).to_dict(),
        "chart-margin": chart_margin(reports["project_profitability"]).to_dict(),
        "chart-rejections": chart_rejections(reports["rejection_summary"]).to_dict(),
    }

    collected_pct = (
        100 * Decimal(kpi["total_collected"]) / Decimal(kpi["total_invoiced"])
        if kpi["total_invoiced"] else Decimal(0)
    )
    overdue_pct = (
        100 * Decimal(kpi["overdue"]) / Decimal(kpi["outstanding"])
        if kpi["outstanding"] else Decimal(0)
    )

    tiles = [
        ("Total invoiced", money(kpi["total_invoiced"]),
         f"{kpi['invoices']:,} invoices, excluding void", ""),
        ("Collected", money(kpi["total_collected"]),
         f"{collected_pct:.1f}% of invoiced", ""),
        ("Outstanding", money(kpi["outstanding"]),
         "open and partly paid invoices", ""),
        ("Overdue", money(kpi["overdue"]),
         f"{overdue_pct:.1f}% of outstanding past due",
         "critical" if overdue_pct > 50 else "warning"),
        ("Rejected rows", f"{run['rows_rejected']:,}",
         f"of {run['rows_extracted']:,} extracted", ""),
    ]
    tile_html = "".join(
        f'<div class="tile"><div class="tile-label">{escape(label)}</div>'
        f'<div class="tile-value {tone}">{escape(value)}</div>'
        f'<div class="tile-note">{escape(note)}</div></div>'
        for label, value, note, tone in tiles
    )

    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = PAGE.format(
        repo=REPO_URL,
        built=built,
        vega=VEGA,
        vega_lite=VEGA_LITE,
        vega_embed=VEGA_EMBED,
        tiles=tile_html,
        customers=f"{kpi['customers']:,}",
        projects=f"{kpi['projects']:,}",
        invoices=f"{kpi['invoices']:,}",
        extracted=f"{run['rows_extracted']:,}",
        loaded=f"{run['rows_loaded']:,}",
        rejected=f"{run['rows_rejected']:,}",
        run_id=run["run_id"],
        t_overdue=html_table(reports["overdue_invoices"]),
        t_balances=html_table(reports["customer_balances"], limit=15),
        t_customers=html_table(reports["customer_revenue_rank"], limit=20),
        t_projects=html_table(reports["project_profitability"], limit=20),
        t_overbudget=html_table(reports["projects_over_budget"], limit=15),
        t_rejections=html_table(reports["rejection_summary"]),
        t_rejected_detail=html_table(reports["rejected_records_detail"]),
        t_runs=html_table(reports["pipeline_run_history"]),
        t_audit=html_table(reports["load_audit_detail"]),
        specs=json.dumps(specs, default=str),
        surface=theme.SURFACE, plane=theme.PLANE, ink=theme.INK,
        ink2=theme.INK_SECONDARY, muted=theme.INK_MUTED, grid=theme.GRID,
        border=theme.BORDER, blue=theme.SERIES[0],
        critical=theme.STATUS["critical"], warning=theme.STATUS["warning"],
        font=theme.FONT,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    index.write_text(page)
    (out_dir / ".nojekyll").write_text("")
    return index


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlowLedger</title>
<meta name="description" content="ERP data integration and reporting pipeline:
 a static snapshot of the FlowLedger reports.">
<style>
  :root {{
    color-scheme: light;
    --surface: {surface};
    --plane: {plane};
    --ink: {ink};
    --ink2: {ink2};
    --muted: {muted};
    --grid: {grid};
    --border: {border};
    --blue: {blue};
    --critical: {critical};
    --warning: {warning};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--plane); color: var(--ink);
    font-family: {font}; font-size: 14px; line-height: 1.5;
  }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 16px 80px; }}
  header h1 {{ font-size: 28px; margin: 0 0 2px; font-weight: 680; }}
  header h1 span {{ color: var(--muted); font-weight: 400; }}
  header p {{ margin: 6px 0 0; color: var(--ink2); max-width: 70ch; }}
  .meta {{
    margin: 18px 0 26px; padding: 10px 14px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 8px;
    font-size: 12px; color: var(--ink2);
  }}
  .meta strong {{ color: var(--ink); }}
  a {{ color: var(--blue); }}
  .tiles {{
    display: grid; gap: 10px; margin-bottom: 30px;
    grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  }}
  .tile {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .tile-label {{
    font-size: 11px; letter-spacing: .04em; text-transform: uppercase;
    color: var(--muted); font-weight: 600;
  }}
  .tile-value {{ font-size: 26px; font-weight: 650; margin-top: 6px; }}
  .tile-value.critical {{ color: var(--critical); }}
  .tile-value.warning {{ color: var(--warning); }}
  .tile-note {{ font-size: 11px; color: var(--ink2); margin-top: 4px; }}
  section {{ margin-top: 42px; }}
  h2 {{
    font-size: 13px; letter-spacing: .06em; text-transform: uppercase;
    color: var(--muted); margin: 0 0 14px; font-weight: 700;
    border-bottom: 1px solid var(--grid); padding-bottom: 8px;
  }}
  h3 {{ font-size: 14px; margin: 24px 0 2px; font-weight: 640; }}
  h3 + p.cap {{ margin: 0 0 10px; font-size: 12px; color: var(--ink2); }}
  .cols {{ display: grid; gap: 22px; grid-template-columns: 1fr; }}
  @media (min-width: 900px) {{ .cols.split {{ grid-template-columns: 3fr 2fr; }} }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .chart {{ width: 100%; overflow-x: auto; }}
  .scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; }}
  th, td {{
    text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--grid);
    white-space: nowrap;
  }}
  th {{
    color: var(--muted); font-weight: 600; font-size: 11px;
    text-transform: uppercase; letter-spacing: .03em;
    position: sticky; top: 0; background: var(--surface);
  }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  .note, .empty {{ font-size: 11.5px; color: var(--muted); margin: 8px 0 0; }}
  code {{
    background: var(--plane); border: 1px solid var(--border);
    border-radius: 4px; padding: 1px 5px; font-size: 12px;
  }}
  footer {{
    margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--grid);
    font-size: 12px; color: var(--ink2);
  }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>FlowLedger <span>/ ERP data integration</span></h1>
  <p>
    Customers from a CRM, projects and invoices from an ERP, reconciled into
    PostgreSQL by a Python ETL pipeline. Every figure on this page comes from a
    named query in <code>sql/reports.sql</code>.
  </p>
</header>

<div class="meta">
  <strong>Static snapshot</strong>, built {built} from the synthetic extracts in
  the repository &mdash; this page does not query a live database.
  Pipeline run <strong>{run_id}</strong> extracted <strong>{extracted}</strong>
  rows, loaded <strong>{loaded}</strong> and rejected
  <strong>{rejected}</strong>. Database holds {customers} customers,
  {projects} projects and {invoices} invoices.
  Source and setup instructions: <a href="{repo}">{repo}</a>.
</div>

<div class="tiles">{tiles}</div>

<section>
  <h2>Receivables</h2>
  <div class="cols split">
    <div class="card">
      <h3>Invoiced and collected by month</h3>
      <p class="cap">Bars: invoiced. Line: collected. Both USD, one axis.</p>
      <div class="chart" id="chart-monthly"></div>
    </div>
    <div class="card">
      <h3>Receivables by age</h3>
      <p class="cap">Darker is older. Open balance, not invoice face value.</p>
      <div class="chart" id="chart-aging"></div>
    </div>
  </div>
  <h3>Oldest overdue invoices</h3>
  <p class="cap">Unpaid or part-paid, past due date, worst first.</p>
  {t_overdue}
  <h3>Receivables per customer, by age</h3>
  <p class="cap">Aging buckets per customer.</p>
  {t_balances}
</section>

<section>
  <h2>Customers</h2>
  <div class="card">
    <h3>Top customers by total invoiced</h3>
    <p class="cap">Excluding void invoices.</p>
    <div class="chart" id="chart-customers"></div>
  </div>
  <h3>Ranking with concentration</h3>
  <p class="cap">Share of the book and cumulative share, highest first.</p>
  {t_customers}
</section>

<section>
  <h2>Projects</h2>
  <div class="card">
    <h3>Best and worst projects by gross margin</h3>
    <p class="cap">Invoiced minus labor cost. Blue above zero, red below.</p>
    <div class="chart" id="chart-margin"></div>
  </div>
  <h3>Projects over budget</h3>
  <p class="cap">Labor cost has passed the budget.</p>
  {t_overbudget}
  <h3>Project financials</h3>
  <p class="cap">Budget, invoiced, collected, labor cost and margin.</p>
  {t_projects}
</section>

<section>
  <h2>Data quality</h2>
  <div class="cols split">
    <div class="card">
      <h3>Rejections by rule</h3>
      <p class="cap">{rejected} rows refused in run {run_id}; none dropped silently.</p>
      <div class="chart" id="chart-rejections"></div>
    </div>
    <div class="card">
      <h3>Rule summary</h3>
      <p class="cap">One example key and reason per rule.</p>
      {t_rejections}
    </div>
  </div>
  <h3>Every rejected row</h3>
  <p class="cap">
    Each is stored with the rule it broke, a readable reason, its source line
    number and the original values as JSON.
  </p>
  {t_rejected_detail}
</section>

<section>
  <h2>Pipeline</h2>
  <h3>Run history</h3>
  <p class="cap">
    Re-running over unchanged extracts updates in place and inserts nothing:
    the idempotency guarantee, visible as data.
  </p>
  {t_runs}
  <h3>Per-table load statistics, latest run</h3>
  <p class="cap">What each table absorbed, and how long it took.</p>
  {t_audit}
</section>

<footer>
  FlowLedger &mdash; Python, Pandas, PostgreSQL, SQLAlchemy, pytest, Docker
  Compose. Synthetic data only; no real customer records.
  <a href="{repo}">Repository</a> &middot;
  <a href="{repo}/blob/main/docs/architecture.md">Architecture</a>
</footer>
</div>

<script src="{vega}"></script>
<script src="{vega_lite}"></script>
<script src="{vega_embed}"></script>
<script>
  const SPECS = {specs};
  for (const [id, spec] of Object.entries(SPECS)) {{
    const el = document.getElementById(id);
    if (!el) continue;
    vegaEmbed(el, spec, {{actions: false, renderer: "svg", width: "container"}})
      .catch(err => {{
        el.innerHTML =
          '<p class="empty">Chart failed to render: ' + err + '</p>';
      }});
  }}
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs",
        help="output directory (default: docs/, which GitHub Pages serves)",
    )
    args = parser.parse_args(argv)
    index = build(args.out)
    size = index.stat().st_size
    print(f"wrote {index} ({size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
