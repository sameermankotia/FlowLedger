"""Unit tests for the field-level transforms."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from src.transform import (
    INVOICE_STATUSES,
    PROJECT_STATUSES,
    clean_text,
    normalize_currency,
    normalize_email,
    normalize_id,
    normalize_status,
    parse_amount,
    parse_date,
    transform_invoices,
)


class TestCleanText:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  Cascade Power Inc. ", "Cascade Power Inc."),
            ("Northline   Energy", "Northline Energy"),
            ("", None),
            ("   ", None),
            (None, None),
            (float("nan"), None),
        ],
    )
    def test_trims_collapses_and_nulls(self, raw, expected):
        assert clean_text(raw) == expected


class TestNormalizeId:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  cust-0007 ", "CUST-0007"),
            ("CUST-0007", "CUST-0007"),
            ("cust 0007", "CUST0007"),
            ("", None),
            ("  ", None),
        ],
    )
    def test_canonical_key_form(self, raw, expected):
        assert normalize_id(raw) == expected

    def test_crm_and_erp_spellings_converge(self):
        """The whole point: the two systems' spellings must match."""
        assert normalize_id("  cust-0042 ") == normalize_id("CUST-0042")


class TestParseDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024-03-15", date(2024, 3, 15)),
            ("03/15/2024", date(2024, 3, 15)),
            ("15-Mar-2024", date(2024, 3, 15)),
            ("2024/03/15", date(2024, 3, 15)),
            ("  2024-03-15 ", date(2024, 3, 15)),
        ],
    )
    def test_accepts_every_source_format(self, raw, expected):
        assert parse_date(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["2024-13-45", "31/02/2024", "not a date", "", "   ", "15/15/2024"]
    )
    def test_rejects_impossible_dates_instead_of_coercing(self, raw):
        assert parse_date(raw) is None

    def test_leap_day_is_valid_in_a_leap_year(self):
        assert parse_date("2024-02-29") == date(2024, 2, 29)

    def test_leap_day_is_invalid_otherwise(self):
        assert parse_date("2023-02-29") is None


class TestParseAmount:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1234.50", Decimal("1234.50")),
            ("1,234.50", Decimal("1234.50")),
            ("$1,234.50", Decimal("1234.50")),
            (" $ 1,234.5 ", Decimal("1234.50")),
            ("(500.00)", Decimal("-500.00")),
            ("-1250.00", Decimal("-1250.00")),
            ("0", Decimal("0.00")),
        ],
    )
    def test_parses_money_formats(self, raw, expected):
        assert parse_amount(raw) == expected

    @pytest.mark.parametrize("raw", ["N/A", "", "   ", "abc", "$", "1.2.3"])
    def test_returns_none_for_unparseable(self, raw):
        assert parse_amount(raw) is None

    def test_rounds_to_two_places(self):
        assert parse_amount("10.005") == Decimal("10.01")

    def test_result_is_decimal_not_float(self):
        assert isinstance(parse_amount("0.10"), Decimal)

    def test_decimal_avoids_binary_float_error(self):
        total = parse_amount("0.10") + parse_amount("0.20")
        assert total == Decimal("0.30")


class TestNormalizeStatus:
    @pytest.mark.parametrize("raw", ["Paid", "paid", "PAID", "  paid "])
    def test_case_insensitive_match(self, raw):
        assert normalize_status(raw, INVOICE_STATUSES) == "Paid"

    def test_multiword_status(self):
        assert normalize_status("on hold", PROJECT_STATUSES) == "On Hold"

    @pytest.mark.parametrize("raw", ["Pending", "Archived", "", "paidd"])
    def test_unknown_status_is_none(self, raw):
        assert normalize_status(raw, INVOICE_STATUSES) is None

    def test_project_and_invoice_vocabularies_are_separate(self):
        assert normalize_status("Open", PROJECT_STATUSES) is None
        assert normalize_status("Active", INVOICE_STATUSES) is None


class TestSmallNormalizers:
    def test_email_is_lowercased(self):
        assert normalize_email("  AP@Cascade.Example.COM ") == "ap@cascade.example.com"

    def test_currency_is_uppercased(self):
        assert normalize_currency(" usd ") == "USD"

    def test_blank_currency_is_none(self):
        assert normalize_currency("") is None


class TestTransformInvoices:
    def test_transforms_a_whole_frame(self):
        raw = pd.DataFrame(
            [
                {
                    "invoice_id": " inv-200001 ",
                    "customer_id": "cust-0007",
                    "project_id": " prj-1001",
                    "invoice_date": "03/15/2024",
                    "due_date": "15-Apr-2024",
                    "amount": "$1,200.00",
                    "amount_paid": "0",
                    "currency": "usd",
                    "status": "open",
                }
            ]
        )
        out = transform_invoices(raw).iloc[0]

        assert out["invoice_id"] == "INV-200001"
        assert out["customer_id"] == "CUST-0007"
        assert out["project_id"] == "PRJ-1001"
        assert out["invoice_date"] == date(2024, 3, 15)
        assert out["due_date"] == date(2024, 4, 15)
        assert out["amount"] == Decimal("1200.00")
        assert out["currency"] == "USD"
        assert out["status"] == "Open"
        assert out["source_system"] == "ERP"

    def test_leaves_the_raw_frame_untouched(self):
        raw = pd.DataFrame(
            [
                {
                    "invoice_id": " inv-1 ",
                    "customer_id": "c",
                    "project_id": "p",
                    "invoice_date": "2024-01-01",
                    "due_date": "2024-02-01",
                    "amount": "1.00",
                    "amount_paid": "0",
                    "currency": "usd",
                    "status": "open",
                }
            ]
        )
        transform_invoices(raw)
        assert raw.at[0, "invoice_id"] == " inv-1 "
