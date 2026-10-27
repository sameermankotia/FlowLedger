"""Load: upsert clean rows into PostgreSQL and record what happened.

Idempotency comes from the primary keys plus ``ON CONFLICT DO UPDATE``: a
second run over the same extracts updates the existing rows instead of
inserting duplicates. All three tables, the rejected records and the audit
rows are written in a single transaction, so a failure part-way through
leaves no half-loaded run behind.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd
from sqlalchemy import Connection, Engine, text

from src.config import SQL_DIR
from src.validate import Rejection, ValidationResult

BATCH_SIZE = 500

TARGET_COLUMNS: dict[str, list[str]] = {
    "customers": [
        "customer_id", "customer_name", "contact_email", "contact_phone",
        "industry", "country", "created_date", "source_system",
    ],
    "projects": [
        "project_id", "customer_id", "project_name", "project_manager",
        "status", "start_date", "end_date", "budget_amount", "labor_cost",
        "source_system",
    ],
    "invoices": [
        "invoice_id", "customer_id", "project_id", "invoice_date", "due_date",
        "amount", "amount_paid", "currency", "status", "source_system",
    ],
}

PRIMARY_KEYS = {
    "customers": "customer_id",
    "projects": "project_id",
    "invoices": "invoice_id",
}

# Tables must load parents first so the foreign keys resolve.
LOAD_ORDER = ("customers", "projects", "invoices")


@dataclass
class TableLoadStats:
    table: str
    rows_in: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    duration_ms: int = 0


def apply_schema(engine: Engine) -> None:
    """Run sql/schema.sql. It is written to be safe to re-run."""
    ddl = (SQL_DIR / "schema.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(ddl))


def start_run(engine: Engine, source_dir: Path) -> int:
    """Open a pipeline_runs row in its own transaction.

    Committing immediately means the run is on record even if the load that
    follows fails and rolls back.
    """
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                INSERT INTO pipeline_runs (source_dir, status)
                VALUES (:source_dir, 'running')
                RETURNING run_id
                """
            ),
            {"source_dir": str(source_dir)},
        ).scalar_one()


def finish_run(
    engine: Engine,
    run_id: int,
    status: str,
    *,
    rows_extracted: int = 0,
    rows_loaded: int = 0,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    rows_rejected: int = 0,
    error_message: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE pipeline_runs
                   SET finished_at    = now(),
                       status         = :status,
                       rows_extracted = :rows_extracted,
                       rows_loaded    = :rows_loaded,
                       rows_inserted  = :rows_inserted,
                       rows_updated   = :rows_updated,
                       rows_rejected  = :rows_rejected,
                       error_message  = :error_message
                 WHERE run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "rows_extracted": rows_extracted,
                "rows_loaded": rows_loaded,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_rejected": rows_rejected,
                "error_message": error_message,
            },
        )


def _records(frame: pd.DataFrame, columns: Sequence[str]) -> list[dict[str, Any]]:
    """DataFrame rows as parameter dicts, with pandas nulls mapped to None."""
    records = []
    for row in frame[list(columns)].to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for key, value in row.items():
            if value is None or (isinstance(value, float) and pd.isna(value)):
                clean[key] = None
            elif isinstance(value, Decimal):
                clean[key] = value
            else:
                clean[key] = value
        records.append(clean)
    return records


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _upsert_sql(table: str) -> str:
    columns = TARGET_COLUMNS[table]
    pk = PRIMARY_KEYS[table]
    updatable = [c for c in columns if c != pk]
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
    return f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({', '.join(f':{c}' for c in columns)})
        ON CONFLICT ({pk}) DO UPDATE
           SET {assignments},
               updated_at = now()
    """


def upsert_table(
    conn: Connection,
    table: str,
    frame: pd.DataFrame,
) -> TableLoadStats:
    """Upsert one table, counting inserts and updates separately."""
    started = time.perf_counter()
    stats = TableLoadStats(table=table, rows_in=len(frame))
    if frame.empty:
        stats.duration_ms = int((time.perf_counter() - started) * 1000)
        return stats

    pk = PRIMARY_KEYS[table]
    records = _records(frame, TARGET_COLUMNS[table])
    keys = [record[pk] for record in records]

    # Keys already present become updates; the rest are inserts. Counted
    # before the write, inside the same transaction, so the split is exact.
    existing = set(
        conn.execute(
            text(f"SELECT {pk} FROM {table} WHERE {pk} = ANY(:keys)"),
            {"keys": keys},
        ).scalars()
    )
    stats.rows_updated = sum(1 for key in keys if key in existing)
    stats.rows_inserted = len(keys) - stats.rows_updated

    statement = text(_upsert_sql(table))
    for batch in _chunks(records, BATCH_SIZE):
        conn.execute(statement, batch)

    stats.duration_ms = int((time.perf_counter() - started) * 1000)
    return stats


def insert_rejections(
    conn: Connection, run_id: int, rejections: list[Rejection]
) -> None:
    if not rejections:
        return
    statement = text(
        """
        INSERT INTO rejected_records
            (run_id, source_table, source_row, natural_key, rule, reason, raw_record)
        VALUES
            (:run_id, :source_table, :source_row, :natural_key, :rule, :reason,
             CAST(:raw_record AS JSONB))
        """
    )
    payload = [
        {
            "run_id": run_id,
            "source_table": r.source_table,
            "source_row": r.source_row,
            "natural_key": r.natural_key,
            "rule": r.rule,
            "reason": r.reason,
            "raw_record": json.dumps(r.raw_record),
        }
        for r in rejections
    ]
    for batch in _chunks(payload, BATCH_SIZE):
        conn.execute(statement, batch)


def insert_audit(conn: Connection, run_id: int, stats: TableLoadStats) -> None:
    conn.execute(
        text(
            """
            INSERT INTO load_audit
                (run_id, target_table, rows_in, rows_inserted, rows_updated,
                 rows_rejected, duration_ms)
            VALUES
                (:run_id, :target_table, :rows_in, :rows_inserted, :rows_updated,
                 :rows_rejected, :duration_ms)
            """
        ),
        {
            "run_id": run_id,
            "target_table": stats.table,
            "rows_in": stats.rows_in,
            "rows_inserted": stats.rows_inserted,
            "rows_updated": stats.rows_updated,
            "rows_rejected": stats.rows_rejected,
            "duration_ms": stats.duration_ms,
        },
    )


def load_all(
    engine: Engine,
    run_id: int,
    results: dict[str, ValidationResult],
) -> dict[str, TableLoadStats]:
    """Load every table, its rejections and its audit row in one transaction."""
    stats: dict[str, TableLoadStats] = {}
    with engine.begin() as conn:
        for table in LOAD_ORDER:
            result = results[table]
            table_stats = upsert_table(conn, table, result.clean)
            table_stats.rows_rejected = result.rejected_count
            insert_rejections(conn, run_id, result.rejections)
            insert_audit(conn, run_id, table_stats)
            stats[table] = table_stats
    return stats
