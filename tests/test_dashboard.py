"""Tests for the dashboard's chart specifications.

The charts are built from the same named reports as the CLI, so these tests
check two things: that each chart compiles to a valid Vega-Lite spec against
real query output, and that the design rules the charts are supposed to
follow actually hold in the emitted spec.

Streamlit itself is not exercised -- only the pure chart functions.
"""

from __future__ import annotations

import pytest

from src import theme
from src.dashboard import (
    chart_aging,
    chart_margin,
    chart_monthly,
    chart_rejections,
    chart_top_customers,
)
from src.pipeline import run_pipeline
from src.reports import load_queries, run_report
from src.config import DATA_DIR

CHARTS = {
    "revenue_by_month": chart_monthly,
    "ar_aging_summary": chart_aging,
    "customer_revenue_rank": chart_top_customers,
    "project_profitability": chart_margin,
    "rejection_summary": chart_rejections,
}


@pytest.fixture(scope="module")
def loaded(request):
    """Load the shipped sample data once for the whole module."""
    engine = request.getfixturevalue("engine")
    from src.load import apply_schema
    from sqlalchemy import text

    apply_schema(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE load_audit, rejected_records, pipeline_runs, "
                "invoices, projects, customers RESTART IDENTITY CASCADE"
            )
        )
    run_pipeline(source_dir=DATA_DIR, engine=engine)
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE load_audit, rejected_records, pipeline_runs, "
                "invoices, projects, customers RESTART IDENTITY CASCADE"
            )
        )


def spec_for(engine, name):
    frame = run_report(engine, load_queries()[name])
    theme.register()
    return CHARTS[name](frame).to_dict()


def marks(spec: dict) -> list[dict]:
    """Every mark in a spec, whether or not it is layered."""
    layers = spec.get("layer", [spec])
    out = []
    for layer in layers:
        mark = layer.get("mark")
        if isinstance(mark, str):
            out.append({"type": mark})
        elif isinstance(mark, dict):
            out.append(mark)
    return out


def encodings(spec: dict) -> list[dict]:
    return [
        layer.get("encoding", {}) for layer in spec.get("layer", [spec])
    ]


class TestChartsCompile:
    @pytest.mark.parametrize("name", list(CHARTS))
    def test_chart_builds_a_valid_spec(self, loaded, name):
        spec = spec_for(loaded, name)
        assert spec["$schema"].startswith("https://vega.github.io/schema/vega-lite/")
        assert marks(spec), "chart emitted no marks"

    @pytest.mark.parametrize("name", list(CHARTS))
    def test_chart_has_data(self, loaded, name):
        spec = spec_for(loaded, name)
        rows = spec.get("datasets", {})
        inline = spec.get("data", {}).get("values")
        assert rows or inline, "chart has no data attached"


class TestDesignRules:
    """The rules the charts are meant to follow, asserted on the spec."""

    @pytest.mark.parametrize("name", list(CHARTS))
    def test_every_chart_has_a_hover_tooltip(self, loaded, name):
        spec = spec_for(loaded, name)
        assert any("tooltip" in enc for enc in encodings(spec)), (
            f"{name} has no tooltip layer"
        )

    def test_monthly_chart_uses_a_single_shared_y_axis(self, loaded):
        """Two dollar measures must share one scale -- never a dual axis."""
        spec = spec_for(loaded, "revenue_by_month")
        titles = set()
        for enc in encodings(spec):
            y = enc.get("y", {})
            if "title" in y and y["title"] is not None:
                titles.add(y["title"])
            assert "scale" not in y or "domain" not in y.get("scale", {}), (
                "a layer pins its own y domain, which creates a second scale"
            )
        assert titles == {"USD"}

    def test_aging_ramp_is_a_single_hue_in_order(self, loaded):
        spec = spec_for(loaded, "ar_aging_summary")
        colors = [
            enc["color"]["scale"]["range"]
            for enc in encodings(spec)
            if "color" in enc and "scale" in enc["color"]
        ]
        assert colors and colors[0] == theme.RAMP_BLUE

    def test_aging_bars_are_directly_labelled(self, loaded):
        """An ordinal ramp without a legend needs the values on the bars."""
        spec = spec_for(loaded, "ar_aging_summary")
        assert any(m["type"] == "text" for m in marks(spec))

    def test_margin_chart_uses_the_diverging_pair(self, loaded):
        spec = spec_for(loaded, "project_profitability")
        ranges = [
            enc["color"]["scale"]["range"]
            for enc in encodings(spec)
            if "color" in enc and "scale" in enc["color"]
        ]
        assert [theme.POSITIVE, theme.NEGATIVE] in ranges

    def test_margin_chart_keeps_a_legend_for_its_two_series(self, loaded):
        spec = spec_for(loaded, "project_profitability")
        legends = [
            enc["color"].get("legend")
            for enc in encodings(spec)
            if "color" in enc and "scale" in enc["color"]
        ]
        assert any(legend is not None for legend in legends)

    def test_single_series_charts_have_no_legend(self, loaded):
        """One series needs no legend box -- the title names it."""
        for name in ("customer_revenue_rank", "rejection_summary"):
            spec = spec_for(loaded, name)
            for enc in encodings(spec):
                assert "color" not in enc, f"{name} encodes colour for one series"

    def test_bars_have_rounded_data_ends(self, loaded):
        spec = spec_for(loaded, "ar_aging_summary")
        assert spec["config"]["bar"]["cornerRadiusEnd"] == 4

    def test_lines_are_two_pixels(self, loaded):
        spec = spec_for(loaded, "revenue_by_month")
        line = next(m for m in marks(spec) if m["type"] == "line")
        assert line["strokeWidth"] == 2

    def test_overlapping_points_carry_a_surface_ring(self, loaded):
        spec = spec_for(loaded, "revenue_by_month")
        point = next(m for m in marks(spec) if m["type"] == "point")
        assert point["stroke"] == theme.SURFACE
        assert point["strokeWidth"] == 2

    def test_chart_surface_and_recessive_axes(self, loaded):
        config = spec_for(loaded, "ar_aging_summary")["config"]
        assert config["background"] == theme.SURFACE
        assert config["axis"]["gridColor"] == theme.GRID
        assert config["axis"]["labelColor"] == theme.INK_MUTED


class TestThemePalette:
    def test_categorical_order_is_fixed(self):
        assert theme.SERIES[:2] == ["#2a78d6", "#eb6834"]

    def test_ordinal_ramp_is_five_ordered_steps(self):
        assert len(theme.RAMP_BLUE) == 5
        assert theme.RAMP_BLUE[0] == "#86b6ef"
        assert theme.RAMP_BLUE[-1] == "#104281"

    def test_diverging_midpoint_is_neutral_not_a_hue(self):
        r, g, b = (int(theme.MIDPOINT[i : i + 2], 16) for i in (1, 3, 5))
        assert max(r, g, b) - min(r, g, b) < 20, "midpoint reads as a hue"

    def test_status_colours_are_not_reused_as_series(self):
        assert not set(theme.STATUS.values()) & set(theme.SERIES)


class TestPageRuns:
    """Execute the whole Streamlit script, the way the browser would.

    A chart spec compiling is not proof the page renders: Streamlit runs the
    script top to bottom and swallows nothing, so AppTest is what actually
    catches a bad column reference or a formatting error in the layout.
    """

    @pytest.fixture(scope="class")
    def app(self, loaded):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("src/dashboard.py", default_timeout=60)
        at.run()
        return at

    def test_the_page_runs_without_raising(self, app):
        assert not app.exception, [e.value for e in app.exception]

    def test_no_error_banner_is_shown(self, app):
        assert not app.error, [e.value for e in app.error]
        assert not app.warning, [w.value for w in app.warning]

    def test_the_five_stat_tiles_are_rendered(self, app):
        html = " ".join(block.value for block in app.markdown)
        for label in (
            "Total invoiced",
            "Collected",
            "Outstanding",
            "Overdue",
            "Rejected rows",
        ):
            assert label in html, f"missing stat tile: {label}"

    def test_the_tabs_are_present(self, app):
        labels = {tab.label for tab in app.tabs}
        assert labels == {
            "Receivables",
            "Customers",
            "Projects",
            "Data quality",
            "Pipeline",
        }

    def test_the_charts_are_rendered(self, app):
        # Five charts across the tabs, one per question.
        assert len(app.get("arrow_vega_lite_chart")) == 5

    def test_the_tables_are_rendered(self, app):
        assert len(app.dataframe) >= 9

    def test_the_sidebar_reports_the_latest_run(self, app):
        sidebar = " ".join(block.value for block in app.sidebar.markdown)
        assert "Last pipeline run" in sidebar
        assert "rejected" in sidebar

    def test_the_headline_figures_match_the_database(self, app, loaded):
        from sqlalchemy import text

        with loaded.connect() as conn:
            invoiced = conn.execute(
                text("SELECT SUM(amount) FROM invoices WHERE status <> 'Void'")
            ).scalar()

        html = " ".join(block.value for block in app.markdown)
        assert f"${invoiced:,.0f}" in html


class TestLaunchableByStreamlit:
    """`streamlit run src/dashboard.py` must work, not just `pytest`.

    Streamlit puts the *script's* directory on sys.path, not the project
    root, so a bare `from src import theme` fails there even though it works
    under pytest. This runs the script in a subprocess with exactly that
    path layout, which is the only way to catch the difference.
    """

    def test_the_script_imports_with_only_its_own_directory_on_the_path(self):
        import subprocess
        import sys as _sys
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parents[1]
        probe = (
            "import sys;"
            f"sys.path.insert(0, {str(root / 'src')!r});"
            "import importlib.util as u;"
            f"spec = u.spec_from_file_location('dash', {str(root / 'src' / 'dashboard.py')!r});"
            "m = u.module_from_spec(spec);"
            "spec.loader.exec_module(m);"
            "print('IMPORT_OK', bool(m.chart_monthly))"
        )
        result = subprocess.run(
            [_sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            cwd=root.parent,
            timeout=120,
        )
        assert "IMPORT_OK True" in result.stdout, (
            f"dashboard.py cannot be imported the way Streamlit imports it:\n"
            f"{result.stderr[-2000:]}"
        )
