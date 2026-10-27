"""Extract: read the CSV extracts as raw strings.

Nothing is parsed or coerced here. Every column comes back as a string so the
transform stage sees exactly what the source system wrote, and a malformed
value becomes a rejected record rather than a pandas-level crash.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

EXPECTED_COLUMNS: dict[str, list[str]] = {
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


class ExtractError(RuntimeError):
    """A source file is missing or does not have the expected columns."""


def read_source(name: str, source_dir: Path | None = None) -> pd.DataFrame:
    """Read one named extract (``customers``, ``projects``, ``invoices``)."""
    if name not in EXPECTED_COLUMNS:
        raise ExtractError(f"unknown source '{name}'")

    path = (source_dir or DATA_DIR) / f"{name}.csv"
    if not path.exists():
        raise ExtractError(f"source file not found: {path}")

    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    missing = [c for c in EXPECTED_COLUMNS[name] if c not in frame.columns]
    if missing:
        raise ExtractError(f"{path.name} is missing columns: {', '.join(missing)}")

    # Keep the 1-based line number from the file for the rejection report.
    frame = frame.copy()
    frame["_source_row"] = frame.index + 2
    return frame


def extract_all(source_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Read all three extracts."""
    return {name: read_source(name, source_dir) for name in EXPECTED_COLUMNS}
