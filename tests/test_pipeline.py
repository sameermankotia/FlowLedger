"""End-to-end tests against a real PostgreSQL instance.

These cover the three things unit tests cannot: that the database constraints
actually hold, that a second run does not duplicate anything, and that a
failing load leaves no partial data behind.

They skip when PostgreSQL is not reachable (see tests/conftest.py).
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.config import DATA_DIR
from src.pipeline import run_pipeline
from src.reports import load_queries, run_report

CUSTOMERS = [
    {
        "customer_id": "CUST-0001",
        "customer_name": "Cascade Power Inc.",
        "contact_email": "ap@cascade.example.com",
        "contact_phone": "(555) 010-1000",
        "industry": "Utilities",
        "country": "USA",
        "created_date": "2022-01-15",
    },
    {
        "customer_id": "  cust-0002 ",
        "customer_name": " Northline Energy LLC ",
        "contact_email": "AP@Northline.example.com",
        "contact_phone": "(555) 010-1001",
        "industry": "Renewables",
        "country": "Canada",
        "created_date": "03/09/2021",
    },
]
PROJECTS = [
    {
        "project_id": "PRJ-1001",
        "customer_id": "CUST-0001",
        "project_name": "Substation Upgrade",
        "project_manager": "Ada Lovelace",
        "status": "active",
        "start_date": "2024-01-10",
        "end_date": "",
        "budget_amount": "100,000.00",
        "labor_cost": "40000.00",
    },
    {
        "project_id": "PRJ-1002",
        "customer_id": "cust-0002",
        "project_name": "SCADA Rollout",
        "project_manager": "Grace Hopper",
        "status": "Completed",
        "start_date": "15-Mar-2023",
        "end_date": "2024-02-29",
        "budget_amount": "$250,000.00",
        "labor_cost": "310000.00",
    },
]
INVOICES = [
    {
        "invoice_id": "INV-200001",
        "customer_id": "CUST-0001",
        "project_id": "PRJ-1001",
        "invoice_date": "2024-02-01",
        "due_date": "2024-03-02",
        "amount": "5000.00",
        "amount_paid": "5000.00",
        "currency": "USD",
        "status": "paid",
    },
    {
        "invoice_id": "INV-200002",
        "customer_id": "CUST-0001",
        "project_id": "PRJ-1001",
        "invoice_date": "2024-03-01",
        "due_date": "2024-04-01",
        "amount": "7500.00",
        "amount_paid": "0.00",
        "currency": "usd",
        "status": "Open",
    },
    {
        "invoice_id": "INV-200003",
        "customer_id": "cust-0002",
        "project_id": "PRJ-1002",
        "invoice_date": "2024-04-01",
        "due_date": "2024-05-01",
        "amount": "12000.00",
        "amount_paid": "3000.00",
        "currency": "USD",
        "status": "Partial",
    },
    # One bad row per table keeps the fixture small but still exercises
    # the rejection path end to end.
    {
        "invoice_id": "INV-200004",
        "customer_id": "CUST-9999",
        "project_id": "PRJ-1001",
        "invoice_date": "2024-05-01",
        "due_date": "2024-06-01",
        "amount": "900.00",
        "amount_paid": "0.00",
        "currency": "USD",
        "status": "Open",
    },
]


def write_sources(directory: Path, invoices=None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("customers", CUSTOMERS),
        ("projects", PROJECTS),
        ("invoices", invoices if invoices is not None else INVOICES),
    ):
        path = directory / f"{name}.csv"
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return directory


@pytest.fixture
def source_dir(tmp_path) -> Path:
    return write_sources(tmp_path / "extract")


def scalar(engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


class TestFullRun:
    def test_loads_the_clean_rows(self, clean_db, source_dir):
        summary = run_pipeline(source_dir=source_dir, engine=clean_db)

        assert summary.status == "success"
        assert scalar(clean_db, "SELECT count(*) FROM customers") == 2
        assert scalar(clean_db, "SELECT count(*) FROM projects") == 2
        assert scalar(clean_db, "SELECT count(*) FROM invoices") == 3

    def test_normalizes_values_on_the_way_in(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)

        name = scalar(
            clean_db,
            "SELECT customer_name FROM customers WHERE customer_id = 'CUST-0002'",
        )
        assert name == "Northline Energy LLC"
        assert (
            scalar(
                clean_db,
                "SELECT contact_email FROM customers WHERE customer_id = 'CUST-0002'",
            )
            == "ap@northline.example.com"
        )
        assert (
            scalar(clean_db, "SELECT status FROM projects WHERE project_id = 'PRJ-1001'")
            == "Active"
        )
        assert (
            scalar(clean_db, "SELECT currency FROM invoices WHERE invoice_id = 'INV-200002'")
            == "USD"
        )
        assert scalar(
            clean_db, "SELECT budget_amount FROM projects WHERE project_id = 'PRJ-1002'"
        ) == Decimal("250000.00")

    def test_records_the_run(self, clean_db, source_dir):
        summary = run_pipeline(source_dir=source_dir, engine=clean_db)

        with clean_db.connect() as conn:
            run = conn.execute(
                text("SELECT * FROM pipeline_runs WHERE run_id = :id"),
                {"id": summary.run_id},
            ).mappings().one()

        assert run["status"] == "success"
        assert run["finished_at"] is not None
        assert run["rows_extracted"] == 8
        assert run["rows_loaded"] == 7
        assert run["rows_rejected"] == 1
        assert run["error_message"] is None

    def test_writes_an_audit_row_per_table(self, clean_db, source_dir):
        summary = run_pipeline(source_dir=source_dir, engine=clean_db)

        with clean_db.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT target_table, rows_in, rows_inserted, rows_rejected
                      FROM load_audit WHERE run_id = :id ORDER BY audit_id
                    """
                ),
                {"id": summary.run_id},
            ).mappings().all()

        assert [r["target_table"] for r in rows] == ["customers", "projects", "invoices"]
        assert [r["rows_inserted"] for r in rows] == [2, 2, 3]
        assert [r["rows_rejected"] for r in rows] == [0, 0, 1]

    def test_stores_the_rejected_row_with_its_reason(self, clean_db, source_dir):
        summary = run_pipeline(source_dir=source_dir, engine=clean_db)

        with clean_db.connect() as conn:
            rejection = conn.execute(
                text("SELECT * FROM rejected_records WHERE run_id = :id"),
                {"id": summary.run_id},
            ).mappings().one()

        assert rejection["source_table"] == "invoices"
        assert rejection["natural_key"] == "INV-200004"
        assert rejection["rule"] == "orphan_customer"
        assert "CUST-9999" in rejection["reason"]
        # The original row is preserved verbatim for the data owner.
        assert rejection["raw_record"]["customer_id"] == "CUST-9999"
        assert rejection["source_row"] == 5

    def test_dry_run_writes_nothing(self, clean_db, source_dir):
        summary = run_pipeline(source_dir=source_dir, engine=clean_db, dry_run=True)

        assert summary.status == "dry-run"
        assert summary.rows_rejected == 1
        assert scalar(clean_db, "SELECT count(*) FROM customers") == 0
        assert scalar(clean_db, "SELECT count(*) FROM pipeline_runs") == 0


class TestIdempotency:
    def test_rerunning_does_not_duplicate_rows(self, clean_db, source_dir):
        first = run_pipeline(source_dir=source_dir, engine=clean_db)
        second = run_pipeline(source_dir=source_dir, engine=clean_db)

        assert first.rows_inserted == 7
        assert second.rows_inserted == 0
        assert second.rows_updated == 7
        assert scalar(clean_db, "SELECT count(*) FROM invoices") == 3

    def test_three_runs_still_hold(self, clean_db, source_dir):
        for _ in range(3):
            run_pipeline(source_dir=source_dir, engine=clean_db)

        assert scalar(clean_db, "SELECT count(*) FROM customers") == 2
        assert scalar(clean_db, "SELECT count(*) FROM projects") == 2
        assert scalar(clean_db, "SELECT count(*) FROM invoices") == 3
        assert scalar(clean_db, "SELECT count(*) FROM pipeline_runs") == 3

    def test_a_changed_source_value_updates_in_place(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)

        revised = [dict(row) for row in INVOICES]
        revised[1]["amount_paid"] = "7500.00"
        revised[1]["status"] = "Paid"
        write_sources(source_dir, invoices=revised)

        run_pipeline(source_dir=source_dir, engine=clean_db)

        assert scalar(
            clean_db, "SELECT status FROM invoices WHERE invoice_id = 'INV-200002'"
        ) == "Paid"
        assert scalar(
            clean_db, "SELECT amount_paid FROM invoices WHERE invoice_id = 'INV-200002'"
        ) == Decimal("7500.00")
        assert scalar(clean_db, "SELECT count(*) FROM invoices") == 3

    def test_updated_at_moves_but_ingested_at_does_not(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)
        run_pipeline(source_dir=source_dir, engine=clean_db)

        assert scalar(
            clean_db,
            "SELECT updated_at > ingested_at FROM invoices WHERE invoice_id = 'INV-200001'",
        ) is True

    def test_rejections_are_kept_per_run_not_overwritten(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)
        run_pipeline(source_dir=source_dir, engine=clean_db)

        assert scalar(clean_db, "SELECT count(*) FROM rejected_records") == 2
        assert scalar(
            clean_db, "SELECT count(DISTINCT run_id) FROM rejected_records"
        ) == 2


class TestDatabaseConstraints:
    """The database is the last line of defence, independent of Python."""

    @pytest.fixture
    def loaded(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)
        return clean_db

    def _insert_invoice(self, engine, **overrides):
        values = {
            "invoice_id": "INV-999999",
            "customer_id": "CUST-0001",
            "project_id": "PRJ-1001",
            "invoice_date": "2024-06-01",
            "due_date": "2024-07-01",
            "amount": "100.00",
            "amount_paid": "0.00",
            "currency": "USD",
            "status": "Open",
        }
        values.update(overrides)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO invoices
                        (invoice_id, customer_id, project_id, invoice_date,
                         due_date, amount, amount_paid, currency, status)
                    VALUES
                        (:invoice_id, :customer_id, :project_id, :invoice_date,
                         :due_date, :amount, :amount_paid, :currency, :status)
                    """
                ),
                values,
            )

    def test_duplicate_invoice_id_violates_the_primary_key(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, invoice_id="INV-200001")

    def test_unknown_customer_violates_the_foreign_key(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, customer_id="CUST-9999")

    def test_unknown_project_violates_the_foreign_key(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, project_id="PRJ-9999")

    def test_negative_amount_violates_the_check_constraint(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, amount="-1.00")

    def test_payment_over_the_amount_violates_the_check_constraint(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, amount="100.00", amount_paid="200.00")

    def test_due_date_before_invoice_date_violates_the_check_constraint(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(
                loaded, invoice_date="2024-07-01", due_date="2024-06-01"
            )

    def test_unknown_status_violates_the_check_constraint(self, loaded):
        with pytest.raises(IntegrityError):
            self._insert_invoice(loaded, status="Pending")

    def test_a_customer_with_projects_cannot_be_deleted(self, loaded):
        with pytest.raises(IntegrityError):
            with loaded.begin() as conn:
                conn.execute(
                    text("DELETE FROM customers WHERE customer_id = 'CUST-0001'")
                )


class TestFailureHandling:
    def test_a_failing_load_rolls_back_and_is_recorded(
        self, clean_db, source_dir, monkeypatch
    ):
        """A mid-load failure must leave no data and a 'failed' run row."""
        import src.load as load_module

        calls = {"n": 0}
        real_insert_audit = load_module.insert_audit

        def exploding_audit(conn, run_id, stats):
            calls["n"] += 1
            if stats.table == "invoices":
                raise RuntimeError("simulated failure during load")
            return real_insert_audit(conn, run_id, stats)

        monkeypatch.setattr(load_module, "insert_audit", exploding_audit)

        with pytest.raises(RuntimeError, match="simulated failure"):
            run_pipeline(source_dir=source_dir, engine=clean_db)

        # Customers and projects were written before the failure, but the
        # whole load shares one transaction, so nothing survives.
        assert scalar(clean_db, "SELECT count(*) FROM customers") == 0
        assert scalar(clean_db, "SELECT count(*) FROM projects") == 0
        assert scalar(clean_db, "SELECT count(*) FROM invoices") == 0

        with clean_db.connect() as conn:
            run = conn.execute(
                text("SELECT status, error_message FROM pipeline_runs")
            ).mappings().one()
        assert run["status"] == "failed"
        assert "simulated failure" in run["error_message"]

    def test_a_missing_source_file_fails_before_any_run_is_opened(
        self, clean_db, tmp_path
    ):
        from src.extract import ExtractError

        with pytest.raises(ExtractError, match="source file not found"):
            run_pipeline(source_dir=tmp_path / "nothing", engine=clean_db)

        assert scalar(clean_db, "SELECT count(*) FROM pipeline_runs") == 0


class TestReports:
    @pytest.fixture
    def loaded(self, clean_db, source_dir):
        run_pipeline(source_dir=source_dir, engine=clean_db)
        return clean_db

    @pytest.mark.parametrize("name", list(load_queries()))
    def test_every_report_executes(self, loaded, name):
        run_report(loaded, load_queries()[name])

    def test_revenue_by_month_matches_the_invoice_totals(self, loaded):
        frame = run_report(loaded, load_queries()["revenue_by_month"])
        assert frame["total_invoiced"].sum() == Decimal("24500.00")
        assert frame["invoice_count"].sum() == 3

    def test_aging_buckets_sum_to_total_receivables(self, loaded):
        frame = run_report(loaded, load_queries()["ar_aging_summary"])
        # INV-200002 (7500 open) + INV-200003 (12000 - 3000 partial).
        assert frame["balance_due"].sum() == Decimal("16500.00")

    def test_customer_rank_is_ordered_by_revenue(self, loaded):
        frame = run_report(loaded, load_queries()["customer_revenue_rank"])
        assert list(frame["revenue_rank"]) == [1, 2]
        assert frame.iloc[0]["customer_id"] == "CUST-0001"
        assert frame.iloc[0]["total_invoiced"] == Decimal("12500.00")

    def test_project_profitability_does_not_multiply_labor_cost(self, loaded):
        """PRJ-1001 has two invoices; its labor cost must still count once."""
        frame = run_report(loaded, load_queries()["project_profitability"])
        row = frame.set_index("project_id").loc["PRJ-1001"]
        assert row["labor_cost"] == Decimal("40000.00")
        assert row["total_invoiced"] == Decimal("12500.00")
        assert row["gross_margin"] == Decimal("-27500.00")

    def test_over_budget_report_finds_the_overrun(self, loaded):
        frame = run_report(loaded, load_queries()["projects_over_budget"])
        assert list(frame["project_id"]) == ["PRJ-1002"]
        assert frame.iloc[0]["overrun_amount"] == Decimal("60000.00")

    def test_rejection_summary_reports_the_latest_run(self, loaded):
        frame = run_report(loaded, load_queries()["rejection_summary"])
        assert list(frame["rule"]) == ["orphan_customer"]
        assert int(frame.iloc[0]["rejected_rows"]) == 1


class TestShippedSampleData:
    """The committed extracts must behave as documented in the README."""

    def test_the_sample_extracts_load_with_exactly_20_rejections(self, clean_db):
        summary = run_pipeline(source_dir=DATA_DIR, engine=clean_db)

        assert summary.status == "success"
        assert summary.rows_extracted == 565
        assert summary.rows_rejected == 20
        assert summary.rows_loaded == 545
        assert summary.rows_inserted == 545

    def test_every_documented_rule_fires_on_the_sample_data(self, clean_db):
        run_pipeline(source_dir=DATA_DIR, engine=clean_db)

        with clean_db.connect() as conn:
            fired = set(
                conn.execute(text("SELECT DISTINCT rule FROM rejected_records")).scalars()
            )

        assert fired == {
            "duplicate_key",
            "missing_required",
            "invalid_date",
            "invalid_status",
            "negative_amount",
            "non_numeric_amount",
            "date_order",
            "overpaid",
            "orphan_customer",
            "orphan_project",
        }
