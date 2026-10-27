"""Transform: normalize the raw strings into typed, canonical values.

Each helper returns ``None`` when a value cannot be parsed instead of raising.
The typed column sits next to the raw one, so :mod:`src.validate` can tell a
value that was absent at source from one that was present but malformed.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import pandas as pd

# The two source systems disagree on date format; accept all four.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d")

PROJECT_STATUSES = ("Active", "Completed", "On Hold", "Cancelled")
INVOICE_STATUSES = ("Paid", "Open", "Partial", "Void")

_WHITESPACE = re.compile(r"\s+")
_MONEY_NOISE = re.compile(r"[\s$,]")


def clean_text(value: object) -> str | None:
    """Trim, collapse internal whitespace, and map empty strings to None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = _WHITESPACE.sub(" ", str(value)).strip()
    return text or None


def normalize_id(value: object) -> str | None:
    """Canonical key form: trimmed, whitespace-free, upper case.

    ``'  cust-0007 '`` and ``'CUST-0007'`` are the same customer; the CRM
    exports the first and the ERP the second.
    """
    text = clean_text(value)
    if text is None:
        return None
    return text.replace(" ", "").upper()


def normalize_email(value: object) -> str | None:
    text = clean_text(value)
    return text.lower() if text else None


def parse_date(value: object) -> date | None:
    """Parse a date in any accepted source format, else None.

    Parsing is strict: ``'2024-13-45'`` and ``'31/02/2024'`` are rejected
    rather than coerced to a nearby real date.
    """
    text = clean_text(value)
    if text is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value: object) -> Decimal | None:
    """Parse a money string to Decimal, else None.

    Handles ``'1,234.50'``, ``'$1,234.50'`` and the accounting negative
    ``'(500.00)'``. Rounds half-up to two places -- the scale of the target
    columns, and the convention finance expects, rather than Decimal's
    default banker's rounding.
    """
    text = clean_text(value)
    if text is None:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = _MONEY_NOISE.sub("", text)
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return -amount if negative else amount


def normalize_status(value: object, allowed: tuple[str, ...]) -> str | None:
    """Match a status case-insensitively against the allowed set, else None."""
    text = clean_text(value)
    if text is None:
        return None
    lookup = {status.casefold(): status for status in allowed}
    return lookup.get(text.casefold())


def normalize_currency(value: object) -> str | None:
    text = clean_text(value)
    return text.upper() if text else None


# ---------------------------------------------------------------------------
# Table-level transforms
# ---------------------------------------------------------------------------

def transform_customers(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["customer_id"] = raw["customer_id"].map(normalize_id)
    out["customer_name"] = raw["customer_name"].map(clean_text)
    out["contact_email"] = raw["contact_email"].map(normalize_email)
    out["contact_phone"] = raw["contact_phone"].map(clean_text)
    out["industry"] = raw["industry"].map(clean_text)
    out["country"] = raw["country"].map(clean_text)
    out["created_date"] = raw["created_date"].map(parse_date)
    out["source_system"] = "CRM"
    return out


def transform_projects(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["project_id"] = raw["project_id"].map(normalize_id)
    out["customer_id"] = raw["customer_id"].map(normalize_id)
    out["project_name"] = raw["project_name"].map(clean_text)
    out["project_manager"] = raw["project_manager"].map(clean_text)
    out["status"] = raw["status"].map(lambda v: normalize_status(v, PROJECT_STATUSES))
    out["start_date"] = raw["start_date"].map(parse_date)
    out["end_date"] = raw["end_date"].map(parse_date)
    out["budget_amount"] = raw["budget_amount"].map(parse_amount)
    out["labor_cost"] = raw["labor_cost"].map(parse_amount)
    out["source_system"] = "ERP"
    return out


def transform_invoices(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["invoice_id"] = raw["invoice_id"].map(normalize_id)
    out["customer_id"] = raw["customer_id"].map(normalize_id)
    out["project_id"] = raw["project_id"].map(normalize_id)
    out["invoice_date"] = raw["invoice_date"].map(parse_date)
    out["due_date"] = raw["due_date"].map(parse_date)
    out["amount"] = raw["amount"].map(parse_amount)
    out["amount_paid"] = raw["amount_paid"].map(parse_amount)
    out["currency"] = raw["currency"].map(normalize_currency)
    out["status"] = raw["status"].map(lambda v: normalize_status(v, INVOICE_STATUSES))
    out["source_system"] = "ERP"
    return out


TRANSFORMS = {
    "customers": transform_customers,
    "projects": transform_projects,
    "invoices": transform_invoices,
}


def transform_all(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {name: TRANSFORMS[name](frame) for name, frame in raw.items()}
