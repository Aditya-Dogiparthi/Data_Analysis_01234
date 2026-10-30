# dbt Collections Models

The dbt project expects source CSVs to be loaded into PostgreSQL schema `raw`.

1. Copy `.env.example` to `.env` and set local credentials (`POSTGRES_PORT=5433` for the host-mapped Docker port).
2. `docker compose up -d db`
3. `pip install -r requirements.txt`
4. `python scripts/load_postgres.py`
5. Copy `dbt_collections/profiles.example.yml` to `~/.dbt/profiles.yml` (Windows: `%USERPROFILE%\.dbt\profiles.yml`) and update credentials.
6. From `dbt_collections/`, run `dbt parse`, `dbt run`, `dbt test`.

The loader is append-only and idempotent for the same file hash/source row. Raw source values land as text with source file, batch hash, source row and row hash metadata. SQL staging models cast values without changing raw evidence.

The dbt path currently provides a payments/calls/account-status analytical slice: staged payments and operational calls, conflict-free golden payment/call events, monthly cash, month-start eligible-account proxy, and QA tests. The broader collections analysis (all channels, portfolio mix, agent tenure, PTP, forensic reports and the end-to-end statistical investigation) is implemented in the Python pipeline and PostgreSQL SQL repository under `sql/`.

**Important:** monthly cash models read from `golden_payment_events`, not raw/staging payments. The current source does not support true net recovery, RPC, PTP-kept, channel conversion or ROI. The dbt model names and descriptions preserve those limitations.
