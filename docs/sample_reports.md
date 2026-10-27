# Sample report output

Generated with `python -m src.reports --format md`. Figures come from the synthetic extracts in `data/`.

### `overdue_invoices` -- Overdue invoices (worst first)

| invoice_id   | customer_name                 | project_name                    | invoice_date   | due_date   |     amount |   amount_paid |   balance_due |   days_overdue |
|:-------------|:------------------------------|:--------------------------------|:---------------|:-----------|-----------:|--------------:|--------------:|---------------:|
| INV-200307   | Harbor Utilities Corp.        | Birchwood Substation Upgrade    | 2025-01-22     | 2025-02-06 |  43,758.33 |          0.00 |     43,758.33 |            628 |
| INV-200082   | Riverbend Industrial LLC      | Fairmont Breaker Replacement    | 2025-01-07     | 2025-02-06 |  12,900.26 |          0.00 |     12,900.26 |            628 |
| INV-200372   | Birchwood Power LLC           | Northline Protection Study      | 2025-01-13     | 2025-02-12 |  53,600.55 |     18,698.90 |     34,901.65 |            622 |
| INV-200283   | Fairmont Industrial LLC       | Timberlake Arc Flash Assessment | 2025-01-15     | 2025-02-14 | 129,842.45 |          0.00 |    129,842.45 |            620 |
| INV-200039   | Meridian Utilities Inc.       | Harbor Fiber Backbone           | 2025-01-18     | 2025-02-17 | 146,090.48 |          0.00 |    146,090.48 |            617 |
| INV-200190   | Timberlake Transmission Corp. | Summit Relay Retrofit           | 2025-01-11     | 2025-02-25 | 104,299.32 |     34,819.07 |     69,480.25 |            609 |
| INV-200033   | Copperline Utilities Partners | Harbor Grid Hardening           | 2025-02-13     | 2025-02-28 | 170,650.75 |          0.00 |    170,650.75 |            606 |
| INV-200155   | Copperline Systems Co-op      | Cascade Arc Flash Assessment    | 2025-01-09     | 2025-03-10 |   2,781.64 |          0.00 |      2,781.64 |            596 |
| INV-200305   | Riverbend Industrial LLC      | Oakhurst Fiber Backbone         | 2025-02-17     | 2025-03-19 |  53,479.77 |          0.00 |     53,479.77 |            587 |
| INV-200094   | Summit Industrial Group       | Meridian Breaker Replacement    | 2025-02-19     | 2025-03-21 | 133,111.21 |     60,682.73 |     72,428.48 |            585 |
| INV-200263   | Meridian Utilities Inc.       | Blue Ridge Breaker Replacement  | 2025-02-19     | 2025-03-21 |  14,496.87 |          0.00 |     14,496.87 |            585 |
| INV-200312   | Granite Grid Services Group   | Granite Relay Retrofit          | 2025-03-07     | 2025-03-22 |  29,554.55 |          0.00 |     29,554.55 |            584 |
| INV-200311   | Birchwood Power LLC           | Northline Protection Study      | 2025-02-23     | 2025-03-25 | 174,854.07 |          0.00 |    174,854.07 |            581 |
| INV-200241   | Copperline Systems Group      | Redstone Control House Build    | 2025-01-24     | 2025-03-25 |  32,386.06 |          0.00 |     32,386.06 |            581 |
| INV-200040   | Riverbend Power Co-op         | Clearwater Breaker Replacement  | 2025-02-24     | 2025-03-26 |  77,779.26 |     21,969.85 |     55,809.41 |            580 |
| INV-200088   | Harbor Power Corp.            | Stonebridge Fiber Backbone      | 2025-02-09     | 2025-03-26 |  37,570.70 |          0.00 |     37,570.70 |            580 |
| INV-200164   | Harbor Power Corp.            | Granite Arc Flash Assessment    | 2025-02-15     | 2025-04-01 |  60,649.28 |          0.00 |     60,649.28 |            574 |
| INV-200124   | Fairmont Industrial LLC       | Cascade Grid Hardening          | 2025-03-09     | 2025-04-08 |  27,140.12 |     12,454.88 |     14,685.24 |            567 |
| INV-200339   | Granite Grid Services Group   | Granite Relay Retrofit          | 2025-03-25     | 2025-04-09 | 136,629.50 |          0.00 |    136,629.50 |            566 |
| INV-200259   | Cascade Utilities LLC         | Lakeshore Control House Build   | 2025-03-26     | 2025-04-10 | 179,883.35 |          0.00 |    179,883.35 |            565 |

### `revenue_by_month` -- Invoiced amount by month

| month      |   invoice_count |   total_invoiced |   total_collected |   running_total_invoiced |   change_vs_prior_month |   pct_change_vs_prior_month |
|:-----------|----------------:|-----------------:|------------------:|-------------------------:|------------------------:|----------------------------:|
| 2025-01-01 |              17 |     1,229,690.41 |        757,549.29 |             1,229,690.41 |                  nan    |                      nan    |
| 2025-02-01 |              21 |     1,970,117.22 |        830,470.16 |             3,199,807.63 |              740,426.81 |                       60.20 |
| 2025-03-01 |              23 |     2,321,598.01 |      1,247,020.29 |             5,521,405.64 |              351,480.79 |                       17.80 |
| 2025-04-01 |              12 |     1,204,573.74 |        927,383.01 |             6,725,979.38 |           -1,117,024.27 |                      -48.10 |
| 2025-05-01 |              23 |     2,158,040.90 |      1,492,874.24 |             8,884,020.28 |              953,467.16 |                       79.20 |
| 2025-06-01 |              14 |     1,038,197.55 |        745,174.37 |             9,922,217.83 |           -1,119,843.35 |                      -51.90 |
| 2025-07-01 |              14 |     1,229,705.94 |        844,755.58 |            11,151,923.77 |              191,508.39 |                       18.40 |
| 2025-08-01 |              20 |     1,871,000.57 |      1,445,659.35 |            13,022,924.34 |              641,294.63 |                       52.20 |
| 2025-09-01 |              21 |     2,318,734.10 |      1,693,838.81 |            15,341,658.44 |              447,733.53 |                       23.90 |
| 2025-10-01 |              11 |     1,170,192.36 |        543,649.68 |            16,511,850.80 |           -1,148,541.74 |                      -49.50 |
| 2025-11-01 |              13 |     1,230,484.31 |        997,084.43 |            17,742,335.11 |               60,291.95 |                        5.20 |
| 2025-12-01 |              18 |     1,376,676.60 |      1,130,774.73 |            19,119,011.71 |              146,192.29 |                       11.90 |
| 2026-01-01 |              18 |     1,596,218.78 |      1,065,881.93 |            20,715,230.49 |              219,542.18 |                       15.90 |
| 2026-02-01 |              17 |     1,691,886.17 |      1,066,755.48 |            22,407,116.66 |               95,667.39 |                        6.00 |
| 2026-03-01 |              13 |       910,022.62 |        406,700.31 |            23,317,139.28 |             -781,863.55 |                      -46.20 |
| 2026-04-01 |              10 |       793,291.91 |        482,335.45 |            24,110,431.19 |             -116,730.71 |                      -12.80 |
| 2026-05-01 |              18 |     1,365,662.59 |      1,011,400.96 |            25,476,093.78 |              572,370.68 |                       72.20 |
| 2026-06-01 |              22 |     2,061,791.86 |      1,597,912.95 |            27,537,885.64 |              696,129.27 |                       51.00 |
| 2026-07-01 |              27 |     2,783,155.35 |      1,682,485.29 |            30,321,040.99 |              721,363.49 |                       35.00 |
| 2026-08-01 |              20 |     2,011,772.55 |      1,605,603.68 |            32,332,813.54 |             -771,382.80 |                      -27.70 |
| 2026-09-01 |              12 |       852,587.23 |        489,926.66 |            33,185,400.77 |           -1,159,185.32 |                      -57.60 |
| 2026-10-01 |              19 |     1,658,280.94 |      1,039,077.83 |            34,843,681.71 |              805,693.71 |                       94.50 |

### `customer_revenue_rank` -- Customers ranked by total invoiced

| customer_id   | customer_name                  | industry             |   invoice_count |   total_invoiced |   balance_outstanding |   revenue_rank |   pct_of_total |   cumulative_pct |
|:--------------|:-------------------------------|:---------------------|----------------:|-----------------:|----------------------:|---------------:|---------------:|-----------------:|
| CUST-0038     | Birchwood Power LLC            | Oil & Gas            |              25 |     2,806,577.86 |            812,691.52 |              1 |           8.05 |             8.05 |
| CUST-0043     | Timberlake Transmission Corp.  | Manufacturing        |              21 |     2,135,635.60 |            556,323.03 |              2 |           6.13 |            14.18 |
| CUST-0054     | Harbor Power Corp.             | Utilities            |              19 |     1,863,462.19 |            847,010.43 |              3 |           5.35 |            19.53 |
| CUST-0050     | Meridian Utilities Inc.        | Mining               |              19 |     1,700,359.29 |            575,789.99 |              4 |           4.88 |            24.41 |
| CUST-0049     | Clearwater Energy LLC          | Manufacturing        |              14 |     1,532,849.92 |            324,626.53 |              5 |           4.40 |            28.81 |
| CUST-0034     | Blue Ridge Utilities Corp.     | Mining               |              19 |     1,363,875.23 |            318,696.86 |              6 |           3.91 |            32.73 |
| CUST-0020     | Riverbend Power Partners       | Oil & Gas            |              16 |     1,357,451.14 |            700,740.69 |              7 |           3.90 |            36.62 |
| CUST-0006     | Redstone Engineering LLC       | Engineering Services |              15 |     1,102,567.74 |            317,519.76 |              8 |           3.16 |            39.79 |
| CUST-0057     | Cascade Utilities LLC          | Mining               |               9 |     1,049,583.33 |            342,889.19 |              9 |           3.01 |            42.80 |
| CUST-0024     | Meridian Energy Inc.           | Oil & Gas            |              14 |     1,026,378.05 |            321,521.28 |             10 |           2.95 |            45.74 |
| CUST-0051     | Granite Infrastructure Corp.   | Renewables           |              10 |       988,034.04 |            643,911.49 |             11 |           2.84 |            48.58 |
| CUST-0025     | Fairmont Industrial LLC        | Transportation       |              10 |       970,837.80 |            346,002.81 |             12 |           2.79 |            51.37 |
| CUST-0012     | Westfield Engineering Partners | Mining               |               9 |       881,218.79 |            453,977.62 |             13 |           2.53 |            53.89 |
| CUST-0017     | Harbor Utilities Corp.         | Renewables           |               7 |       758,063.66 |            287,801.68 |             14 |           2.18 |            56.07 |
| CUST-0046     | Summit Engineering Corp.       | Renewables           |               9 |       735,927.52 |            343,958.40 |             15 |           2.11 |            58.18 |
| CUST-0022     | Cascade Resources Co-op        | Renewables           |               5 |       723,832.52 |                  0.00 |             16 |           2.08 |            60.26 |
| CUST-0001     | Harbor Grid Services Group     | Renewables           |              10 |       718,501.80 |             95,412.07 |             17 |           2.06 |            62.32 |
| CUST-0026     | Copperline Utilities Partners  | Engineering Services |               6 |       716,806.02 |            555,950.80 |             18 |           2.06 |            64.38 |
| CUST-0041     | Summit Power Corp.             | Utilities            |               7 |       710,139.83 |            311,740.50 |             19 |           2.04 |            66.42 |
| CUST-0035     | Blue Ridge Systems Partners    | Manufacturing        |               7 |       677,885.55 |              2,102.93 |             20 |           1.95 |            68.36 |

### `customer_balances` -- Customer receivables by age

| customer_id   | customer_name                  |   open_invoices |   total_outstanding |   current_not_yet_due |   overdue_1_30 |   overdue_31_60 |   overdue_61_90 |   overdue_90_plus |
|:--------------|:-------------------------------|----------------:|--------------------:|----------------------:|---------------:|----------------:|----------------:|------------------:|
| CUST-0054     | Harbor Power Corp.             |              11 |          847,010.43 |                  0.00 |           0.00 |            0.00 |            0.00 |        847,010.43 |
| CUST-0038     | Birchwood Power LLC            |               9 |          812,691.52 |                  0.00 |           0.00 |            0.00 |      353,662.09 |        459,029.43 |
| CUST-0020     | Riverbend Power Partners       |              12 |          700,740.69 |             18,173.70 |           0.00 |            0.00 |       14,092.98 |        668,474.01 |
| CUST-0051     | Granite Infrastructure Corp.   |               6 |          643,911.49 |                  0.00 |           0.00 |            0.00 |       79,755.89 |        564,155.60 |
| CUST-0050     | Meridian Utilities Inc.        |               9 |          575,789.99 |                  0.00 |      62,246.67 |       10,687.39 |       32,915.94 |        469,939.99 |
| CUST-0043     | Timberlake Transmission Corp.  |               6 |          556,323.03 |             59,528.70 |           0.00 |            0.00 |      177,884.27 |        318,910.06 |
| CUST-0026     | Copperline Utilities Partners  |               4 |          555,950.80 |                  0.00 |      75,096.83 |            0.00 |            0.00 |        480,853.97 |
| CUST-0012     | Westfield Engineering Partners |               4 |          453,977.62 |                  0.00 |           0.00 |            0.00 |            0.00 |        453,977.62 |
| CUST-0003     | Oakhurst Engineering Corp.     |               6 |          357,677.83 |                  0.00 |      11,663.37 |      128,871.05 |            0.00 |        217,143.41 |
| CUST-0025     | Fairmont Industrial LLC        |               4 |          346,002.81 |            134,959.81 |           0.00 |            0.00 |            0.00 |        211,043.00 |
| CUST-0046     | Summit Engineering Corp.       |               6 |          343,958.40 |                  0.00 |           0.00 |            0.00 |      102,114.64 |        241,843.76 |
| CUST-0057     | Cascade Utilities LLC          |               3 |          342,889.19 |             93,428.83 |           0.00 |            0.00 |            0.00 |        249,460.36 |
| CUST-0049     | Clearwater Energy LLC          |               4 |          324,626.53 |                  0.00 |           0.00 |            0.00 |            0.00 |        324,626.53 |
| CUST-0024     | Meridian Energy Inc.           |               5 |          321,521.28 |            132,895.25 |           0.00 |            0.00 |            0.00 |        188,626.03 |
| CUST-0034     | Blue Ridge Utilities Corp.     |               6 |          318,696.86 |                  0.00 |           0.00 |            0.00 |       23,082.28 |        295,614.58 |
| CUST-0006     | Redstone Engineering LLC       |               7 |          317,519.76 |                  0.00 |           0.00 |       76,044.99 |       20,861.65 |        220,613.12 |
| CUST-0041     | Summit Power Corp.             |               3 |          311,740.50 |            156,737.35 |           0.00 |            0.00 |      100,549.86 |         54,453.29 |
| CUST-0017     | Harbor Utilities Corp.         |               4 |          287,801.68 |                  0.00 |      44,552.22 |            0.00 |            0.00 |        243,249.46 |
| CUST-0045     | Birchwood Transmission Inc.    |               3 |          241,116.13 |                  0.00 |           0.00 |            0.00 |            0.00 |        241,116.13 |
| CUST-0011     | Riverbend Engineering LLC      |               2 |          236,018.33 |                  0.00 |           0.00 |            0.00 |       87,946.68 |        148,071.65 |

### `ar_aging_summary` -- Receivables aging summary

| aging_bucket   |   open_invoices |   balance_due |   pct_of_receivables |
|:---------------|----------------:|--------------:|---------------------:|
| 0 - current    |              10 |    791,359.97 |                 6.70 |
| 1 - 1-30 days  |               8 |    396,720.24 |                 3.40 |
| 2 - 31-60 days |               5 |    337,245.31 |                 2.90 |
| 3 - 61-90 days |              14 |  1,249,711.69 |                10.60 |
| 4 - 90+ days   |             123 |  8,964,330.02 |                76.40 |

### `project_profitability` -- Project profitability

| project_id   | project_name                    | customer_name                 | status    |   budget_amount |   total_invoiced |   total_collected |   labor_cost |   gross_margin |   margin_pct |   pct_of_budget_invoiced |
|:-------------|:--------------------------------|:------------------------------|:----------|----------------:|-----------------:|------------------:|-------------:|---------------:|-------------:|-------------------------:|
| PRJ-1035     | Ironwood Breaker Replacement    | Cascade Resources Co-op       | Completed |      130,901.44 |       723,832.52 |        723,832.52 |    53,806.31 |     670,026.21 |        92.60 |                   553.00 |
| PRJ-1024     | Copperline Breaker Replacement  | Birchwood Power LLC           | Completed |      172,363.37 |       672,784.20 |        529,954.41 |    70,562.70 |     602,221.50 |        89.50 |                   390.30 |
| PRJ-1069     | Lakeshore Control House Build   | Cascade Utilities LLC         | Completed |      310,018.91 |       692,734.45 |        443,274.09 |   115,192.76 |     577,541.69 |        83.40 |                   223.40 |
| PRJ-1081     | Meridian Relay Retrofit         | Redstone Engineering LLC      | Completed |       80,140.94 |       606,970.74 |        503,040.79 |    59,003.87 |     547,966.87 |        90.30 |                   757.40 |
| PRJ-1085     | Summit Fiber Backbone           | Meridian Utilities Inc.       | Active    |      483,083.98 |       765,779.67 |        497,404.55 |   220,892.69 |     544,886.98 |        71.20 |                   158.50 |
| PRJ-1003     | Ironwood Load Flow Analysis     | Granite Infrastructure Corp.  | Active    |      231,294.48 |       722,181.58 |        158,025.98 |   201,784.85 |     520,396.73 |        72.10 |                   312.20 |
| PRJ-1077     | Ironwood Metering Rollout       | Clearwater Energy LLC         | Active    |      301,473.42 |       648,376.42 |        472,198.80 |   146,638.99 |     501,737.43 |        77.40 |                   215.10 |
| PRJ-1050     | Harbor Relay Retrofit           | Riverbend Power Partners      | Active    |      188,561.05 |       593,975.25 |         83,245.09 |   114,939.83 |     479,035.42 |        80.60 |                   315.00 |
| PRJ-1028     | Fairmont Relay Retrofit         | Ironwood Systems Group        | Completed |       48,682.38 |       512,967.04 |        400,661.88 |    42,967.45 |     469,999.59 |        91.60 |                 1,053.70 |
| PRJ-1071     | Northline Metering Rollout      | Redstone Engineering LLC      | Completed |       94,997.84 |       495,597.00 |        282,007.19 |    86,037.00 |     409,560.00 |        82.60 |                   521.70 |
| PRJ-1043     | Fairmont Control House Build    | Clearwater Energy LLC         | Active    |      488,011.71 |       593,648.19 |        524,455.73 |   240,367.21 |     353,280.98 |        59.50 |                   121.60 |
| PRJ-1042     | Ironwood Grid Hardening         | Blue Ridge Utilities Corp.    | Completed |      139,566.21 |       406,360.93 |        381,956.02 |    67,471.53 |     338,889.40 |        83.40 |                   291.20 |
| PRJ-1061     | Summit Metering Rollout         | Riverbend Power Partners      | Active    |      831,880.89 |       763,475.89 |        573,465.36 |   439,896.15 |     323,579.74 |        42.40 |                    91.80 |
| PRJ-1040     | Northline Load Flow Analysis    | Blue Ridge Utilities Corp.    | Completed |       86,815.09 |       352,680.68 |        197,400.73 |    32,511.85 |     320,168.83 |        90.80 |                   406.20 |
| PRJ-1051     | Timberlake Protection Study     | Oakhurst Grid Services Group  | On Hold   |      151,868.16 |       412,482.85 |        412,482.85 |    95,651.26 |     316,831.59 |        76.80 |                   271.60 |
| PRJ-1018     | Summit Relay Retrofit           | Timberlake Transmission Corp. | Completed |    1,345,098.16 |     1,108,577.11 |        690,127.32 |   794,446.24 |     314,130.87 |        28.30 |                    82.40 |
| PRJ-1021     | Blue Ridge Arc Flash Assessment | Birchwood Power LLC           | Active    |      524,404.46 |       776,604.96 |        611,943.02 |   472,041.35 |     304,563.61 |        39.20 |                   148.10 |
| PRJ-1014     | Birchwood Substation Upgrade    | Harbor Utilities Corp.        | Active    |      308,499.68 |       382,358.31 |        251,559.04 |   151,330.89 |     231,027.42 |        60.40 |                   123.90 |
| PRJ-1056     | Redstone Relay Retrofit         | Blue Ridge Transmission Inc.  | Active    |      386,459.97 |       545,297.54 |        380,539.60 |   333,737.21 |     211,560.33 |        38.80 |                   141.10 |
| PRJ-1064     | Cascade Breaker Replacement     | Summit Power Corp.            | Active    |      407,694.19 |       394,446.02 |        237,708.67 |   200,543.37 |     193,902.65 |        49.20 |                    96.80 |

### `projects_over_budget` -- Projects over budget

| project_id   | project_name               | customer_name                 | status    |   budget_amount |   labor_cost |   overrun_amount |   pct_of_budget_spent |
|:-------------|:---------------------------|:------------------------------|:----------|----------------:|-------------:|-----------------:|----------------------:|
| PRJ-1076     | Northline Protection Study | Birchwood Power LLC           | Active    |    1,273,675.80 | 1,539,918.38 |       266,242.58 |                120.90 |
| PRJ-1045     | Harbor Load Flow Analysis  | Riverbend Energy Co-op        | Active    |    1,248,425.65 | 1,448,051.28 |       199,625.63 |                116.00 |
| PRJ-1008     | Cascade Grid Hardening     | Fairmont Industrial LLC       | Active    |      808,864.03 |   983,945.76 |       175,081.73 |                121.60 |
| PRJ-1055     | Harbor Substation Upgrade  | Blue Ridge Systems Partners   | Completed |      689,164.74 |   833,103.70 |       143,938.96 |                120.90 |
| PRJ-1047     | Harbor Grid Hardening      | Copperline Utilities Partners | Active    |    1,115,487.64 | 1,182,755.45 |        67,267.81 |                106.00 |

### `pipeline_run_history` -- Pipeline run history

|   run_id | status   | started_at                       |   duration_seconds |   rows_extracted |   rows_loaded |   rows_inserted |   rows_updated |   rows_rejected | error_message   |
|---------:|:---------|:---------------------------------|-------------------:|-----------------:|--------------:|----------------:|---------------:|----------------:|:----------------|
|        2 | success  | 2026-10-27 18:09:02.727637+00:00 |               0.04 |              565 |           545 |               0 |            545 |              20 |                 |
|        1 | success  | 2026-10-27 18:09:02.217022+00:00 |               0.04 |              565 |           545 |             545 |              0 |              20 |                 |

### `rejection_summary` -- Rejected records by rule (latest run)

| source_table   | rule               |   rejected_rows | example_key   |   first_source_row | example_reason                                                                                  |
|:---------------|:-------------------|----------------:|:--------------|-------------------:|:------------------------------------------------------------------------------------------------|
| customers      | missing_required   |               2 | CUST-0901     |                 63 | customer_id is required but missing                                                             |
| customers      | duplicate_key      |               1 | CUST-0007     |                 62 | customer_id=CUST-0007 already seen at source row 8                                              |
| customers      | invalid_date       |               1 | CUST-0902     |                 65 | created_date='2024-13-45' is not a valid date                                                   |
| invoices       | duplicate_key      |               2 | INV-200031    |                402 | invoice_id=INV-200031 already seen at source row 32                                             |
| invoices       | date_order         |               1 | INV-900006    |                409 | due_date 2025-02-20 is before invoice_date 2025-03-20                                           |
| invoices       | invalid_date       |               1 | INV-900005    |                408 | invoice_date='31/02/2024' is not a valid date                                                   |
| invoices       | invalid_status     |               1 | INV-900008    |                411 | status='Pending' is not a valid status (expected one of Paid, Open, Partial, Void)              |
| invoices       | missing_required   |               1 | INV-900001    |                404 | customer_id is required but missing                                                             |
| invoices       | negative_amount    |               1 | INV-900003    |                406 | amount=-1250.00 must not be negative                                                            |
| invoices       | non_numeric_amount |               1 | INV-900004    |                407 | amount='N/A' is not a valid amount                                                              |
| invoices       | orphan_customer    |               1 | INV-900002    |                405 | customer_id=CUST-9001 does not exist                                                            |
| invoices       | orphan_project     |               1 | INV-900009    |                412 | project_id=PRJ-9999 does not exist                                                              |
| invoices       | overpaid           |               1 | INV-900007    |                410 | amount_paid=6500.00 exceeds amount=4000.00                                                      |
| projects       | date_order         |               1 | PRJ-2003      |                 90 | end_date 2024-03-01 is before start_date 2024-08-01                                             |
| projects       | duplicate_key      |               1 | PRJ-1004      |                 87 | project_id=PRJ-1004 already seen at source row 5                                                |
| projects       | invalid_status     |               1 | PRJ-2004      |                 91 | status='Archived' is not a valid status (expected one of Active, Completed, On Hold, Cancelled) |
| projects       | negative_amount    |               1 | PRJ-2002      |                 89 | budget_amount=-45000.00 must not be negative                                                    |
| projects       | orphan_customer    |               1 | PRJ-2001      |                 88 | customer_id=CUST-9999 does not exist                                                            |

### `rejected_records_detail` -- Rejected records in detail (latest run)

| source_table   |   source_row | natural_key   | rule               | reason                                                                                          |
|:---------------|-------------:|:--------------|:-------------------|:------------------------------------------------------------------------------------------------|
| customers      |           62 | CUST-0007     | duplicate_key      | customer_id=CUST-0007 already seen at source row 8                                              |
| customers      |           63 |               | missing_required   | customer_id is required but missing                                                             |
| customers      |           64 | CUST-0901     | missing_required   | customer_name is required but missing                                                           |
| customers      |           65 | CUST-0902     | invalid_date       | created_date='2024-13-45' is not a valid date                                                   |
| invoices       |          402 | INV-200031    | duplicate_key      | invoice_id=INV-200031 already seen at source row 32                                             |
| invoices       |          403 | INV-200077    | duplicate_key      | invoice_id=INV-200077 already seen at source row 78                                             |
| invoices       |          404 | INV-900001    | missing_required   | customer_id is required but missing                                                             |
| invoices       |          405 | INV-900002    | orphan_customer    | customer_id=CUST-9001 does not exist                                                            |
| invoices       |          406 | INV-900003    | negative_amount    | amount=-1250.00 must not be negative                                                            |
| invoices       |          407 | INV-900004    | non_numeric_amount | amount='N/A' is not a valid amount                                                              |
| invoices       |          408 | INV-900005    | invalid_date       | invoice_date='31/02/2024' is not a valid date                                                   |
| invoices       |          409 | INV-900006    | date_order         | due_date 2025-02-20 is before invoice_date 2025-03-20                                           |
| invoices       |          410 | INV-900007    | overpaid           | amount_paid=6500.00 exceeds amount=4000.00                                                      |
| invoices       |          411 | INV-900008    | invalid_status     | status='Pending' is not a valid status (expected one of Paid, Open, Partial, Void)              |
| invoices       |          412 | INV-900009    | orphan_project     | project_id=PRJ-9999 does not exist                                                              |
| projects       |           87 | PRJ-1004      | duplicate_key      | project_id=PRJ-1004 already seen at source row 5                                                |
| projects       |           88 | PRJ-2001      | orphan_customer    | customer_id=CUST-9999 does not exist                                                            |
| projects       |           89 | PRJ-2002      | negative_amount    | budget_amount=-45000.00 must not be negative                                                    |
| projects       |           90 | PRJ-2003      | date_order         | end_date 2024-03-01 is before start_date 2024-08-01                                             |
| projects       |           91 | PRJ-2004      | invalid_status     | status='Archived' is not a valid status (expected one of Active, Completed, On Hold, Cancelled) |

### `load_audit_detail` -- Load audit (latest run)

| target_table   |   rows_in |   rows_inserted |   rows_updated |   rows_rejected |   duration_ms |
|:---------------|----------:|----------------:|---------------:|----------------:|--------------:|
| customers      |        60 |               0 |             60 |               4 |             5 |
| projects       |        85 |               0 |             85 |               5 |             7 |
| invoices       |       400 |               0 |            400 |              11 |            15 |

