"""Run the reports in sql/reports.sql and print them as tables.

    python -m src.reports                      # run every report
    python -m src.reports --list               # show the available names
    python -m src.reports --report overdue_invoices
    python -m src.reports --format md > docs/sample_reports.md
    python -m src.reports --format csv --report overdue_invoices > overdue.csv
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text
from tabulate import tabulate

from src.config import SQL_DIR, make_engine

NAME_MARKER = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)

TITLES = {
    "overdue_invoices": "Overdue invoices (worst first)",
    "revenue_by_month": "Invoiced amount by month",
    "customer_revenue_rank": "Customers ranked by total invoiced",
    "customer_balances": "Customer receivables by age",
    "ar_aging_summary": "Receivables aging summary",
    "project_profitability": "Project profitability",
    "projects_over_budget": "Projects over budget",
    "pipeline_run_history": "Pipeline run history",
    "rejection_summary": "Rejected records by rule (latest run)",
    "rejected_records_detail": "Rejected records in detail (latest run)",
    "load_audit_detail": "Load audit (latest run)",
}


def load_queries(path: Path | None = None) -> dict[str, str]:
    """Split reports.sql into named queries on its ``-- name:`` markers."""
    path = path or SQL_DIR / "reports.sql"
    sql = path.read_text()

    matches = list(NAME_MARKER.finditer(sql))
    queries: dict[str, str] = {}
    for current, following in zip(matches, matches[1:] + [None]):
        end = following.start() if following else len(sql)
        body = sql[current.end() : end].strip()
        if body:
            queries[current.group(1)] = body
    return queries


def run_report(engine: Engine, sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn)


# Columns whose values are counts, ids or years, so they must not be
# rendered with thousands separators or decimal places.
PLAIN_NUMERIC = {
    "run_id", "source_row", "first_source_row", "invoice_count",
    "open_invoices", "revenue_rank", "rejected_rows", "days_overdue",
    "rows_in", "rows_inserted", "rows_updated", "rows_rejected",
    "rows_extracted", "rows_loaded", "duration_ms",
}


def format_cell(column: str, value: object) -> str:
    """Render one cell for display: aligned money, plain counts, '-' for null."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (Decimal, float, int)):
        if column in PLAIN_NUMERIC or isinstance(value, int):
            return f"{int(value):,}"
        if column.startswith("pct") or column.endswith("_pct"):
            return f"{value:,.1f}%"
        return f"{value:,.2f}"
    return str(value)


def _display_frame(frame: pd.DataFrame) -> tuple[list[list[str]], list[str]]:
    """Format every cell and right-align the numeric columns."""
    numeric = {
        column
        for column in frame.columns
        if frame[column].map(lambda v: isinstance(v, (Decimal, float, int))).any()
    }
    rows = [
        [format_cell(column, row[column]) for column in frame.columns]
        for _, row in frame.iterrows()
    ]
    align = ["right" if column in numeric else "left" for column in frame.columns]
    return rows, align


def render(name: str, frame: pd.DataFrame, fmt: str) -> str:
    title = TITLES.get(name, name)

    if fmt == "csv":
        return frame.to_csv(index=False)

    if fmt == "md":
        body = (
            frame.to_markdown(index=False, floatfmt=",.2f")
            if not frame.empty
            else "_no rows_"
        )
        return f"### `{name}` -- {title}\n\n{body}\n"

    if frame.empty:
        return f"\n  {title}  [{name}]\n  (no rows)\n"

    rows, align = _display_frame(frame)
    table = tabulate(
        rows,
        headers=[c.replace("_", " ") for c in frame.columns],
        tablefmt="rounded_outline",
        colalign=align,
        disable_numparse=True,
    )
    width = max(len(line) for line in table.splitlines())
    heading = f"  {title}".ljust(width)
    footer = f"  {name}  --  {len(frame)} row{'s' if len(frame) != 1 else ''}"
    return f"\n{heading}\n{table}\n{footer}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SQL business reports.")
    parser.add_argument("--report", action="append", help="report name; repeatable")
    parser.add_argument("--list", action="store_true", help="list report names")
    parser.add_argument(
        "--format",
        choices=["text", "md", "csv"],
        default="text",
        help="output format (default: text)",
    )
    args = parser.parse_args(argv)

    queries = load_queries()

    if args.list:
        for name in queries:
            print(f"{name:<26}{TITLES.get(name, '')}")
        return 0

    selected = args.report or list(queries)
    unknown = [name for name in selected if name not in queries]
    if unknown:
        print(f"unknown report(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(queries)}", file=sys.stderr)
        return 2

    engine = make_engine()
    if args.format == "md":
        print("# Sample report output\n")
        print(
            "Generated with `python -m src.reports --format md`. "
            "Figures come from the synthetic extracts in `data/`.\n"
        )
    for name in selected:
        print(render(name, run_report(engine, queries[name]), args.format))
    return 0


if __name__ == "__main__":
    sys.exit(main())
