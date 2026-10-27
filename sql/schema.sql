-- ERP Data Integration -- target schema.
-- Idempotent: safe to run on every pipeline start.

CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    customer_name   TEXT        NOT NULL,
    contact_email   TEXT,
    contact_phone   TEXT,
    industry        TEXT,
    country         TEXT,
    created_date    DATE,
    source_system   TEXT        NOT NULL DEFAULT 'CRM',
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    project_id      TEXT PRIMARY KEY,
    customer_id     TEXT        NOT NULL REFERENCES customers (customer_id),
    project_name    TEXT        NOT NULL,
    project_manager TEXT,
    status          TEXT        NOT NULL,
    start_date      DATE,
    end_date        DATE,
    budget_amount   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    labor_cost      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    source_system   TEXT        NOT NULL DEFAULT 'ERP',
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT projects_status_chk
        CHECK (status IN ('Active', 'Completed', 'On Hold', 'Cancelled')),
    CONSTRAINT projects_budget_nonneg_chk CHECK (budget_amount >= 0),
    CONSTRAINT projects_dates_chk
        CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id      TEXT PRIMARY KEY,
    customer_id     TEXT        NOT NULL REFERENCES customers (customer_id),
    project_id      TEXT        REFERENCES projects (project_id),
    invoice_date    DATE        NOT NULL,
    due_date        DATE        NOT NULL,
    amount          NUMERIC(14, 2) NOT NULL,
    amount_paid     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    currency        TEXT        NOT NULL DEFAULT 'USD',
    status          TEXT        NOT NULL,
    source_system   TEXT        NOT NULL DEFAULT 'ERP',
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT invoices_status_chk
        CHECK (status IN ('Paid', 'Open', 'Partial', 'Void')),
    CONSTRAINT invoices_amount_nonneg_chk CHECK (amount >= 0),
    CONSTRAINT invoices_paid_bounds_chk
        CHECK (amount_paid >= 0 AND amount_paid <= amount),
    CONSTRAINT invoices_due_after_invoice_chk CHECK (due_date >= invoice_date)
);

CREATE INDEX IF NOT EXISTS idx_projects_customer      ON projects (customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_customer      ON invoices (customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_project       ON invoices (project_id);
CREATE INDEX IF NOT EXISTS idx_invoices_invoice_date  ON invoices (invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_status_due    ON invoices (status, due_date);

-- ---------------------------------------------------------------------------
-- Operational tables: one row per pipeline run, one row per rejected record.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id            BIGSERIAL PRIMARY KEY,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    status            TEXT        NOT NULL DEFAULT 'running',
    source_dir        TEXT,
    rows_extracted    INTEGER     NOT NULL DEFAULT 0,
    rows_loaded       INTEGER     NOT NULL DEFAULT 0,
    rows_inserted     INTEGER     NOT NULL DEFAULT 0,
    rows_updated      INTEGER     NOT NULL DEFAULT 0,
    rows_rejected     INTEGER     NOT NULL DEFAULT 0,
    error_message     TEXT,
    CONSTRAINT pipeline_runs_status_chk
        CHECK (status IN ('running', 'success', 'failed'))
);

CREATE TABLE IF NOT EXISTS rejected_records (
    rejection_id    BIGSERIAL PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES pipeline_runs (run_id) ON DELETE CASCADE,
    source_table    TEXT        NOT NULL,
    source_row      INTEGER,
    natural_key     TEXT,
    rule            TEXT        NOT NULL,
    reason          TEXT        NOT NULL,
    raw_record      JSONB       NOT NULL,
    rejected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rejected_run   ON rejected_records (run_id);
CREATE INDEX IF NOT EXISTS idx_rejected_rule  ON rejected_records (source_table, rule);

CREATE TABLE IF NOT EXISTS load_audit (
    audit_id        BIGSERIAL PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES pipeline_runs (run_id) ON DELETE CASCADE,
    target_table    TEXT        NOT NULL,
    rows_in         INTEGER     NOT NULL DEFAULT 0,
    rows_inserted   INTEGER     NOT NULL DEFAULT 0,
    rows_updated    INTEGER     NOT NULL DEFAULT 0,
    rows_rejected   INTEGER     NOT NULL DEFAULT 0,
    duration_ms     INTEGER     NOT NULL DEFAULT 0,
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_load_audit_run ON load_audit (run_id);
