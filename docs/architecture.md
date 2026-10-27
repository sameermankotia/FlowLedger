# FlowLedger -- architecture

## Problem

Customer data lives in one system (a CRM) and project and invoice data in
another (an ERP). Neither agrees with the other about how to spell a customer
id, format a date, or capitalize a status. Reporting needs a single place
where the three datasets can be joined and trusted.

This project is that single place, in miniature: a Python ETL pipeline that
reads flat-file extracts from both systems, reconciles them, loads them into
PostgreSQL under real constraints, and exposes the result through SQL reports.

## Data flow

```
   CRM extract              ERP extracts
   customers.csv     projects.csv  invoices.csv
        |                  |            |
        +---------+--------+------------+
                  |
          +-------v--------+   src/extract.py
          |    EXTRACT     |   read as raw strings, no coercion;
          |                |   verify expected columns; keep source
          +-------+--------+   line numbers for error reporting
                  |
          +-------v--------+   src/transform.py
          |   TRANSFORM    |   trim and collapse whitespace
          |                |   upper-case ids    cust-0007 -> CUST-0007
          |                |   parse 4 date formats -> date
          |                |   parse $1,234.50 / (500.00) -> Decimal
          |                |   canonicalize status and currency
          +-------+--------+   unparseable value -> None (not an exception)
                  |
          +-------v--------+   src/validate.py
          |    VALIDATE    |   10 rules; parents before children
          |                |
          |  clean rows ---+--------------------+
          |  bad rows      |                    |
          +-------+--------+                    |
                  |                             |
   rejected with rule + reason                  | upsert
                  |                             |
          +-------v-----------------------------v--------+   src/load.py
          |                   LOAD                       |   one transaction
          |  ON CONFLICT (pk) DO UPDATE                  |
          +-------+--------------------------------------+
                  |
   +--------------v---------------------------------------------+
   |                        PostgreSQL                          |
   |                                                            |
   |  customers --< projects --< invoices    (FKs + CHECKs)      |
   |                                                            |
   |  pipeline_runs      one row per run, with counts + status   |
   |  rejected_records   one row per bad record, with raw JSON   |
   |  load_audit         per-table insert/update/timing          |
   +--------------+---------------------------------------------+
                  |
          +-------v--------+   sql/reports.sql + src/reports.py
          |    REPORTS     |   revenue, AR aging, profitability,
          |                |   overdue, concentration, data quality
          +----------------+
```

## Why the stages are separate

**Extract reads strings only.** If extraction parsed dates, a single bad date
in row 300 would raise and the run would die with a stack trace instead of a
report. Reading everything as text means a malformed value becomes a
*rejected record with a reason*, which is what a person troubleshooting the
source system actually needs.

**Transform never raises.** Every parser returns `None` on failure. The typed
column sits beside the raw one, so validation can distinguish *absent at
source* (`missing_required`) from *present but malformed* (`invalid_date`,
`non_numeric_amount`). Those two cases have different owners and different
fixes.

**Validate decides, load executes.** All the business judgment is in one
module with no database dependency, which is why most of the test suite needs
no PostgreSQL running.

## Validation rules

Rules are applied per table, parents first. Projects are checked against the
customers that *survived* validation, and invoices against the surviving
customers and projects, so a child row is never loaded against a parent that
was itself rejected.

| Rule | Meaning |
|---|---|
| `missing_required` | A required field is empty, or blank after trimming |
| `invalid_date` | Present but not parseable in any accepted format |
| `non_numeric_amount` | Present but not parseable as money |
| `negative_amount` | An amount that must not be negative, is |
| `date_order` | `due_date < invoice_date`, or `end_date < start_date` |
| `overpaid` | `amount_paid > amount` |
| `invalid_status` | Status outside the allowed set for that table |
| `orphan_customer` | References a customer that does not exist |
| `orphan_project` | References a project that does not exist |
| `duplicate_key` | The natural key was already seen; the first row wins |

Each rejected row produces exactly **one** rejection, so a run's rejection
count equals its rejected-row count. When a row breaks several rules, `rule`
holds the first one in the table's rule order and `reason` lists all of them.

A rejected row does not claim its key: if the first `INV-300` is rejected for
a bad status, a later valid `INV-300` is loaded rather than reported as a
duplicate.

## Idempotency

Re-running the pipeline over unchanged extracts must not change the database.
Three things combine to guarantee it:

1. **Primary keys** on the natural business keys (`customer_id`,
   `project_id`, `invoice_id`), normalized so the CRM's `cust-0007` and the
   ERP's `CUST-0007` collide on purpose.
2. **`INSERT ... ON CONFLICT (pk) DO UPDATE`**, so a second run refreshes the
   row rather than inserting beside it.
3. **One transaction** for all three tables plus the rejection and audit
   rows, so a failure part-way through leaves nothing behind.

Insert and update counts are split by reading the existing keys inside the
same transaction before writing. `rows_updated` therefore means *rows that
already existed and were refreshed*, whether or not any column actually
changed.

`ingested_at` is set once; `updated_at` moves on every upsert. The pair
answers "when did we first see this record, and when did we last confirm it".

## Audit trail

`pipeline_runs` is opened in its own committed transaction *before* the load
begins. That is deliberate: if the load then fails and rolls back, the failed
run is still on record with its error message. The alternative — one
transaction for everything — would roll back the evidence along with the
data.

Three tables answer three different questions:

- `pipeline_runs` — did the run succeed, when, how long, how many rows?
- `load_audit` — which table absorbed the time, and what was inserted vs updated?
- `rejected_records` — exactly which source rows were refused, why, and what
  did they contain? The raw record is kept as `JSONB`, so a data owner can be
  shown their own values back.

## Schema

```
customers                      projects                      invoices
---------                      --------                      --------
customer_id   PK  <--------+   project_id    PK  <-------+    invoice_id   PK
customer_name              |   customer_id   FK ---------+--- customer_id  FK
contact_email              +-- project_name              +--- project_id   FK (nullable)
contact_phone                  project_manager                invoice_date
industry                       status                         due_date
country                        start_date                     amount
created_date                   end_date                       amount_paid
source_system                  budget_amount                  currency
ingested_at                    labor_cost                     status
updated_at                     source_system                  source_system
                               ingested_at                    ingested_at
                               updated_at                     updated_at
```

Constraints that matter for reporting correctness:

- `invoices.amount >= 0` and `0 <= amount_paid <= amount` — so
  `amount - amount_paid` is always a sane balance.
- `invoices.due_date >= invoice_date` — so `CURRENT_DATE - due_date` is a
  meaningful aging figure.
- Status `CHECK`s on both tables — so `WHERE status <> 'Void'` cannot silently
  miss a row spelled `VOID` or `Voided`.
- Indexes on the foreign keys, `invoice_date`, and `(status, due_date)`,
  matching how the reports filter and join.

`project_id` on invoices is nullable by design: not every invoice belongs to a
project. The profitability report uses a `LEFT JOIN` accordingly.

## A note on "revenue"

The reports sum invoice amounts and label the result `total_invoiced`, not
`revenue`. In a real accounting system recognized revenue depends on contract
terms and percent-complete rules that these three tables do not carry.
Calling an invoice total "revenue" would be the kind of quiet error that
reporting pipelines are supposed to prevent.

## Extending it

The shape generalizes past CSV files:

- **A different source** — add a reader to `src/extract.py` that returns a
  DataFrame of strings with a `_source_row` column. A database or API source
  changes nothing downstream.
- **A new rule** — add a `(rule, message)` tuple to the relevant function in
  `src/validate.py`. The rejection plumbing, counts and reporting pick it up
  automatically.
- **Incremental loads** — the upsert is already key-based, so filtering the
  extract by a watermark is the only change needed.
