# Assignment Coverage Matrix

This matrix maps each assignment requirement to a concrete artifact and states where the source data cannot support a result. It is intentionally explicit: unavailable metrics are not replaced by convenient proxies without naming the limitation.

## Core leadership questions

| Requirement | Artifact / evidence | Status |
|---|---|---|
| What happened; when; what changed | `reports/executive_memo.md`, `data/golden/monthly_cash_metrics.csv`, `monthly_trend_analysis.csv` | Completed as gross cash-event reconstruction; not a recovery-rate proof |
| Where it changed | `portfolio_mix_by_*.csv`, `recovery_by_*.csv`, `agent_tenure_performance.csv`, `vendor_call_performance.csv`, `call_hour_performance.csv`, `attempt_frequency_outcomes.csv` | Descriptive only; current snapshots and missing links noted |
| Which metrics improve vs mislead | `docs/metric_definitions.md`, `reports/statistical_investigation.md` | Defined and status-labelled; contact/RPC/PTP conversion/recovery rate/ROI unavailable |
| Why it changed | `reports/statistical_investigation.md` | Facts/correlations/hypotheses separated; causal driver not identified |
| Validate reported +11% | Monthly cash trend + denominator and data quality diagnostics | Inconclusive; original formula, full year and exposure denominator missing |
| Allocate ₹10 Cr | `reports/investment_recommendation.md`, `six_option_investment_comparison.csv` | Better targeting selected as pilot priority only; no unsupported ROI estimate |

## Part 1 — Golden Dataset

| Requirement | Implementation |
|---|---|
| Source-of-truth decisions | `docs/forensic_decisions.md`, `docs/assumptions.md` |
| Entity resolution | Current borrower/agent snapshots; alias review; no fuzzy PII merges; `data/quarantine/*superseded*` |
| Deduplication | Exact full-row dedup in derived copies; stable-key payload conflicts quarantined in full |
| Missing data | Null inventory, contract report, explicit unknown/coverage flags; no silent zero/imputation for history |
| Timestamp treatment | Source strings preserved; event and recorded clocks separated; no unsupported timezone conversion |
| Payment attribution | Seven-day candidate-touch counts only; no last-touch attribution |
| Historical changes | Borrower/agent latest-update current snapshots; bitemporal account-status reconstruction |
| Exclusion and quantification | `reports/reconciliation_flow.csv`, `data/quarantine/`, `data/processed/pipeline_manifest.json` |

## Part 2 — Data Forensics

| Investigation | Finding / artifact |
|---|---|
| Duplicate payments | 486 exact duplicate rows removed; 14 payment IDs / 28 conflicting rows quarantined; `payment_deduplication.sql` |
| Attribution errors / window bias | No payment-to-touch/campaign/agent/PTP key; 1/7/30-day nested candidate-window sensitivity shows how apparent touch coverage changes with look-back length, without causal credit |
| Timezone problems | Payment timezone absent; call storage semantics unverified; source-local timestamps preserved |
| Vendor/disposition mapping | Vendor schema versions v1–v3 and disposition versions legacy/v1/v2 exist; semantic mapping unavailable |
| Agent identity | 30,000 agent versions / 1,000 IDs; 29,000 superseded versions; 262 employee codes alias across IDs |
| Portfolio mix | Current risk/DPD/loan/geography cuts; no historical effective-dated dimensions |
| Denominator manipulation | Start-vs-end status and coverage measured; unknown statuses excluded; start coverage is incomplete |

## Part 3 — Statistical Investigation

Mix, vintage cohorts, selection, survivorship, candidate attribution windows, short time-series and a segmented direction screen for Simpson-style divergence are implemented in `reports/statistical_investigation.md`, `data/golden/account_vintage_cohorts.csv`, `simpsons_paradox_*.csv` and notebooks. No causal inference is claimed.

## Part 4 — Counterfactual

`reports/counterfactual_design.md` specifies borrower-cluster randomized 1:1 assignment, control/treatment, frozen eligibility, ITT estimand, assumptions, confounders, power, guardrails and fallback DiD conditions. The supplied historical data do not identify the no-targeting counterfactual.

## Part 5 — Production Analytics Design

`docs/architecture.md` and `docs/architecture.svg` specify Raw → Staging → Clean → Golden → Feature → Metrics → Dashboard, data contracts, grains/keys, bitemporal history, lineage, incremental loads, late arrivals, backfills, monitoring and release gates.

## Deliverables

| Deliverable | Artifact |
|---|---|
| SQL repository | `sql/` and `dbt_collections/` |
| Analysis notebook | `notebooks/07_end_to_end_investigation.ipynb` plus six focused notebooks |
| Golden dataset / reproducible pipeline | `scripts/run_pipeline.py`, `data/golden/`, `data/processed/pipeline_manifest.json` |
| Data quality report | `reports/data_quality_report.md` plus CSV evidence registers |
| Executive dashboard | `app/dashboard.py` (single-screen Streamlit view) |
| Executive memo ≤2 pages | `reports/executive_memo.md` |
| Architecture diagram | `docs/architecture.svg` and `docs/architecture.md` |

## Explicit source limitations

The package is synthetic, covers seven full months plus partial August, and has no original KPI definition, historical outstanding-exposure snapshots, client, language, separate borrower-segment, dialer-mode, payment-to-interaction linkage, reliable reversal-to-original mapping or fully loaded cost ledger. A result that requires one of these is reported as unavailable/not identified, not fabricated.
