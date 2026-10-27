"""FlowLedger -- Streamlit dashboard over the loaded ERP data.

    streamlit run src/dashboard.py

Every figure on this page comes from a named query in sql/reports.sql -- the
same SQL the CLI reports run. The dashboard adds no business logic of its
own, so there is one definition of "outstanding" in the project, not two.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run src/dashboard.py` puts src/ on sys.path, not the project
# root, so `import src.*` would fail. Put the root on the path before the
# first project import. Running under pytest or `python -m` already has it.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import text

from src import theme
from src.config import make_engine
from src.reports import load_queries, run_report

CHART_HEIGHT = 300


# ---------------------------------------------------------------------------
# Data access -- cached so moving between tabs does not re-query.
# ---------------------------------------------------------------------------

@st.cache_resource
def engine():
    return make_engine()


@st.cache_data(ttl=60)
def report(name: str) -> pd.DataFrame:
    return run_report(engine(), load_queries()[name])


@st.cache_data(ttl=60)
def headline() -> dict:
    """The few totals that are not already a named report."""
    sql = """
        SELECT
            (SELECT count(*) FROM customers)                        AS customers,
            (SELECT count(*) FROM projects)                         AS projects,
            (SELECT count(*) FROM projects WHERE status = 'Active')  AS active_projects,
            (SELECT count(*) FROM invoices)                         AS invoices,
            (SELECT COALESCE(SUM(amount), 0) FROM invoices
              WHERE status <> 'Void')                               AS total_invoiced,
            (SELECT COALESCE(SUM(amount_paid), 0) FROM invoices
              WHERE status <> 'Void')                               AS total_collected,
            (SELECT COALESCE(SUM(amount - amount_paid), 0) FROM invoices
              WHERE status NOT IN ('Paid', 'Void'))                 AS outstanding,
            (SELECT COALESCE(SUM(amount - amount_paid), 0) FROM invoices
              WHERE status NOT IN ('Paid', 'Void')
                AND due_date < CURRENT_DATE)                        AS overdue
    """
    with engine().connect() as conn:
        return dict(conn.execute(text(sql)).mappings().one())


@st.cache_data(ttl=60)
def latest_run() -> dict | None:
    sql = """
        SELECT run_id, status, started_at, rows_extracted, rows_loaded,
               rows_inserted, rows_updated, rows_rejected, error_message
          FROM pipeline_runs ORDER BY run_id DESC LIMIT 1
    """
    with engine().connect() as conn:
        row = conn.execute(text(sql)).mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def money(value) -> str:
    return f"${Decimal(value):,.0f}"


def tile(column, label: str, value: str, note: str = "", tone: str = "") -> None:
    """A stat tile. The value is the mark; colour only ever carries status."""
    accent = theme.STATUS.get(tone, theme.INK)
    column.markdown(
        f"""
        <div style="background:{theme.SURFACE};border:1px solid {theme.BORDER};
                    border-radius:10px;padding:14px 16px;height:100%">
          <div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;
                      color:{theme.INK_MUTED};font-weight:600">{label}</div>
          <div style="font-size:26px;font-weight:650;color:{accent};
                      margin-top:6px;line-height:1.15">{value}</div>
          <div style="font-size:11px;color:{theme.INK_SECONDARY};margin-top:4px">
            {note or "&nbsp;"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def money_axis(field: str, title: str | None = None) -> alt.X:
    return alt.X(
        field,
        type="quantitative",
        title=title,
        axis=alt.Axis(format="~s", labelExpr="'$' + datum.label"),
    )


def table(frame: pd.DataFrame, **kwargs) -> None:
    st.dataframe(frame, width="stretch", hide_index=True, **kwargs)


# ---------------------------------------------------------------------------
# Charts. One form per question; hover tooltips on every mark.
# ---------------------------------------------------------------------------

def chart_monthly(frame: pd.DataFrame) -> alt.LayerChart:
    """Invoiced vs collected over time.

    Both measures are dollars, so they share one axis -- never a second
    y-scale. Bars carry the magnitude, the line carries the comparison.
    """
    data = frame.assign(
        month=pd.to_datetime(frame["month"]),
        total_invoiced=frame["total_invoiced"].astype(float),
        total_collected=frame["total_collected"].astype(float),
    )
    base = alt.Chart(data).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y", tickCount=8))
    )
    bars = base.mark_bar(size=16, color=theme.SERIES[0]).encode(
        y=alt.Y(
            "total_invoiced:Q",
            title="USD",
            axis=alt.Axis(format="~s", labelExpr="'$' + datum.label"),
        ),
        tooltip=[
            alt.Tooltip("month:T", title="Month", format="%B %Y"),
            alt.Tooltip("invoice_count:Q", title="Invoices"),
            alt.Tooltip("total_invoiced:Q", title="Invoiced", format="$,.2f"),
            alt.Tooltip("total_collected:Q", title="Collected", format="$,.2f"),
        ],
    )
    line = base.mark_line(color=theme.SERIES[1], strokeWidth=2).encode(
        y="total_collected:Q"
    )
    points = base.mark_point(
        color=theme.SERIES[1], size=45, filled=True, stroke=theme.SURFACE, strokeWidth=2
    ).encode(y="total_collected:Q")
    return (bars + line + points).properties(height=CHART_HEIGHT)


def chart_aging(frame: pd.DataFrame) -> alt.LayerChart:
    """Receivables by age.

    The buckets are ordered, so the colour is an ordinal single-hue ramp:
    older money is darker. Every bar is directly labelled, which is what
    lets the ramp carry meaning without a legend.
    """
    data = frame.assign(
        balance_due=frame["balance_due"].astype(float),
        label=frame["aging_bucket"].str.replace(r"^\d - ", "", regex=True),
    )
    base = alt.Chart(data).encode(
        y=alt.Y("aging_bucket:N", title=None, sort=None,
                axis=alt.Axis(labelExpr="replace(datum.label, /^\\d - /, '')")),
    )
    bars = base.mark_bar(height=22).encode(
        x=money_axis("balance_due", "Balance due"),
        color=alt.Color("aging_bucket:N", sort=None, legend=None,
                        scale=alt.Scale(range=theme.RAMP_BLUE)),
        tooltip=[
            alt.Tooltip("label:N", title="Age"),
            alt.Tooltip("open_invoices:Q", title="Open invoices"),
            alt.Tooltip("balance_due:Q", title="Balance due", format="$,.2f"),
            alt.Tooltip("pct_of_receivables:Q", title="Share", format=".1f"),
        ],
    )
    labels = base.mark_text(
        align="left", dx=6, color=theme.INK_SECONDARY, fontSize=11
    ).encode(x="balance_due:Q", text=alt.Text("balance_due:Q", format="$,.0f"))
    return (bars + labels).properties(height=190)


def chart_top_customers(frame: pd.DataFrame) -> alt.LayerChart:
    """Concentration of the book. One series, so no legend -- the title names it."""
    data = frame.head(10).assign(total_invoiced=lambda d: d["total_invoiced"].astype(float))
    base = alt.Chart(data).encode(
        y=alt.Y("customer_name:N", title=None, sort="-x"),
    )
    bars = base.mark_bar(height=18, color=theme.SERIES[0]).encode(
        x=money_axis("total_invoiced", "Total invoiced"),
        tooltip=[
            alt.Tooltip("customer_name:N", title="Customer"),
            alt.Tooltip("industry:N", title="Industry"),
            alt.Tooltip("invoice_count:Q", title="Invoices"),
            alt.Tooltip("total_invoiced:Q", title="Invoiced", format="$,.2f"),
            alt.Tooltip("pct_of_total:Q", title="Share of book", format=".2f"),
        ],
    )
    labels = base.mark_text(
        align="left", dx=6, color=theme.INK_SECONDARY, fontSize=11
    ).encode(x="total_invoiced:Q", text=alt.Text("total_invoiced:Q", format="$,.0f"))
    return (bars + labels).properties(height=320)


def chart_margin(frame: pd.DataFrame) -> alt.LayerChart:
    """Gross margin by project -- a polarity question, so a diverging pair.

    Blue above zero, red below, with a zero rule rather than a coloured
    midpoint. Sign is also carried by which side of the baseline the bar
    sits on, so colour is not doing the work alone.
    """
    data = frame.assign(gross_margin=lambda d: d["gross_margin"].astype(float))
    data = pd.concat([data.nlargest(8, "gross_margin"), data.nsmallest(8, "gross_margin")])
    data = data.drop_duplicates(subset="project_id").assign(
        sign=lambda d: d["gross_margin"].ge(0).map({True: "Profit", False: "Loss"})
    )
    base = alt.Chart(data).encode(y=alt.Y("project_name:N", title=None, sort="-x"))
    bars = base.mark_bar(height=16).encode(
        x=money_axis("gross_margin", "Invoiced minus labor cost"),
        color=alt.Color(
            "sign:N",
            title=None,
            scale=alt.Scale(
                domain=["Profit", "Loss"], range=[theme.POSITIVE, theme.NEGATIVE]
            ),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("project_id:N", title="Project"),
            alt.Tooltip("project_name:N", title="Name"),
            alt.Tooltip("customer_name:N", title="Customer"),
            alt.Tooltip("status:N", title="Status"),
            alt.Tooltip("budget_amount:Q", title="Budget", format="$,.2f"),
            alt.Tooltip("total_invoiced:Q", title="Invoiced", format="$,.2f"),
            alt.Tooltip("labor_cost:Q", title="Labor cost", format="$,.2f"),
            alt.Tooltip("gross_margin:Q", title="Gross margin", format="$,.2f"),
        ],
    )
    zero = alt.Chart(data).mark_rule(color=theme.AXIS, strokeWidth=1).encode(
        x=alt.datum(0)
    )
    return (bars + zero).properties(height=380)


def chart_rejections(frame: pd.DataFrame) -> alt.LayerChart:
    """Which data-quality rule fired, and how often. One series, no legend."""
    data = (
        frame.groupby("rule", as_index=False)["rejected_rows"]
        .sum()
        .assign(rejected_rows=lambda d: d["rejected_rows"].astype(int))
        .sort_values("rejected_rows", ascending=False)
    )
    base = alt.Chart(data).encode(y=alt.Y("rule:N", title=None, sort="-x"))
    bars = base.mark_bar(height=16, color=theme.SERIES[0]).encode(
        x=alt.X("rejected_rows:Q", title="Rejected rows",
                axis=alt.Axis(tickMinStep=1, format="d")),
        tooltip=[
            alt.Tooltip("rule:N", title="Rule"),
            alt.Tooltip("rejected_rows:Q", title="Rejected rows"),
        ],
    )
    labels = base.mark_text(
        align="left", dx=6, color=theme.INK_SECONDARY, fontSize=11
    ).encode(x="rejected_rows:Q", text="rejected_rows:Q")
    return (bars + labels).properties(height=max(140, 26 * len(data)))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="FlowLedger",
        page_icon="📊",
        layout="wide",
    )
    theme.register()

    st.markdown(
        f"""
        <div style="margin-bottom:2px">
          <span style="font-size:24px;font-weight:680;color:{theme.INK}">
            FlowLedger</span>
          <span style="font-size:24px;font-weight:400;color:{theme.INK_MUTED}">
            &nbsp;/ ERP data integration</span>
        </div>
        <div style="font-size:12px;color:{theme.INK_SECONDARY};margin-bottom:18px">
          Customers from the CRM, projects and invoices from the ERP, reconciled
          into PostgreSQL. Every figure below is a query in
          <code>sql/reports.sql</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        kpi = headline()
        run = latest_run()
    except Exception as exc:  # noqa: BLE001
        st.error(
            f"Cannot read the database ({type(exc).__name__}). "
            "Start it with `make up` and load it with `make pipeline`."
        )
        st.stop()

    if not run:
        st.warning("The database is empty. Run `make pipeline` to load it.")
        st.stop()

    with st.sidebar:
        st.markdown("#### Last pipeline run")
        st.markdown(
            f"**Run {run['run_id']}** &middot; {run['status']}  \n"
            f"{run['started_at']:%Y-%m-%d %H:%M}"
        )
        st.markdown(
            f"- extracted **{run['rows_extracted']:,}**\n"
            f"- loaded **{run['rows_loaded']:,}** "
            f"(inserted {run['rows_inserted']:,}, updated {run['rows_updated']:,})\n"
            f"- rejected **{run['rows_rejected']:,}**"
        )
        if run["error_message"]:
            st.error(run["error_message"])
        st.divider()
        st.caption(
            f"{kpi['customers']:,} customers · {kpi['projects']:,} projects "
            f"· {kpi['invoices']:,} invoices"
        )
        if st.button("Refresh data", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    # --- stat tiles --------------------------------------------------------
    collected_pct = (
        100 * Decimal(kpi["total_collected"]) / Decimal(kpi["total_invoiced"])
        if kpi["total_invoiced"]
        else Decimal(0)
    )
    overdue_pct = (
        100 * Decimal(kpi["overdue"]) / Decimal(kpi["outstanding"])
        if kpi["outstanding"]
        else Decimal(0)
    )
    cols = st.columns(5, gap="small")
    tile(cols[0], "Total invoiced", money(kpi["total_invoiced"]),
         f"{kpi['invoices']:,} invoices, excluding void")
    tile(cols[1], "Collected", money(kpi["total_collected"]),
         f"{collected_pct:.1f}% of invoiced")
    tile(cols[2], "Outstanding", money(kpi["outstanding"]),
         "open and partly paid invoices")
    tile(cols[3], "Overdue", money(kpi["overdue"]),
         f"⚠ {overdue_pct:.1f}% of outstanding past due",
         tone="critical" if overdue_pct > 50 else "warning")
    tile(cols[4], "Rejected rows", f"{run['rows_rejected']:,}",
         f"of {run['rows_extracted']:,} extracted, run {run['run_id']}")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    tabs = st.tabs(
        ["Receivables", "Customers", "Projects", "Data quality", "Pipeline"]
    )

    # --- receivables ------------------------------------------------------
    with tabs[0]:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            st.markdown("**Invoiced and collected by month**")
            st.caption("Bars: invoiced. Line: collected. Both in USD, one axis.")
            st.altair_chart(chart_monthly(report("revenue_by_month")))
        with right:
            st.markdown("**Receivables by age**")
            st.caption("Darker is older. Open balance, not invoice face value.")
            st.altair_chart(chart_aging(report("ar_aging_summary")))

        st.markdown("**Oldest overdue invoices**")
        table(report("overdue_invoices"))

        with st.expander("Receivables per customer, by age"):
            table(report("customer_balances"))

    # --- customers --------------------------------------------------------
    with tabs[1]:
        left, right = st.columns([3, 2], gap="medium")
        with left:
            st.markdown("**Top customers by total invoiced**")
            st.caption("Excluding void invoices.")
            st.altair_chart(chart_top_customers(report("customer_revenue_rank")))
        with right:
            st.markdown("**Concentration**")
            st.caption("Cumulative share of the book, highest first.")
            ranked = report("customer_revenue_rank")
            table(
                ranked[["revenue_rank", "customer_name", "total_invoiced",
                        "pct_of_total", "cumulative_pct"]],
                height=320,
            )
        st.markdown("**Full ranking**")
        table(ranked)

    # --- projects ---------------------------------------------------------
    with tabs[2]:
        profitability = report("project_profitability")
        left, right = st.columns([3, 2], gap="medium")
        with left:
            st.markdown("**Best and worst projects by gross margin**")
            st.caption("Invoiced minus labor cost. Blue above zero, red below.")
            st.altair_chart(chart_margin(profitability))
        with right:
            st.markdown("**Projects over budget**")
            st.caption("Labor cost has passed the budget.")
            table(report("projects_over_budget"), height=380)
        st.markdown("**Project financials**")
        table(profitability)

    # --- data quality -----------------------------------------------------
    with tabs[3]:
        rejections = report("rejection_summary")
        st.markdown(
            f"**{run['rows_rejected']} rows were refused in run {run['run_id']}, "
            "and none were silently dropped.**"
        )
        st.caption(
            "Each one is stored with the rule it broke, a readable reason, its "
            "source line number, and the original values as JSON."
        )
        left, right = st.columns([2, 3], gap="medium")
        with left:
            st.altair_chart(chart_rejections(rejections))
        with right:
            table(rejections, height=max(180, 36 + 36 * len(rejections)))
        st.markdown("**Every rejected row**")
        table(report("rejected_records_detail"))

    # --- pipeline ---------------------------------------------------------
    with tabs[4]:
        st.markdown("**Run history**")
        st.caption(
            "Re-running over unchanged extracts updates in place and inserts "
            "nothing: that is the idempotency guarantee, visible as data."
        )
        table(report("pipeline_run_history"))
        st.markdown("**Per-table load statistics, latest run**")
        table(report("load_audit_detail"))


if __name__ == "__main__":
    main()
