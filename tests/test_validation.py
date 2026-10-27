"""Unit tests for the validation rules.

Each test states one bad-data case and asserts both that the row does not
reach the clean set and that it is reported with the expected rule.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.transform import transform_customers, transform_invoices, transform_projects
from src.validate import (
    validate_all,
    validate_customers,
    validate_invoices,
    validate_projects,
)
from tests.conftest import frame

CUSTOMER_ROW = {
    "customer_id": "CUST-0001",
    "customer_name": "Cascade Power Inc.",
    "contact_email": "ap@cascade.example.com",
    "contact_phone": "(555) 010-1000",
    "industry": "Utilities",
    "country": "USA",
    "created_date": "2022-01-15",
}
PROJECT_ROW = {
    "project_id": "PRJ-1001",
    "customer_id": "CUST-0001",
    "project_name": "Substation Upgrade",
    "project_manager": "Ada Lovelace",
    "status": "Active",
    "start_date": "2024-01-10",
    "end_date": "",
    "budget_amount": "100000.00",
    "labor_cost": "40000.00",
}
INVOICE_ROW = {
    "invoice_id": "INV-200001",
    "customer_id": "CUST-0001",
    "project_id": "PRJ-1001",
    "invoice_date": "2024-02-01",
    "due_date": "2024-03-02",
    "amount": "5000.00",
    "amount_paid": "0.00",
    "currency": "USD",
    "status": "Open",
}


def customers(*overrides: dict):
    rows = [{**CUSTOMER_ROW, **o} for o in overrides] or [dict(CUSTOMER_ROW)]
    raw = frame(rows)
    return validate_customers(raw, transform_customers(raw))


def projects(*overrides: dict, customer_ids=frozenset({"CUST-0001"})):
    rows = [{**PROJECT_ROW, **o} for o in overrides] or [dict(PROJECT_ROW)]
    raw = frame(rows)
    return validate_projects(raw, transform_projects(raw), set(customer_ids))


def invoices(
    *overrides: dict,
    customer_ids=frozenset({"CUST-0001"}),
    project_ids=frozenset({"PRJ-1001"}),
):
    rows = [{**INVOICE_ROW, **o} for o in overrides] or [dict(INVOICE_ROW)]
    raw = frame(rows)
    return validate_invoices(
        raw, transform_invoices(raw), set(customer_ids), set(project_ids)
    )


def rules(result) -> list[str]:
    return [r.rule for r in result.rejections]


class TestHappyPath:
    def test_a_good_customer_passes(self):
        result = customers()
        assert len(result.clean) == 1
        assert result.rejections == []

    def test_a_good_project_passes(self):
        assert len(projects().clean) == 1

    def test_a_good_invoice_passes(self):
        assert len(invoices().clean) == 1

    def test_messy_but_valid_values_pass(self):
        """Whitespace, lower-case ids and odd date formats are not errors."""
        result = invoices(
            {
                "invoice_id": "  inv-200001 ",
                "customer_id": " cust-0001",
                "invoice_date": "02/01/2024",
                "due_date": "02-Mar-2024",
                "amount": "$5,000.00",
                "status": "open",
            }
        )
        assert result.rejections == []
        assert result.clean.iloc[0]["invoice_id"] == "INV-200001"


class TestCustomerRules:
    def test_blank_customer_id_is_rejected(self):
        result = customers({"customer_id": ""})
        assert result.clean.empty
        assert rules(result) == ["missing_required"]

    def test_whitespace_only_name_is_rejected(self):
        result = customers({"customer_name": "   "})
        assert rules(result) == ["missing_required"]

    def test_unparseable_created_date_is_rejected(self):
        result = customers({"created_date": "2024-13-45"})
        assert rules(result) == ["invalid_date"]

    def test_absent_created_date_is_allowed(self):
        """created_date is optional, so an empty one is not an error."""
        result = customers({"created_date": ""})
        assert result.rejections == []
        assert result.clean.iloc[0]["created_date"] is None

    def test_duplicate_id_keeps_the_first_row(self):
        result = customers(
            {"customer_name": "First Spelling"},
            {"customer_name": "Second Spelling"},
        )
        assert len(result.clean) == 1
        assert result.clean.iloc[0]["customer_name"] == "First Spelling"
        assert rules(result) == ["duplicate_key"]

    def test_duplicate_detection_is_case_insensitive(self):
        """The CRM's 'cust-0001' is the ERP's 'CUST-0001'."""
        result = customers({}, {"customer_id": "  cust-0001 "})
        assert len(result.clean) == 1
        assert rules(result) == ["duplicate_key"]

    def test_rejection_carries_the_source_row_and_raw_values(self):
        result = customers({"created_date": "2024-13-45"})
        rejection = result.rejections[0]
        assert rejection.source_row == 2
        assert rejection.source_table == "customers"
        assert rejection.raw_record["created_date"] == "2024-13-45"
        assert "2024-13-45" in rejection.reason


class TestProjectRules:
    def test_negative_budget_is_rejected(self):
        assert rules(projects({"budget_amount": "-45000.00"})) == ["negative_amount"]

    def test_end_before_start_is_rejected(self):
        result = projects({"start_date": "2024-08-01", "end_date": "2024-03-01"})
        assert rules(result) == ["date_order"]

    def test_end_equal_to_start_is_allowed(self):
        result = projects({"start_date": "2024-08-01", "end_date": "2024-08-01"})
        assert result.rejections == []

    def test_unknown_status_is_rejected(self):
        assert rules(projects({"status": "Archived"})) == ["invalid_status"]

    def test_nonexistent_customer_is_rejected(self):
        assert rules(projects({"customer_id": "CUST-9999"})) == ["orphan_customer"]

    def test_non_numeric_budget_is_rejected(self):
        assert rules(projects({"budget_amount": "TBD"})) == ["non_numeric_amount"]

    def test_duplicate_project_id_is_rejected(self):
        assert rules(projects({}, {})) == ["duplicate_key"]


class TestInvoiceRules:
    def test_missing_customer_id_is_rejected(self):
        assert rules(invoices({"customer_id": ""})) == ["missing_required"]

    def test_negative_amount_is_rejected(self):
        assert rules(invoices({"amount": "-1250.00"})) == ["negative_amount"]

    def test_zero_amount_is_allowed(self):
        assert invoices({"amount": "0.00"}).rejections == []

    def test_non_numeric_amount_is_rejected(self):
        assert rules(invoices({"amount": "N/A"})) == ["non_numeric_amount"]

    def test_invalid_invoice_date_is_rejected(self):
        assert rules(invoices({"invoice_date": "31/02/2024"})) == ["invalid_date"]

    def test_due_date_before_invoice_date_is_rejected(self):
        result = invoices({"invoice_date": "2025-03-20", "due_date": "2025-02-20"})
        assert rules(result) == ["date_order"]

    def test_due_date_equal_to_invoice_date_is_allowed(self):
        result = invoices({"invoice_date": "2025-03-20", "due_date": "2025-03-20"})
        assert result.rejections == []

    def test_payment_over_the_invoice_amount_is_rejected(self):
        result = invoices(
            {"amount": "4000.00", "amount_paid": "6500.00", "status": "Partial"}
        )
        assert rules(result) == ["overpaid"]

    def test_payment_equal_to_the_amount_is_allowed(self):
        result = invoices(
            {"amount": "4000.00", "amount_paid": "4000.00", "status": "Paid"}
        )
        assert result.rejections == []

    def test_unknown_status_is_rejected(self):
        assert rules(invoices({"status": "Pending"})) == ["invalid_status"]

    def test_nonexistent_customer_is_rejected(self):
        assert rules(invoices({"customer_id": "CUST-9001"})) == ["orphan_customer"]

    def test_nonexistent_project_is_rejected(self):
        assert rules(invoices({"project_id": "PRJ-9999"})) == ["orphan_project"]

    def test_absent_project_is_allowed(self):
        """project_id is nullable: not every invoice belongs to a project."""
        result = invoices({"project_id": ""})
        assert result.rejections == []
        assert result.clean.iloc[0]["project_id"] is None

    def test_identical_duplicate_is_rejected_once(self):
        result = invoices({}, {})
        assert len(result.clean) == 1
        assert rules(result) == ["duplicate_key"]

    def test_conflicting_duplicate_keeps_the_first_amount(self):
        result = invoices({"amount": "5000.00"}, {"amount": "99999.00"})
        assert str(result.clean.iloc[0]["amount"]) == "5000.00"
        assert rules(result) == ["duplicate_key"]

    def test_several_violations_report_one_row_with_every_reason(self):
        result = invoices({"amount": "-10.00", "status": "Pending"})
        assert len(result.rejections) == 1
        reason = result.rejections[0].reason
        assert "must not be negative" in reason
        assert "not a valid status" in reason


class TestCrossTableValidation:
    """Children must not be loaded against a parent that was itself rejected."""

    def _sources(self):
        return {
            "customers": frame([{**CUSTOMER_ROW, "customer_name": "   "}]),
            "projects": frame([dict(PROJECT_ROW)]),
            "invoices": frame([dict(INVOICE_ROW)]),
        }

    def test_rejected_customer_cascades_to_project_and_invoice(self):
        raw = self._sources()
        clean = {
            "customers": transform_customers(raw["customers"]),
            "projects": transform_projects(raw["projects"]),
            "invoices": transform_invoices(raw["invoices"]),
        }
        results = validate_all(raw, clean)

        assert results["customers"].clean.empty
        assert rules(results["projects"]) == ["orphan_customer"]
        assert rules(results["invoices"]) == ["orphan_customer"]

    def test_counts_by_rule_groups_the_rejections(self):
        result = invoices(
            {"invoice_id": "INV-1", "amount": "-1.00"},
            {"invoice_id": "INV-2", "amount": "N/A"},
            {"invoice_id": "INV-3", "status": "Pending"},
            {"invoice_id": "INV-3", "status": "Open"},
        )
        assert result.counts_by_rule() == {
            "invalid_status": 1,
            "negative_amount": 1,
            "non_numeric_amount": 1,
        }
        assert result.rejected_count == 3


class TestEmptyInput:
    def test_an_empty_extract_validates_to_nothing(self):
        raw = pd.DataFrame(columns=list(CUSTOMER_ROW) + ["_source_row"], dtype=str)
        result = validate_customers(raw, transform_customers(raw))
        assert result.clean.empty
        assert result.rejections == []
