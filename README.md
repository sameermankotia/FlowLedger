# FlowLedger

**ERP data integration & reporting pipeline**

[**Live report snapshot →**](https://sameermankotia.github.io/FlowLedger/)
&nbsp;·&nbsp;
[Architecture](docs/architecture.md)
&nbsp;·&nbsp;
[Sample SQL output](docs/sample_reports.md)

[![tests](https://github.com/sameermankotia/FlowLedger/actions/workflows/tests.yml/badge.svg)](https://github.com/sameermankotia/FlowLedger/actions/workflows/tests.yml)

A Python and PostgreSQL ETL project that simulates integrating customer,
project and invoice data across two enterprise business systems — a CRM that
owns customers and an ERP that owns projects and invoices — then reports on
the combined result.

The interesting part is not that it loads CSV files. It is that the source
extracts are deliberately dirty, and the pipeline tells you exactly what was
wrong with each bad record instead of silently dropping it.

```
$ make demo

====================================================================
  pipeline run 1  --  SUCCESS
====================================================================
  extracted   565 rows   loaded   545   rejected   20
--------------------------------------------------------------------
  table            in  inserted  updated  rejected
  customers        60        60        0         4
  projects         85        85        0         5
  invoices        400       400        0        11
--------------------------------------------------------------------
  rejections by rule
  customers   duplicate_key             1
  customers   invalid_date              1
  customers   missing_required          2
  projects    date_order                1
  projects    duplicate_key             1
  projects    invalid_status            1
  projects    negative_amount           1
  projects    orphan_customer           1
  invoices    date_order                1
  invoices    duplicate_key             2
  invoices    invalid_date              1
  invoices    invalid_status            1
  invoices    missing_required          1
  invoices    negative_amount           1
  invoices    non_numeric_amount        1
  invoices    orphan_customer           1
  invoices    orphan_project            1
  invoices    overpaid                  1
====================================================================
```

Those 20 rejections are the 20 bad records planted in the sample extracts, and
they are listed in [`data/KNOWN_BAD_RECORDS.txt`](data/KNOWN_BAD_RECORDS.txt).
A test asserts that the count and the set of triggered rules both match, so
the claim above cannot quietly rot.

## Quick start

Requires Docker and Python 3.11+.

```bash
cp .env.example .env     # defaults work as-is for local use
make setup               # create .venv and install dependencies
make up                  # start PostgreSQL on port 5433
make pipeline            # extract -> validate -> transform -> load
make reports             # print every SQL report
make dashboard           # Streamlit dashboard at localhost:8501
make test                # 162 tests
```

Without `make`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
docker compose up -d
.venv/bin/python -m src.pipeline
.venv/bin/python -m src.reports
.venv/bin/python -m pytest
```

`make help` lists the rest (`dry-run`, `reset`, `data`, `site`, `down`, `clean`).

## What it does

**1. Extracts** three CSV files, reading every column as a raw string and
keeping each row's source line number for error reporting.

**2. Transforms** the values into canonical form: whitespace trimmed and
collapsed, ids upper-cased (`  cust-0007 ` → `CUST-0007`), four different date
formats parsed (`2024-03-15`, `03/15/2024`, `15-Mar-2024`, `2024/03/15`), money
strings parsed to `Decimal` (`$1,234.50`, `1,234.50`, the accounting negative
`(500.00)`), statuses and currency codes normalized.

**3. Validates** against ten rules and splits the rows in two. Clean rows go
to the database; rejected rows go to `rejected_records` with the rule they
broke, a readable reason, the source line number, and the original values as
`JSONB`:

| Rule | Example reason stored |
|---|---|
| `missing_required` | `customer_id is required but missing` |
| `invalid_date` | `created_date='2024-13-45' is not a valid date` |
| `non_numeric_amount` | `amount='N/A' is not a valid amount` |
| `negative_amount` | `budget_amount=-45000.00 must not be negative` |
| `date_order` | `due_date 2025-02-20 is before invoice_date 2025-03-20` |
| `overpaid` | `amount_paid=6500.00 exceeds amount=4000.00` |
| `invalid_status` | `status='Pending' is not a valid status (expected one of Paid, Open, Partial, Void)` |
| `orphan_customer` | `customer_id=CUST-9001 does not exist` |
| `orphan_project` | `project_id=PRJ-9999 does not exist` |
| `duplicate_key` | `invoice_id=INV-200031 already seen at source row 32` |

Parents are validated before children, so an invoice is never loaded against
a customer that was itself rejected.

**4. Loads** everything in a single transaction using
`INSERT ... ON CONFLICT (pk) DO UPDATE`, counting inserts and updates
separately.

**5. Records** the run in `pipeline_runs`, per-table statistics in
`load_audit`, and every refused row in `rejected_records`.

## Re-running is safe

The pipeline is idempotent. A second run over the same extracts updates in
place and inserts nothing:

```
 run_id  status  duration_seconds  rows_extracted  rows_loaded  rows_inserted  rows_updated  rows_rejected
      2 success              0.04             565          545              0           545             20
      1 success              0.05             565          545            545             0             20
```

Row counts are unchanged afterwards. This comes from primary keys on the
normalized business keys plus the upsert — not from truncating and reloading,
which would destroy the audit history and break any foreign keys pointing in.

`rows_updated` means *rows that already existed and were refreshed*, whether
or not a column actually changed.

## Reports

Eleven queries in [`sql/reports.sql`](sql/reports.sql), each marked with a
`-- name:` comment so `src/reports.py` can run them individually. Sample
output from the shipped data is in
[`docs/sample_reports.md`](docs/sample_reports.md).

| Report | What it shows | SQL used |
|---|---|---|
| `overdue_invoices` | Unpaid invoices past due, worst first, with balance due | joins, date arithmetic |
| `revenue_by_month` | Monthly invoiced totals, running total, month-over-month change | CTE, `SUM`/`LAG` windows |
| `customer_revenue_rank` | Customers by total invoiced, with share and cumulative share | CTE, `RANK`, windowed `SUM` |
| `customer_balances` | Receivables per customer in aging buckets | CTE, conditional aggregation |
| `ar_aging_summary` | The same receivables as one row per bucket | `CASE` bucketing, nested window aggregate |
| `project_profitability` | Budget vs invoiced vs labor cost, with margin | CTE pre-aggregation, `LEFT JOIN` |
| `projects_over_budget` | Projects whose labor cost passed budget | filtered join |
| `pipeline_run_history` | What each run did and how long it took | audit query |
| `rejection_summary` | Data-quality scorecard for the latest run | CTE, `GROUP BY` |
| `rejected_records_detail` | The refused rows themselves, with reasons | CTE |
| `load_audit_detail` | Per-table load statistics for the latest run | CTE |

```bash
.venv/bin/python -m src.reports --list
.venv/bin/python -m src.reports --report ar_aging_summary
.venv/bin/python -m src.reports --format md > docs/sample_reports.md
```

A sample, from the aging summary:

```
  aging_bucket  open_invoices  balance_due  pct_of_receivables
   0 - current             10   791,359.97                6.70
 1 - 1-30 days              8   396,720.24                3.40
2 - 31-60 days              5   337,245.31                2.90
3 - 61-90 days             14 1,249,711.69               10.60
  4 - 90+ days            123 8,964,330.02               76.40
```

The reports say `total_invoiced`, not `revenue`. Recognized revenue depends on
contract and percent-complete rules that these three tables do not carry, so
labelling an invoice total as revenue would be exactly the sort of quiet error
this pipeline exists to catch.

## Live demo

**<https://sameermankotia.github.io/FlowLedger/>**

GitHub Pages serves static files only, so the Streamlit app itself cannot run
there. What is published is a **static snapshot**: the same reports and the
same chart specifications, rendered to one self-contained HTML page by
[`scripts/build_site.py`](scripts/build_site.py) and committed to `docs/`. The
page says so at the top — it is not querying a live database, and the figures
are from the synthetic extracts in `data/`.

```bash
make site                # rebuild docs/index.html from the current database
```

The charts are the same Altair objects the dashboard uses, serialised to
Vega-Lite and embedded, so the published page and the dashboard cannot drift
apart. Tests in [`tests/test_site.py`](tests/test_site.py) check that every
chart carries its data, that the Vega-Lite version in the specs matches the
pinned CDN build, and that the page leaks no database credentials.

For the real, interactive thing, run it locally:

## Dashboard

```bash
make dashboard           # http://localhost:8501
```

Five tabs — Receivables, Customers, Projects, Data quality, Pipeline — over
stat tiles for invoiced, collected, outstanding, overdue and rejected rows.

Every figure on the page comes from a named query in `sql/reports.sql`, the
same SQL the CLI reports run, so there is one definition of "outstanding" in
the project rather than two.

The charts are deliberate rather than default:

- **Invoiced vs collected by month** — two dollar measures on **one** y-axis.
  Never a dual axis.
- **Receivables by age** — ordered buckets get a single-hue ordinal ramp
  (older is darker) with the values labelled directly on the bars.
- **Project margin** — a polarity question, so a diverging blue/red pair
  around a zero rule; the sign is carried by the side of the baseline too,
  not by colour alone.
- Single-series charts carry no legend; the title names the series.

The palette was checked with a validator rather than eyeballed — worst
adjacent colour-vision ΔE 24.7 on the categorical pair, and the ordinal ramp
is monotone in lightness with its light end clearing 2:1 against the chart
surface. `.streamlit/config.toml` pins the light theme because that is the
surface the palette was validated against. Tests in
[`tests/test_dashboard.py`](tests/test_dashboard.py) assert these properties
on the emitted chart specs, and run the whole page through Streamlit's
`AppTest` to prove it renders.

The dashboard is optional. `streamlit` and `altair` are only needed for it —
the pipeline and the CLI reports do not import them.

## Schema

```
customers  --<  projects  --<  invoices
```

Integrity is enforced in the database, not only in Python:

- Primary keys on the natural business keys, which is what makes the upsert
  idempotent.
- Foreign keys `projects.customer_id`, `invoices.customer_id`, and the
  nullable `invoices.project_id` (not every invoice belongs to a project).
- `CHECK` constraints: `amount >= 0`, `0 <= amount_paid <= amount`,
  `due_date >= invoice_date`, `end_date >= start_date`, and status values
  restricted to the allowed set — so `WHERE status <> 'Void'` cannot miss a
  row spelled `VOID`.
- Indexes on the foreign keys, `invoice_date` and `(status, due_date)`,
  matching how the reports filter and join.

Operational tables: `pipeline_runs`, `load_audit`, `rejected_records`.
Full details in [`sql/schema.sql`](sql/schema.sql) and
[`docs/architecture.md`](docs/architecture.md).

## Tests

```
$ make test
182 passed in 4.27s
```

- [`tests/test_transform.py`](tests/test_transform.py) — 56 tests on the
  field-level parsers: every accepted date format, impossible dates like
  `2024-13-45` and `31/02/2024` rejected rather than coerced, money formats,
  half-up rounding, `Decimal` rather than float, case-insensitive statuses.
- [`tests/test_validation.py`](tests/test_validation.py) — 37 tests, one per
  rule plus the boundary cases that must *not* reject (zero amount, payment
  exactly equal to the amount, due date equal to invoice date, absent optional
  fields), and the cascade from a rejected parent to its children.
- [`tests/test_dashboard.py`](tests/test_dashboard.py) — 37 tests on the
  dashboard: every chart compiles to a valid Vega-Lite spec against real query
  output, the design rules hold in the emitted spec (one shared y-axis, the
  ordinal ramp in order, direct labels, tooltips on every chart), and the full
  page runs under `AppTest` with no exception, with its headline figure checked
  against the database.
- [`tests/test_site.py`](tests/test_site.py) — 11 tests on the published
  snapshot: the template is fully substituted, every chart div has a matching
  spec that carries data, all three Vega scripts are pinned to exact versions
  that match the emitted schema, and the page contains no credentials.
- [`tests/test_pipeline.py`](tests/test_pipeline.py) — 40 tests against a real
  PostgreSQL instance: the full run, normalization on the way in, audit and
  rejection rows, idempotency over three runs, every database constraint
  actually rejecting bad input, a simulated mid-load failure rolling back
  while still recording the failed run, and each report's numbers checked
  against hand-computed totals.

The transform and validation tests need no database. The pipeline tests skip
cleanly if PostgreSQL is not running, so `pytest` is useful before
`docker compose up`.

## Layout

```
├── data/                     synthetic extracts + the list of planted bad records
├── scripts/
│   ├── generate_data.py      regenerates the extracts (seeded, date-anchored)
│   └── build_site.py         renders the static GitHub Pages snapshot
├── src/
│   ├── config.py             settings and the SQLAlchemy engine
│   ├── extract.py            read CSVs as raw strings
│   ├── transform.py          normalize to canonical typed values
│   ├── validate.py           the ten rules; clean rows vs rejections
│   ├── load.py               transactional upserts, audit and rejection writes
│   ├── pipeline.py           orchestration + CLI
│   ├── reports.py            run the named queries in sql/reports.sql
│   ├── theme.py              validated chart palette + Altair defaults
│   └── dashboard.py          Streamlit dashboard (optional)
├── sql/
│   ├── schema.sql            tables, constraints, indexes (safe to re-run)
│   └── reports.sql           the eleven reports
├── tests/
├── docs/                     also the GitHub Pages root
│   ├── index.html            generated static snapshot (make site)
│   ├── architecture.md       data flow, design decisions, schema
│   └── sample_reports.md     generated output from the shipped data
├── .github/workflows/        CI: pipeline, idempotency check, tests, site build
├── docker-compose.yml
├── Makefile
└── requirements.txt
```

## Sample data

`data/` holds 565 synthetic rows from kaggle: 64 customers, 90 projects, 411 invoices, of
which 20 are deliberately bad. The data is generated by
`scripts/generate_data.py` from a fixed seed, so it is reproducible, and dates
are anchored on the generation date so the overdue and aging reports stay
meaningful as the repository ages:

```bash
.venv/bin/python scripts/generate_data.py                        # anchor on today
.venv/bin/python scripts/generate_data.py --anchor-date 2026-01-01
```

No real customer data is used anywhere in this repository.

## Technologies

Python, Pandas, PostgreSQL, SQL, SQLAlchemy, pytest, Docker Compose.

## Configuration

Settings come from `.env` (see `.env.example`); `.env` is gitignored. The
default port is **5433** rather than 5432, so this does not collide with a
PostgreSQL already running locally.

| Variable | Default |
|---|---|
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5433` |
| `POSTGRES_DB` | `erp` |
| `POSTGRES_USER` | `erp` |
| `POSTGRES_PASSWORD` | `erp_local_password` |

## CLI reference

```bash
python -m src.pipeline                      # load data/ into the database
python -m src.pipeline --source-dir other/  # load a different extract folder
python -m src.pipeline --dry-run            # validate only; write nothing
python -m src.pipeline --quiet              # warnings only

python -m src.reports                       # every report
python -m src.reports --list
python -m src.reports --report revenue_by_month --report overdue_invoices
python -m src.reports --format md           # markdown tables
python -m src.reports --format csv --report overdue_invoices > overdue.csv

streamlit run src/dashboard.py              # dashboard on :8501
python scripts/build_site.py                # rebuild docs/index.html

python scripts/generate_data.py [--anchor-date YYYY-MM-DD]
```
