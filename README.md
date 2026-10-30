# Collections Intelligence — Data Forensics & Decision Platform

> **Evidence first. Trust the evidence, not the dashboard.**

A reproducible analytics investigation for a synthetic financial-collections challenge. The repository includes raw-source files locally, a profiling/cleaning pipeline, golden analytical tables, SQL models, an interactive Streamlit dashboard, statistical investigation notebooks, tests, and executive-facing documentation.

## Important: what this project can and cannot claim

The supplied source README explicitly identifies the package as **synthetic challenge data (seed 42)** with deliberately injected anomalies. The files cover **1 January–8 August 2026** for most operational events—not a full 12 months. August is partial. Therefore:
- Results are demonstrations of analytical logic on synthetic data, not evidence about a real collections business.
- The 11% business claim cannot be verified unless the original reporting definition and comparable complete periods are supplied.
- No causal investment ROI is asserted. The investment section is a decision framework and pilot proposal.
- Timezone normalization is not guessed: raw timestamp strings are preserved and source timezone fields are retained. A timestamp without a trustworthy timezone mapping is not silently converted.

## Quick start (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/run_pipeline.py
streamlit run app/dashboard.py
```

The pipeline reads `data/raw/*.csv`, writes profiling and cleaned outputs under `data/processed/` and `data/golden/`, builds bitemporal account-month panels, mix/cohort and Simpson-style direction diagnostics, operational cuts, identity reviews and forensic findings, then writes a SHA-256 source/output lineage manifest. Raw source files are never modified.

Run checks:

```powershell
pytest -q
```

Optional PostgreSQL/dbt path:
1. Start PostgreSQL 16 using `docker compose up -d db`.
2. Copy `.env.example` to `.env` and set credentials.
3. Run `python scripts/load_postgres.py` to land source CSVs into the append-only `raw` schema. Copy `dbt_collections/profiles.example.yml` to your user dbt profiles path and set credentials.
4. Run `dbt parse`, `dbt run`, and `dbt test` from `dbt_collections`. The compose host port and `.env.example` use `5433`; change both consistently if needed.

The Python pipeline is the default reproducible path and does not require a database. `scripts/run_pipeline.py` orchestrates contract validation, source profiling, exact deduplication, conflict quarantine, advanced descriptive analysis, bitemporal account-month reconstruction, required segment/operational diagnostics and manifest generation.

## Repository map

| Path | Purpose |
|---|---|
| `data/raw/` | Original uploaded CSVs; preserved locally and git-ignored |
| `data/processed/` | Profiling, row-level clean outputs, pipeline manifests |
| `data/golden/` | Reproducible golden account/payment/interaction tables and monthly metrics |
| `data/quarantine/` | Conflicting-key records requiring review |
| `scripts/` | Ingestion, profiling, pipeline, export |
| `sql/` | PostgreSQL SQL for non-destructive cleaning, current dimensions, golden facts, month-start metrics, operational cuts and investigations (`sql/README.md` gives run order) |
| `dbt_collections/` | dbt project structure and models/tests |
| `notebooks/` | End-to-end reasoning notebook plus six focused investigation notebooks |
| `app/` | CEO-oriented Streamlit dashboard |
| `reports/` | Data-quality report, executive memo, investment recommendation |
| `docs/` | Metric definitions, forensic decisions, architecture, assumptions |
| `tests/` | Automated correctness tests |

## Analytical conventions

- **Payments:** exact duplicate rows are removed. Repeated payment IDs with conflicting payloads are quarantined. Only `SUCCESS` records enter gross successful collections; `FAILED` and `PENDING` do not. `REVERSED` is reported separately because the supplied schema has no explicit reversal-to-original-payment key. Do not net a reversal against an arbitrary payment.
- **Account denominator:** current `accounts.csv` is a snapshot, not a historical monthly eligible-account ledger. Monthly account-level recovery rates are therefore not presented as verified historical rates.
- **Recovery amount:** monthly gross successful payment amount is a cash-event measure, not a portfolio-normalized recovery rate.
- **Attribution:** no payment-to-interaction causal attribution is assumed. A nearest/latest touch is not proof of influence.
- **Dates:** event timestamps are parsed as source-local naive values for month grouping only. No UTC conversion is applied without reliable per-event timezone evidence.
- **Data trust:** row counts and exclusions are output by the pipeline; inspect `reports/data_quality_report.md` after every run.

## Current data scope

The uploaded source package contains 17 operational source tables (including vendor telephony) plus the data dictionary. The profiling output records exact row counts, columns, null rates, full-row duplicates and date ranges. Most operational events span January through early August 2026.

## GitHub publication

Raw data is excluded by default because borrower/collections datasets can contain sensitive information, even when a challenge pack is synthetic. To publish:
```powershell
git init
git add .
git status
git commit -m "Build collections intelligence investigation platform"
git branch -M main
git remote add origin https://github.com/<your-username>/collections-intelligence.git
git push -u origin main
```
Before `git add`, inspect `git status` and ensure no `.env`, raw extracts, database dumps, or personal data are staged. The project code and documentation are GitHub-ready; raw data can be supplied separately by an authorized reviewer.


## Generated analytical outputs

Key files after pipeline execution:
- `data/golden/golden_payments.csv` — successful, failed, pending and reversal payment records after exact-row dedup and payment-ID conflict quarantine.
- `data/golden/account_month_recovery_panel.csv` — account-month cash panel with provisional eligibility and current snapshot dimensions.
- `data/golden/monthly_eligible_account_metrics.csv` — gross cash/account-count metrics; not net recovery rate.
- `data/golden/mix_adjusted_recovery_proxy.csv` — fixed-February current-risk mix sensitivity proxy (not historical/exposure-weighted).
- `data/golden/account_vintage_cohorts.csv` — account opening-month cohort panel.
- `data/golden/targeting_strategy_outcomes_descriptive.csv` — non-causal strategy comparison.
- `data/golden/agent_tenure_performance.csv` — call outcomes by tenure band.
- `reports/forensic_findings.csv` — measured issue register.
- `reports/six_option_investment_comparison.csv` — six-option evidence and pilot comparison.
- `reports/counterfactual_design.md` — randomized targeting experiment design.
- `docs/assignment_coverage_matrix.md` — requirement-by-requirement traceability, including unsupported metrics.
- `data/processed/pipeline_manifest.json` — source/output SHA-256 hashes, row counts and run metadata.
- `data/golden/simpsons_paradox_pair_summary.csv` — segmented month-pair direction screen; not a causal decomposition.
- `data/golden/payment_touch_window_sensitivity.csv` — 1/7/30-day candidate-touch look-back sensitivity; not causal attribution.
- `docs/assignment_coverage_matrix.md` — traceability from every assignment section to evidence/artifact or explicit gap.

## Validation boundary

The latest full pipeline run completed with run ID `20261030T094553Z`; the generated manifest records 18 raw sources and 103 generated CSV artifacts. The current automated suite passes **23 tests**. Python compilation, YAML parsing and execution of the 28-cell end-to-end notebook also pass. Streamlit, PostgreSQL and dbt runtime integrations are not installed/configured in the build environment and are not claimed as executed; see `reports/validation_status.md`. The SQL implementation targets PostgreSQL 16 and the dbt project is an optional implementation path.
