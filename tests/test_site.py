"""Tests for the static GitHub Pages snapshot.

The published page is the project's public face, so these check that it is
complete (every chart has data, every table rendered), that the template was
fully substituted, and -- most importantly -- that it leaks no credentials.
"""

from __future__ import annotations

import json
import re

import pytest

from src.config import DATA_DIR, DbConfig
from src.pipeline import run_pipeline

SPEC_RE = re.compile(r"const SPECS = (\{.*?\});\n", re.S)


@pytest.fixture(scope="module")
def built(request, tmp_path_factory):
    """Load the sample data, then build the site into a temp directory."""
    from sqlalchemy import text

    from src.load import apply_schema

    engine = request.getfixturevalue("engine")
    truncate = (
        "TRUNCATE load_audit, rejected_records, pipeline_runs, "
        "invoices, projects, customers RESTART IDENTITY CASCADE"
    )
    apply_schema(engine)
    with engine.begin() as conn:
        conn.execute(text(truncate))
    run_pipeline(source_dir=DATA_DIR, engine=engine)

    from scripts.build_site import build

    out = tmp_path_factory.mktemp("site")
    index = build(out)
    html = index.read_text()
    yield html, out

    with engine.begin() as conn:
        conn.execute(text(truncate))


def specs(html: str) -> dict:
    return json.loads(SPEC_RE.search(html).group(1))


class TestPageStructure:
    def test_it_writes_index_and_nojekyll(self, built):
        _, out = built
        assert (out / "index.html").exists()
        # Without .nojekyll, GitHub Pages runs the output through Jekyll.
        assert (out / ".nojekyll").exists()

    def test_the_template_is_fully_substituted(self, built):
        html, _ = built
        match = SPEC_RE.search(html)
        template = html[: match.start(1)] + html[match.end(1) :]
        assert not re.findall(r"\{[a-z_]{3,}\}", template)
        assert "{{" not in template

    def test_every_chart_div_has_a_matching_spec(self, built):
        html, _ = built
        divs = set(re.findall(r'<div class="chart" id="([^"]+)"></div>', html))
        assert divs == set(specs(html))
        assert len(divs) == 5

    def test_every_chart_carries_its_data(self, built):
        html, _ = built
        for name, spec in specs(html).items():
            datasets = spec.get("datasets", {})
            rows = (
                sum(len(v) for v in datasets.values())
                if datasets
                else len(spec.get("data", {}).get("values", []))
            )
            assert rows > 0, f"{name} has no data rows"

    def test_charts_target_the_vega_lite_version_the_cdn_serves(self, built):
        html, _ = built
        pinned = re.search(r"npm/vega-lite@([\d.]+)/", html).group(1)
        for spec in specs(html).values():
            schema_version = spec["$schema"].split("/v")[-1].removesuffix(".json")
            assert schema_version == pinned, (
                f"spec targets Vega-Lite {schema_version} but the page loads {pinned}"
            )

    def test_all_three_scripts_are_version_pinned(self, built):
        html, _ = built
        pins = re.findall(r"npm/(vega[a-z-]*)@([\d.]+)/", html)
        assert {name for name, _ in pins} == {"vega", "vega-lite", "vega-embed"}
        for name, version in pins:
            assert version.count(".") == 2, f"{name} is not pinned to an exact version"

    def test_the_tables_are_rendered(self, built):
        html, _ = built
        assert html.count("<table>") >= 9
        assert html.count("<tr>") > 100

    def test_it_says_the_snapshot_is_not_live(self, built):
        """A viewer must not think the page is querying a live database."""
        html, _ = built
        assert "Static snapshot" in html
        assert "does not query a live database" in html

    def test_it_links_back_to_the_repository(self, built):
        html, _ = built
        assert "github.com/sameermankotia/FlowLedger" in html


class TestSnapshotTimestamp:
    def test_it_stamps_the_build_time(self, built):
        html, _ = built
        assert re.search(r"built \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", html)

    def test_built_at_overrides_the_timestamp(self, request, tmp_path):
        """The published snapshot date is an explicit parameter, not the clock."""
        from datetime import datetime, timezone

        request.getfixturevalue("built")  # ensure the database is loaded
        from scripts.build_site import build

        stamp = datetime(2026, 6, 27, 18, 9, tzinfo=timezone.utc)
        html = build(tmp_path / "dated", built_at=stamp).read_text()
        assert "built 2026-06-27 18:09 UTC" in html


class TestNoSecretsLeak:
    def test_the_page_contains_no_database_credentials(self, built):
        html, _ = built
        config = DbConfig()
        for secret in (config.password, config.url):
            assert secret not in html, "the published page leaks a credential"

    def test_the_page_contains_no_connection_string(self, built):
        html, _ = built
        assert "postgresql+psycopg" not in html
        assert "POSTGRES_PASSWORD" not in html
