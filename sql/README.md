# SQL repository — PostgreSQL 16

The SQL layer is deliberately explicit and non-destructive. `raw.*` is immutable landing data (the loader stores source columns as `TEXT` plus ingestion metadata). SQL models cast values only in derived schemas. Do not run KPI queries directly against raw tables for financial reporting.

## Execution order

1. `00_setup/schemas.sql`
2. `cleaning/clean_payments.sql` and `cleaning/clean_event_records.sql`
3. `dimensions/current_dimension_snapshots.sql`
4. `golden/golden_call_events.sql` and `golden/golden_account_month_status.sql`
5. `metrics/monthly_cash_metrics.sql`, `metrics/eligible_account_cash.sql`, and `metrics/operational_descriptive_cuts.sql`
6. `investigations/*.sql` for QA and sensitivity analyses

Run from the repository root with `psql` or your SQL client after `python scripts/load_postgres.py`. Example:

```powershell
Get-Content sql/00_setup/schemas.sql | docker compose exec -T db psql -U collections_admin -d collections
```

Adapt credentials/database name to `.env`. The SQL uses PostgreSQL 16 syntax. The Python pipeline is the default portable execution path and remains authoritative for the supplied golden CSV exports.

## Non-negotiable controls

- `SELECT DISTINCT` only removes identical payloads. Repeated stable keys with different payloads are quarantined in full.
- `payment_reference` is not a global key; it can repeat across accounts.
- Never join historical dimension versions directly to event facts. Use a deterministic current snapshot for descriptive views or an effective-time + recorded-time as-of join for historical features.
- Only conflict-free `SUCCESS` rows enter gross successful cash. `REVERSED` is reported separately until original transaction linkage is reliable.
- All metrics are named by numerator, denominator, time window and status. An account-count proxy is not an exposure-weighted recovery rate.
- Interaction proximity is a candidate-touch diagnostic, not channel attribution or causal credit.
