"""Shared fixtures.

Unit tests for the transform and validate stages run with no database.
The pipeline tests need PostgreSQL; when it is not reachable they skip
rather than fail, so ``pytest`` is useful before ``docker compose up``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from src.config import make_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED_TABLES = (
    "load_audit",
    "rejected_records",
    "pipeline_runs",
    "invoices",
    "projects",
    "customers",
)


@pytest.fixture(scope="session")
def engine():
    """A live engine, or a skip when PostgreSQL is not up."""
    engine = make_engine(connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not reachable: {type(exc).__name__}")
    return engine


@pytest.fixture
def clean_db(engine):
    """An empty schema before and after each database test."""
    from src.load import apply_schema

    apply_schema(engine)
    _truncate(engine)
    yield engine
    _truncate(engine)


def _truncate(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"TRUNCATE {', '.join(MANAGED_TABLES)} RESTART IDENTITY CASCADE"
            )
        )


def frame(rows: list[dict], start_row: int = 2) -> pd.DataFrame:
    """Build a raw-style DataFrame with the _source_row column extract adds."""
    df = pd.DataFrame(rows, dtype=str)
    df["_source_row"] = range(start_row, start_row + len(df))
    return df
