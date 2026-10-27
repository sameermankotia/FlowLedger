"""Validate: separate loadable rows from rejected rows.

A rejected row is never silently dropped. Each one is returned as a
:class:`Rejection` carrying the source line number, the rule it broke, a
human-readable reason, and the original raw record, which the loader writes
to ``rejected_records``.

Each rejected row produces exactly one Rejection, so a run's rejection count
matches its rejected row count. When a row breaks several rules, ``rule`` is
the first one in the table's rule order and ``reason`` lists all of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable

import pandas as pd

from src.transform import INVOICE_STATUSES, PROJECT_STATUSES

RAW_COLUMNS = {
    "customers": [
        "customer_id", "customer_name", "contact_email", "contact_phone",
        "industry", "country", "created_date",
    ],
    "projects": [
        "project_id", "customer_id", "project_name", "project_manager",
        "status", "start_date", "end_date", "budget_amount", "labor_cost",
    ],
    "invoices": [
        "invoice_id", "customer_id", "project_id", "invoice_date", "due_date",
        "amount", "amount_paid", "currency", "status",
    ],
}


@dataclass(frozen=True)
class Rejection:
    source_table: str
    source_row: int | None
    natural_key: str | None
    rule: str
    reason: str
    raw_record: dict[str, Any]


@dataclass
class ValidationResult:
    clean: pd.DataFrame
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def rejected_count(self) -> int:
        return len(self.rejections)

    def counts_by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for rejection in self.rejections:
            counts[rejection.rule] = counts.get(rejection.rule, 0) + 1
        return dict(sorted(counts.items()))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return isinstance(value, str) and not value.strip()


def _present_in_source(raw_value: Any) -> bool:
    """True when the source file actually carried a value for this field."""
    return not _is_blank(raw_value)


def _required(row: dict, raw: dict, fields: Iterable[str]) -> list[tuple[str, str]]:
    return [
        ("missing_required", f"{name} is required but missing")
        for name in fields
        if _is_blank(row.get(name))
        and not _present_in_source(raw.get(name))
    ]


def _unparsed(
    row: dict,
    raw: dict,
    fields: Iterable[str],
    rule: str,
    label: str,
) -> list[tuple[str, str]]:
    """Fields the source populated but the transform could not parse."""
    return [
        (rule, f"{name}={raw.get(name)!r} is not a valid {label}")
        for name in fields
        if row.get(name) is None and _present_in_source(raw.get(name))
    ]


def _validate_table(
    name: str,
    raw: pd.DataFrame,
    clean: pd.DataFrame,
    key: str,
    row_rules: Callable[[dict, dict], list[tuple[str, str]]],
) -> ValidationResult:
    """Apply per-row rules, then reject duplicate keys, keeping the first."""
    rejections: list[Rejection] = []
    keep_index: list[Any] = []
    seen_keys: dict[str, int] = {}

    raw_cols = RAW_COLUMNS[name]
    for index, row in clean.iterrows():
        row_dict = row.to_dict()
        raw_dict = {col: raw.at[index, col] for col in raw_cols}
        source_row = row_dict.get("_source_row")
        source_row = int(source_row) if source_row is not None else None
        natural_key = row_dict.get(key)

        violations = row_rules(row_dict, raw_dict)

        if not violations and natural_key in seen_keys:
            violations = [
                (
                    "duplicate_key",
                    f"{key}={natural_key} already seen at source row "
                    f"{seen_keys[natural_key]}",
                )
            ]

        if violations:
            rule, _ = violations[0]
            rejections.append(
                Rejection(
                    source_table=name,
                    source_row=source_row,
                    natural_key=natural_key,
                    rule=rule,
                    reason="; ".join(message for _, message in violations),
                    raw_record={k: _jsonable(v) for k, v in raw_dict.items()},
                )
            )
            continue

        seen_keys[natural_key] = source_row
        keep_index.append(index)

    return ValidationResult(clean=clean.loc[keep_index].copy(), rejections=rejections)


def _jsonable(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


# ---------------------------------------------------------------------------
# Per-table rules
# ---------------------------------------------------------------------------

def validate_customers(raw: pd.DataFrame, clean: pd.DataFrame) -> ValidationResult:
    def rules(row: dict, raw_row: dict) -> list[tuple[str, str]]:
        return [
            *_required(row, raw_row, ["customer_id", "customer_name"]),
            *_blank_after_trim(row, raw_row, ["customer_id", "customer_name"]),
            *_unparsed(row, raw_row, ["created_date"], "invalid_date", "date"),
        ]

    return _validate_table("customers", raw, clean, "customer_id", rules)


def _blank_after_trim(
    row: dict, raw: dict, fields: Iterable[str]
) -> list[tuple[str, str]]:
    """Fields that held only whitespace at source, e.g. a name of '   '."""
    return [
        ("missing_required", f"{name}={raw.get(name)!r} is blank after trimming")
        for name in fields
        if _is_blank(row.get(name)) and _present_in_source(raw.get(name))
    ]


def validate_projects(
    raw: pd.DataFrame,
    clean: pd.DataFrame,
    valid_customer_ids: set[str],
) -> ValidationResult:
    def rules(row: dict, raw_row: dict) -> list[tuple[str, str]]:
        required = ["project_id", "customer_id", "project_name", "status"]
        violations = [
            *_required(row, raw_row, required),
            *_blank_after_trim(row, raw_row, ["project_id", "customer_id", "project_name"]),
            *_unparsed(row, raw_row, ["status"], "invalid_status",
                       f"status (expected one of {', '.join(PROJECT_STATUSES)})"),
            *_unparsed(row, raw_row, ["start_date", "end_date"], "invalid_date", "date"),
            *_unparsed(row, raw_row, ["budget_amount", "labor_cost"],
                       "non_numeric_amount", "amount"),
        ]

        for field_name in ("budget_amount", "labor_cost"):
            value = row.get(field_name)
            if isinstance(value, Decimal) and value < 0:
                violations.append(
                    ("negative_amount", f"{field_name}={value} must not be negative")
                )

        start, end = row.get("start_date"), row.get("end_date")
        if start is not None and end is not None and end < start:
            violations.append(
                ("date_order", f"end_date {end} is before start_date {start}")
            )

        customer_id = row.get("customer_id")
        if customer_id and customer_id not in valid_customer_ids:
            violations.append(
                ("orphan_customer", f"customer_id={customer_id} does not exist")
            )

        return violations

    return _validate_table("projects", raw, clean, "project_id", rules)


def validate_invoices(
    raw: pd.DataFrame,
    clean: pd.DataFrame,
    valid_customer_ids: set[str],
    valid_project_ids: set[str],
) -> ValidationResult:
    def rules(row: dict, raw_row: dict) -> list[tuple[str, str]]:
        required = [
            "invoice_id", "customer_id", "invoice_date", "due_date",
            "amount", "status",
        ]
        violations = [
            *_required(row, raw_row, required),
            *_blank_after_trim(row, raw_row, ["invoice_id", "customer_id"]),
            *_unparsed(row, raw_row, ["status"], "invalid_status",
                       f"status (expected one of {', '.join(INVOICE_STATUSES)})"),
            *_unparsed(row, raw_row, ["invoice_date", "due_date"],
                       "invalid_date", "date"),
            *_unparsed(row, raw_row, ["amount", "amount_paid"],
                       "non_numeric_amount", "amount"),
        ]

        amount = row.get("amount")
        paid = row.get("amount_paid")
        if isinstance(amount, Decimal) and amount < 0:
            violations.append(("negative_amount", f"amount={amount} must not be negative"))
        if isinstance(paid, Decimal) and paid < 0:
            violations.append(
                ("negative_amount", f"amount_paid={paid} must not be negative")
            )
        if (
            isinstance(amount, Decimal)
            and isinstance(paid, Decimal)
            and amount >= 0
            and paid > amount
        ):
            # Only meaningful once the amount itself is sane; a negative
            # amount is already reported as negative_amount.
            violations.append(
                ("overpaid", f"amount_paid={paid} exceeds amount={amount}")
            )

        invoice_date, due_date = row.get("invoice_date"), row.get("due_date")
        if invoice_date is not None and due_date is not None and due_date < invoice_date:
            violations.append(
                ("date_order", f"due_date {due_date} is before invoice_date {invoice_date}")
            )

        customer_id = row.get("customer_id")
        if customer_id and customer_id not in valid_customer_ids:
            violations.append(
                ("orphan_customer", f"customer_id={customer_id} does not exist")
            )

        project_id = row.get("project_id")
        if project_id and project_id not in valid_project_ids:
            violations.append(
                ("orphan_project", f"project_id={project_id} does not exist")
            )

        return violations

    return _validate_table("invoices", raw, clean, "invoice_id", rules)


def validate_all(
    raw: dict[str, pd.DataFrame],
    clean: dict[str, pd.DataFrame],
) -> dict[str, ValidationResult]:
    """Validate the three tables in dependency order.

    Projects are checked against the customers that survived validation, and
    invoices against the surviving customers and projects, so a child row is
    never loaded against a parent that was itself rejected.
    """
    customers = validate_customers(raw["customers"], clean["customers"])
    customer_ids = set(customers.clean["customer_id"])

    projects = validate_projects(raw["projects"], clean["projects"], customer_ids)
    project_ids = set(projects.clean["project_id"])

    invoices = validate_invoices(
        raw["invoices"], clean["invoices"], customer_ids, project_ids
    )
    return {"customers": customers, "projects": projects, "invoices": invoices}
