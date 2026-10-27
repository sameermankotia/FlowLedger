"""Pipeline entry point: extract -> validate -> transform -> load.

    python -m src.pipeline                   # load data/ into the database
    python -m src.pipeline --source-dir X    # load a different extract folder
    python -m src.pipeline --dry-run         # validate only, write nothing
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine

from src.config import DATA_DIR, make_engine
from src.extract import extract_all
from src.load import TableLoadStats, apply_schema, finish_run, load_all, start_run
from src.transform import transform_all
from src.validate import ValidationResult, validate_all

log = logging.getLogger("pipeline")


@dataclass
class RunSummary:
    run_id: int | None
    status: str
    rows_extracted: int = 0
    rows_loaded: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    rejections_by_rule: dict[str, dict[str, int]] = field(default_factory=dict)
    table_stats: dict[str, TableLoadStats] = field(default_factory=dict)
    error_message: str | None = None

    def render(self) -> str:
        heading = (
            f"  pipeline run {self.run_id}  --  {self.status.upper()}"
            if self.run_id is not None
            else f"  pipeline  --  {self.status.upper()} (nothing written)"
        )
        lines = [
            "",
            "=" * 68,
            heading,
            "=" * 68,
            f"  extracted {self.rows_extracted:>5} rows"
            f"   loaded {self.rows_loaded:>5}"
            f"   rejected {self.rows_rejected:>4}",
        ]
        if self.table_stats:
            lines += [
                "-" * 68,
                f"  {'table':<12}{'in':>7}{'inserted':>10}{'updated':>9}{'rejected':>10}",
            ]
            for table, stats in self.table_stats.items():
                lines.append(
                    f"  {table:<12}{stats.rows_in:>7}{stats.rows_inserted:>10}"
                    f"{stats.rows_updated:>9}{stats.rows_rejected:>10}"
                )
        if self.rows_rejected:
            lines += ["-" * 68, "  rejections by rule"]
            for table, counts in self.rejections_by_rule.items():
                if not counts:
                    continue
                for rule, count in counts.items():
                    lines.append(f"  {table:<12}{rule:<22}{count:>5}")
        if self.error_message:
            lines += ["-" * 68, f"  error: {self.error_message}"]
        lines.append("=" * 68)
        return "\n".join(lines)


def _summarize(
    results: dict[str, ValidationResult],
    raw_counts: dict[str, int],
) -> RunSummary:
    return RunSummary(
        run_id=None,
        status="running",
        rows_extracted=sum(raw_counts.values()),
        rows_rejected=sum(r.rejected_count for r in results.values()),
        rejections_by_rule={
            table: result.counts_by_rule() for table, result in results.items()
        },
    )


def run_pipeline(
    source_dir: Path | None = None,
    engine: Engine | None = None,
    dry_run: bool = False,
) -> RunSummary:
    """Run the full pipeline once and return its summary.

    On failure the run is marked ``failed`` in ``pipeline_runs`` with the
    error message, and the exception is re-raised for the caller.
    """
    source_dir = source_dir or DATA_DIR
    engine = engine or make_engine()

    log.info("extracting from %s", source_dir)
    raw = extract_all(source_dir)
    raw_counts = {name: len(frame) for name, frame in raw.items()}

    log.info("transforming %s rows", sum(raw_counts.values()))
    clean = transform_all(raw)

    log.info("validating")
    results = validate_all(raw, clean)
    summary = _summarize(results, raw_counts)

    for table, result in results.items():
        if result.rejections:
            log.warning(
                "%s: %s rejected (%s)",
                table,
                result.rejected_count,
                ", ".join(f"{k}={v}" for k, v in result.counts_by_rule().items()),
            )

    if dry_run:
        summary.status = "dry-run"
        return summary

    apply_schema(engine)
    run_id = start_run(engine, source_dir)
    summary.run_id = run_id
    log.info("run %s started", run_id)

    try:
        stats = load_all(engine, run_id, results)
    except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
        summary.status = "failed"
        summary.error_message = f"{type(exc).__name__}: {exc}"
        finish_run(
            engine,
            run_id,
            "failed",
            rows_extracted=summary.rows_extracted,
            rows_rejected=summary.rows_rejected,
            error_message=summary.error_message,
        )
        log.error("run %s failed: %s", run_id, summary.error_message)
        raise

    summary.table_stats = stats
    summary.rows_loaded = sum(s.rows_in for s in stats.values())
    summary.rows_inserted = sum(s.rows_inserted for s in stats.values())
    summary.rows_updated = sum(s.rows_updated for s in stats.values())
    summary.status = "success"

    finish_run(
        engine,
        run_id,
        "success",
        rows_extracted=summary.rows_extracted,
        rows_loaded=summary.rows_loaded,
        rows_inserted=summary.rows_inserted,
        rows_updated=summary.rows_updated,
        rows_rejected=summary.rows_rejected,
    )
    log.info("run %s finished", run_id)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ERP integration pipeline.")
    parser.add_argument(
        "--source-dir", type=Path, default=DATA_DIR, help="folder holding the CSVs"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate only; write nothing"
    )
    parser.add_argument("--quiet", action="store_true", help="log warnings only")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    summary = run_pipeline(source_dir=args.source_dir, dry_run=args.dry_run)
    print(summary.render())
    return 0 if summary.status in {"success", "dry-run"} else 1


if __name__ == "__main__":
    sys.exit(main())
