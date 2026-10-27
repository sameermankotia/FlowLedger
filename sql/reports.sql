-- ===========================================================================
-- Business reports over the integrated ERP data.
--
-- Each block is preceded by "-- name: <key>" so src/reports.py can run them
-- individually:  python -m src.reports --report revenue_by_month
--
-- A note on terminology: "invoiced" below means the sum of invoice amounts,
-- which is not the same as recognized revenue. Real revenue recognition
-- depends on contract terms and percent-complete rules that live outside
-- these three tables.
-- ===========================================================================


-- name: overdue_invoices
-- Unpaid or part-paid invoices past their due date, worst first.
-- Shows the open balance rather than the invoice face value.
SELECT
    i.invoice_id,
    c.customer_name,
    p.project_name,
    i.invoice_date,
    i.due_date,
    i.amount,
    i.amount_paid,
    i.amount - i.amount_paid              AS balance_due,
    CURRENT_DATE - i.due_date             AS days_overdue
FROM invoices AS i
JOIN customers AS c
    ON c.customer_id = i.customer_id
LEFT JOIN projects AS p
    ON p.project_id = i.project_id
WHERE i.due_date < CURRENT_DATE
  AND i.status NOT IN ('Paid', 'Void')
ORDER BY days_overdue DESC, balance_due DESC
LIMIT 20;


-- name: revenue_by_month
-- Monthly invoiced totals with a running total and month-over-month change.
-- Window functions run over the aggregated months, so the growth figure
-- compares each month with the previous one in a single pass.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::date AS month,
        COUNT(*)                                AS invoice_count,
        SUM(amount)                             AS total_invoiced,
        SUM(amount_paid)                        AS total_collected
    FROM invoices
    WHERE status <> 'Void'
    GROUP BY DATE_TRUNC('month', invoice_date)
)
SELECT
    month,
    invoice_count,
    total_invoiced,
    total_collected,
    SUM(total_invoiced) OVER (ORDER BY month)       AS running_total_invoiced,
    total_invoiced - LAG(total_invoiced) OVER (ORDER BY month)
                                                    AS change_vs_prior_month,
    ROUND(
        100.0 * (total_invoiced - LAG(total_invoiced) OVER (ORDER BY month))
        / NULLIF(LAG(total_invoiced) OVER (ORDER BY month), 0),
        1
    )                                               AS pct_change_vs_prior_month
FROM monthly
ORDER BY month;


-- name: customer_revenue_rank
-- Customers ranked by total invoiced, with each one's share of the book and
-- a cumulative share so you can see concentration risk at a glance.
WITH customer_revenue AS (
    SELECT
        c.customer_id,
        c.customer_name,
        c.industry,
        COUNT(i.invoice_id)                     AS invoice_count,
        SUM(i.amount)                           AS total_invoiced,
        SUM(i.amount - i.amount_paid)           AS balance_outstanding
    FROM customers AS c
    JOIN invoices AS i
        ON i.customer_id = c.customer_id
    WHERE i.status <> 'Void'
    GROUP BY c.customer_id, c.customer_name, c.industry
)
SELECT
    customer_id,
    customer_name,
    industry,
    invoice_count,
    total_invoiced,
    balance_outstanding,
    RANK() OVER (ORDER BY total_invoiced DESC)  AS revenue_rank,
    ROUND(100.0 * total_invoiced / SUM(total_invoiced) OVER (), 2)
                                                AS pct_of_total,
    ROUND(
        100.0 * SUM(total_invoiced) OVER (ORDER BY total_invoiced DESC
                                          ROWS UNBOUNDED PRECEDING)
        / SUM(total_invoiced) OVER (),
        2
    )                                           AS cumulative_pct
FROM customer_revenue
ORDER BY revenue_rank
LIMIT 20;


-- name: customer_balances
-- Accounts-receivable position per customer, bucketed by age of the balance.
-- Customers with nothing outstanding are filtered out at the end.
WITH open_items AS (
    SELECT
        i.customer_id,
        i.amount - i.amount_paid                AS balance_due,
        CURRENT_DATE - i.due_date               AS days_overdue
    FROM invoices AS i
    WHERE i.status NOT IN ('Paid', 'Void')
      AND i.amount > i.amount_paid
)
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(o.customer_id)                        AS open_invoices,
    COALESCE(SUM(o.balance_due), 0)             AS total_outstanding,
    COALESCE(SUM(CASE WHEN o.days_overdue <= 0                        THEN o.balance_due END), 0) AS current_not_yet_due,
    COALESCE(SUM(CASE WHEN o.days_overdue BETWEEN 1  AND 30           THEN o.balance_due END), 0) AS overdue_1_30,
    COALESCE(SUM(CASE WHEN o.days_overdue BETWEEN 31 AND 60           THEN o.balance_due END), 0) AS overdue_31_60,
    COALESCE(SUM(CASE WHEN o.days_overdue BETWEEN 61 AND 90           THEN o.balance_due END), 0) AS overdue_61_90,
    COALESCE(SUM(CASE WHEN o.days_overdue > 90                        THEN o.balance_due END), 0) AS overdue_90_plus
FROM customers AS c
LEFT JOIN open_items AS o
    ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name
HAVING COALESCE(SUM(o.balance_due), 0) > 0
ORDER BY total_outstanding DESC
LIMIT 20;


-- name: ar_aging_summary
-- The same receivables rolled up to one row per bucket, for a summary tile.
WITH open_items AS (
    SELECT
        i.amount - i.amount_paid    AS balance_due,
        CASE
            WHEN i.due_date >= CURRENT_DATE                        THEN '0 - current'
            WHEN CURRENT_DATE - i.due_date BETWEEN 1  AND 30       THEN '1 - 1-30 days'
            WHEN CURRENT_DATE - i.due_date BETWEEN 31 AND 60       THEN '2 - 31-60 days'
            WHEN CURRENT_DATE - i.due_date BETWEEN 61 AND 90       THEN '3 - 61-90 days'
            ELSE                                                        '4 - 90+ days'
        END                         AS aging_bucket
    FROM invoices AS i
    WHERE i.status NOT IN ('Paid', 'Void')
      AND i.amount > i.amount_paid
)
SELECT
    aging_bucket,
    COUNT(*)                                            AS open_invoices,
    SUM(balance_due)                                    AS balance_due,
    ROUND(100.0 * SUM(balance_due) / SUM(SUM(balance_due)) OVER (), 1)
                                                        AS pct_of_receivables
FROM open_items
GROUP BY aging_bucket
ORDER BY aging_bucket;


-- name: project_profitability
-- Project-level financials: what was budgeted, what has been invoiced
-- against the project, what labor it consumed, and the resulting margin.
-- Invoices are aggregated in a CTE first so the per-project join stays 1:1
-- and the labor_cost column is not multiplied by the invoice count.
WITH project_invoices AS (
    SELECT
        project_id,
        COUNT(*)                        AS invoice_count,
        SUM(amount)                     AS total_invoiced,
        SUM(amount_paid)                AS total_collected
    FROM invoices
    WHERE status <> 'Void'
      AND project_id IS NOT NULL
    GROUP BY project_id
)
SELECT
    p.project_id,
    p.project_name,
    c.customer_name,
    p.status,
    p.budget_amount,
    COALESCE(pi.total_invoiced, 0)                      AS total_invoiced,
    COALESCE(pi.total_collected, 0)                     AS total_collected,
    p.labor_cost,
    COALESCE(pi.total_invoiced, 0) - p.labor_cost       AS gross_margin,
    ROUND(
        100.0 * (COALESCE(pi.total_invoiced, 0) - p.labor_cost)
        / NULLIF(COALESCE(pi.total_invoiced, 0), 0),
        1
    )                                                   AS margin_pct,
    ROUND(
        100.0 * COALESCE(pi.total_invoiced, 0) / NULLIF(p.budget_amount, 0),
        1
    )                                                   AS pct_of_budget_invoiced
FROM projects AS p
JOIN customers AS c
    ON c.customer_id = p.customer_id
LEFT JOIN project_invoices AS pi
    ON pi.project_id = p.project_id
ORDER BY gross_margin DESC
LIMIT 20;


-- name: projects_over_budget
-- Projects whose labor cost has passed the budget, and by how much.
SELECT
    p.project_id,
    p.project_name,
    c.customer_name,
    p.status,
    p.budget_amount,
    p.labor_cost,
    p.labor_cost - p.budget_amount                              AS overrun_amount,
    ROUND(100.0 * p.labor_cost / NULLIF(p.budget_amount, 0), 1)  AS pct_of_budget_spent
FROM projects AS p
JOIN customers AS c
    ON c.customer_id = p.customer_id
WHERE p.labor_cost > p.budget_amount
ORDER BY overrun_amount DESC;


-- name: pipeline_run_history
-- Operational view of the loader: what each run did and how long it took.
SELECT
    r.run_id,
    r.status,
    r.started_at,
    ROUND(EXTRACT(EPOCH FROM (r.finished_at - r.started_at))::numeric, 2)
                                        AS duration_seconds,
    r.rows_extracted,
    r.rows_loaded,
    r.rows_inserted,
    r.rows_updated,
    r.rows_rejected,
    r.error_message
FROM pipeline_runs AS r
ORDER BY r.run_id DESC
LIMIT 10;


-- name: rejection_summary
-- Data-quality scorecard for the most recent run: which rule fired, how
-- often, and one example key per rule to start troubleshooting from.
WITH latest AS (
    SELECT MAX(run_id) AS run_id FROM pipeline_runs
)
SELECT
    rr.source_table,
    rr.rule,
    COUNT(*)                                        AS rejected_rows,
    MIN(rr.natural_key)                             AS example_key,
    MIN(rr.source_row)                              AS first_source_row,
    MIN(rr.reason)                                  AS example_reason
FROM rejected_records AS rr
JOIN latest
    ON latest.run_id = rr.run_id
GROUP BY rr.source_table, rr.rule
ORDER BY rr.source_table, rejected_rows DESC, rr.rule;


-- name: rejected_records_detail
-- The rejected rows themselves, with the original values, so a data owner
-- can see exactly what to fix in the source system.
WITH latest AS (
    SELECT MAX(run_id) AS run_id FROM pipeline_runs
)
SELECT
    rr.source_table,
    rr.source_row,
    rr.natural_key,
    rr.rule,
    rr.reason
FROM rejected_records AS rr
JOIN latest
    ON latest.run_id = rr.run_id
ORDER BY rr.source_table, rr.source_row;


-- name: load_audit_detail
-- Per-table load statistics for the most recent run.
WITH latest AS (
    SELECT MAX(run_id) AS run_id FROM pipeline_runs
)
SELECT
    la.target_table,
    la.rows_in,
    la.rows_inserted,
    la.rows_updated,
    la.rows_rejected,
    la.duration_ms
FROM load_audit AS la
JOIN latest
    ON latest.run_id = la.run_id
ORDER BY la.audit_id;
