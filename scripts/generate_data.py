"""Generate the synthetic CRM/ERP extracts in data/.

The output is deliberately messy: mixed date formats, stray whitespace,
inconsistent casing and currency strings, plus a fixed set of genuinely bad
records (listed in BAD_RECORD_NOTES) that the pipeline is expected to reject.

Dates are generated relative to an anchor date (today by default) so the
aging and overdue reports stay meaningful as the repository gets older. Pass
``--anchor-date YYYY-MM-DD`` to reproduce an earlier extract exactly.

Run:  python scripts/generate_data.py
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 20251027
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

N_CUSTOMERS = 60
N_PROJECTS = 85
N_INVOICES = 400

INDUSTRIES = [
    "Utilities", "Manufacturing", "Engineering Services", "Oil & Gas",
    "Transportation", "Public Sector", "Mining", "Renewables",
]
COUNTRIES = ["USA", "Canada", "Mexico", "Germany", "Australia", "Brazil"]
FIRST = [
    "Ada", "Grace", "Linus", "Tariq", "Mei", "Olu", "Ines", "Rafael",
    "Noor", "Hank", "Priya", "Sven", "Lucia", "Omar", "Dana", "Kofi",
]
LAST = [
    "Lovelace", "Hopper", "Nakamura", "Okafor", "Petrov", "Alvarez",
    "Haddad", "Schmidt", "Fontaine", "Kowalski", "Ibrahim", "Lindqvist",
]
ORG_HEAD = [
    "Cascade", "Ironwood", "Northline", "Summit", "Blue Ridge", "Meridian",
    "Granite", "Lakeshore", "Redstone", "Westfield", "Harbor", "Clearwater",
    "Copperline", "Timberlake", "Stonebridge", "Fairmont", "Birchwood",
    "Silverton", "Oakhurst", "Riverbend",
]
ORG_TAIL = [
    "Power", "Energy", "Industrial", "Utilities", "Engineering", "Systems",
    "Resources", "Grid Services", "Infrastructure", "Transmission",
]
ORG_SUFFIX = ["Inc.", "LLC", "Corp.", "Co-op", "Group", "Partners"]
PROJECT_KIND = [
    "Substation Upgrade", "SCADA Rollout", "Relay Retrofit", "Feeder Automation",
    "Protection Study", "Fiber Backbone", "Load Flow Analysis", "Breaker Replacement",
    "Control House Build", "Arc Flash Assessment", "Metering Rollout", "Grid Hardening",
]
PM_POOL = [f"{f} {l}" for f in FIRST for l in LAST]

# Date formats the two source systems disagree on.
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"]

BAD_RECORD_NOTES = """\
Deliberately bad records planted in the extracts
================================================
customers.csv
  - CUST-0007 appears twice with conflicting names   -> duplicate_key
  - one row has a blank customer_id                  -> missing_required
  - one row has a blank customer_name                -> missing_required
  - one row has created_date '2024-13-45'            -> invalid_date
projects.csv
  - PRJ-1004 appears twice                           -> duplicate_key
  - one project references CUST-9999 (nonexistent)   -> orphan_customer
  - one project has budget_amount -45000             -> negative_amount
  - one project has end_date before start_date       -> date_order
  - one project has status 'Archived'                -> invalid_status
invoices.csv
  - INV-200031 appears twice (identical)             -> duplicate_key
  - INV-200077 appears twice with different amounts  -> duplicate_key
  - one invoice has a blank customer_id              -> missing_required
  - one invoice references CUST-9001 (nonexistent)   -> orphan_customer
  - one invoice has amount -1250.00                  -> negative_amount
  - one invoice has amount 'N/A'                     -> non_numeric_amount
  - one invoice has invoice_date '31/02/2024'        -> invalid_date
  - one invoice has due_date before invoice_date      -> date_order
  - one invoice has amount_paid greater than amount  -> overpaid
  - one invoice has status 'Pending'                 -> invalid_status
  - one invoice references PRJ-9999 (nonexistent)    -> orphan_project
"""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchor-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="date the extract is generated relative to (default: today)",
    )
    args = parser.parse_args(argv)
    anchor: date = args.anchor_date

    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    def fmt_date(d: date) -> str:
        """Render a date in one of the source systems' formats."""
        return d.strftime(rng.choice(DATE_FORMATS))

    def maybe_pad(value: str) -> str:
        """Occasionally add the stray whitespace real extracts come with."""
        return f"  {value} " if rng.random() < 0.12 else value

    def money(value: float) -> str:
        """Amounts arrive as plain numbers, with commas, or with a $ sign."""
        roll = rng.random()
        if roll < 0.15:
            return f"${value:,.2f}"
        if roll < 0.30:
            return f"{value:,.2f}"
        return f"{value:.2f}"

    # ------------------------------------------------------------------ customers
    customers: list[dict[str, str]] = []
    used_names: set[str] = set()
    for i in range(1, N_CUSTOMERS + 1):
        while True:
            name = (
                f"{rng.choice(ORG_HEAD)} {rng.choice(ORG_TAIL)} "
                f"{rng.choice(ORG_SUFFIX)}"
            )
            if name not in used_names:
                used_names.add(name)
                break
        cid = f"CUST-{i:04d}"
        contact = f"{rng.choice(FIRST)}.{rng.choice(LAST)}".lower()
        domain = name.split()[0].lower().replace("-", "")
        created = anchor - timedelta(days=rng.randint(400, 2600))
        customers.append(
            {
                "customer_id": maybe_pad(cid.lower() if rng.random() < 0.18 else cid),
                "customer_name": maybe_pad(name),
                "contact_email": f"{contact}@{domain}.example.com",
                "contact_phone": f"({rng.randint(200, 989)}) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
                "industry": rng.choice(INDUSTRIES),
                "country": rng.choice(COUNTRIES),
                "created_date": fmt_date(created),
            }
        )

    valid_customer_ids = [f"CUST-{i:04d}" for i in range(1, N_CUSTOMERS + 1)]

    # Planted customer problems.
    dup = dict(customers[6])                       # CUST-0007
    dup["customer_name"] = "Cascade Power Incorporated"
    customers.append(dup)
    customers.append(
        {
            "customer_id": "",
            "customer_name": "Unknown Holdings LLC",
            "contact_email": "ops@unknown.example.com",
            "contact_phone": "(555) 010-2000",
            "industry": "Manufacturing",
            "country": "USA",
            "created_date": "2023-04-02",
        }
    )
    customers.append(
        {
            "customer_id": "CUST-0901",
            "customer_name": "   ",
            "contact_email": "billing@nameless.example.com",
            "contact_phone": "(555) 010-2001",
            "industry": "Utilities",
            "country": "USA",
            "created_date": "2022-09-19",
        }
    )
    customers.append(
        {
            "customer_id": "CUST-0902",
            "customer_name": "Baddate Engineering Group",
            "contact_email": "ap@baddate.example.com",
            "contact_phone": "(555) 010-2002",
            "industry": "Engineering Services",
            "country": "Canada",
            "created_date": "2024-13-45",
        }
    )

    # ------------------------------------------------------------------- projects
    projects: list[dict[str, str]] = []
    for i in range(N_PROJECTS):
        pid = f"PRJ-{1001 + i}"
        cid = rng.choice(valid_customer_ids)
        start = anchor - timedelta(days=rng.randint(90, 1000))
        length = rng.randint(45, 540)
        status = rng.choices(
            ["Active", "Completed", "On Hold", "Cancelled"],
            weights=[45, 40, 10, 5],
        )[0]
        end = start + timedelta(days=length)
        budget = round(rng.uniform(25_000, 1_400_000), 2)
        # Most projects run under budget; a few overrun.
        cost_ratio = rng.uniform(0.45, 1.25) if rng.random() < 0.25 else rng.uniform(0.35, 0.92)
        projects.append(
            {
                "project_id": maybe_pad(pid),
                "customer_id": maybe_pad(cid.lower() if rng.random() < 0.15 else cid),
                "project_name": f"{rng.choice(ORG_HEAD)} {rng.choice(PROJECT_KIND)}",
                "project_manager": rng.choice(PM_POOL),
                "status": rng.choice([status, status.upper(), status.lower()]),
                "start_date": fmt_date(start),
                "end_date": fmt_date(end) if status != "Active" else "",
                "budget_amount": money(budget),
                "labor_cost": money(round(budget * cost_ratio, 2)),
            }
        )

    valid_project_ids = [f"PRJ-{1001 + i}" for i in range(N_PROJECTS)]

    # Planted project problems.
    projects.append(dict(projects[3]))             # duplicate PRJ-1004
    projects.append(
        {
            "project_id": "PRJ-2001",
            "customer_id": "CUST-9999",
            "project_name": "Orphan Relay Retrofit",
            "project_manager": "Dana Petrov",
            "status": "Active",
            "start_date": "2024-02-01",
            "end_date": "",
            "budget_amount": "180000.00",
            "labor_cost": "92000.00",
        }
    )
    projects.append(
        {
            "project_id": "PRJ-2002",
            "customer_id": "CUST-0012",
            "project_name": "Negative Budget Study",
            "project_manager": "Omar Haddad",
            "status": "On Hold",
            "start_date": "2024-03-11",
            "end_date": "",
            "budget_amount": "-45000.00",
            "labor_cost": "12000.00",
        }
    )
    projects.append(
        {
            "project_id": "PRJ-2003",
            "customer_id": "CUST-0019",
            "project_name": "Backwards Schedule Upgrade",
            "project_manager": "Mei Nakamura",
            "status": "Completed",
            "start_date": "2024-08-01",
            "end_date": "2024-03-01",
            "budget_amount": "310000.00",
            "labor_cost": "298000.00",
        }
    )
    projects.append(
        {
            "project_id": "PRJ-2004",
            "customer_id": "CUST-0025",
            "project_name": "Legacy Metering Rollout",
            "project_manager": "Sven Kowalski",
            "status": "Archived",
            "start_date": "2023-05-02",
            "end_date": "2024-01-30",
            "budget_amount": "75000.00",
            "labor_cost": "61000.00",
        }
    )

    # ------------------------------------------------------------------- invoices
    project_customer = {
        p["project_id"].strip().upper(): p["customer_id"].strip().upper()
        for p in projects[:N_PROJECTS]
    }

    invoices: list[dict[str, str]] = []
    for i in range(N_INVOICES):
        inv_id = f"INV-{200001 + i}"
        pid = rng.choice(valid_project_ids)
        cid = project_customer[pid]
        inv_date = anchor - timedelta(days=rng.randint(0, 660))
        terms = rng.choice([15, 30, 30, 45, 60])
        amount = round(rng.uniform(1_200, 180_000), 2)
        roll = rng.random()
        if roll < 0.52:
            status, paid = "Paid", amount
        elif roll < 0.80:
            status, paid = "Open", 0.0
        elif roll < 0.95:
            status, paid = "Partial", round(amount * rng.uniform(0.1, 0.8), 2)
        else:
            status, paid = "Void", 0.0
        invoices.append(
            {
                "invoice_id": maybe_pad(inv_id),
                "customer_id": maybe_pad(cid.lower() if rng.random() < 0.15 else cid),
                "project_id": pid,
                "invoice_date": fmt_date(inv_date),
                "due_date": fmt_date(inv_date + timedelta(days=terms)),
                "amount": money(amount),
                "amount_paid": money(paid),
                "currency": rng.choice(["USD", "usd", "USD", "USD"]),
                "status": rng.choice([status, status.upper(), status.lower()]),
            }
        )

    def invoice_row(**overrides: str) -> dict[str, str]:
        row = {
            "invoice_id": "INV-900001",
            "customer_id": "CUST-0003",
            "project_id": "PRJ-1005",
            "invoice_date": "2025-01-15",
            "due_date": "2025-02-14",
            "amount": "5000.00",
            "amount_paid": "0.00",
            "currency": "USD",
            "status": "Open",
        }
        row.update(overrides)
        return row

    # Planted invoice problems.
    invoices.append(dict(invoices[30]))            # identical duplicate INV-200031
    conflicting = dict(invoices[76])               # INV-200077 with a different amount
    conflicting["amount"] = "99999.00"
    conflicting["status"] = "Open"
    conflicting["amount_paid"] = "0.00"
    invoices.append(conflicting)
    invoices.extend(
        [
            invoice_row(invoice_id="INV-900001", customer_id=""),
            invoice_row(invoice_id="INV-900002", customer_id="CUST-9001"),
            invoice_row(invoice_id="INV-900003", amount="-1250.00"),
            invoice_row(invoice_id="INV-900004", amount="N/A"),
            invoice_row(invoice_id="INV-900005", invoice_date="31/02/2024"),
            invoice_row(
                invoice_id="INV-900006",
                invoice_date="2025-03-20",
                due_date="2025-02-20",
            ),
            invoice_row(
                invoice_id="INV-900007",
                amount="4000.00",
                amount_paid="6500.00",
                status="Partial",
            ),
            invoice_row(invoice_id="INV-900008", status="Pending"),
            invoice_row(invoice_id="INV-900009", project_id="PRJ-9999"),
        ]
    )

    write_csv(DATA_DIR / "customers.csv", customers)
    write_csv(DATA_DIR / "projects.csv", projects)
    write_csv(DATA_DIR / "invoices.csv", invoices)
    (DATA_DIR / "KNOWN_BAD_RECORDS.txt").write_text(BAD_RECORD_NOTES)

    print(f"anchor date    {anchor.isoformat()}")
    print(f"customers.csv  {len(customers):>4} rows")
    print(f"projects.csv   {len(projects):>4} rows")
    print(f"invoices.csv   {len(invoices):>4} rows")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
