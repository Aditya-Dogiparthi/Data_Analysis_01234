# Data Quality & Reconciliation Report

**Scope:** supplied synthetic challenge data (seed 42), not a production client dataset. Raw data is preserved unchanged. Rebuild with `python scripts/run_pipeline.py`.

## Raw → rejected/corrected → golden

| Source | Raw rows | Exact duplicates removed | Conflict rows quarantined | Historical versions superseded | Golden / current clean rows |
|---|---:|---:|---:|---:|---:|
| Payments | 25,500 | 486 | 28 across 14 payment IDs | — | 24,986 |
| Calls | 91,350 | 1,271 | 158 across 79 call IDs | — | 89,921 |
| Borrowers | 30,600 | 600 | — | 18,985 | 11,015 current borrower IDs |
| Agents | 30,000 | 0 | — | 29,000 | 1,000 current agent IDs |
| WhatsApp events | 60,600 | 600 | 0 | — | 60,000 |
| All 17 operational sources | 639,185 | 2,957 | See event quarantine | See versioned dimensions | Source-specific outputs |

The complete table by source is `reports/reconciliation_flow.csv`. `data/quarantine/payment_id_conflicts.csv`, `data/quarantine/event_id_conflicts.csv`, `data/quarantine/borrower_superseded_versions.csv`, and `data/quarantine/agent_superseded_versions.csv` preserve excluded payloads/versions. No raw input is overwritten.

## Material issues and business impact

1. **Duplicate payment events.** 486 exact full-row duplicates are removed. 14 payment IDs have 28 non-identical rows and are quarantined in full. A total of 3,403 repeated payment references occur; the reference is not a safe global key. Golden payments contain 24,986 rows. The quarantined amount is not counted as revenue or as a loss.
2. **Call event conflicts.** 1,271 exact duplicate call rows are removed; 79 call IDs with 158 non-identical payload rows are quarantined. Golden calls contain 89,921 rows. Conflicting IDs are excluded before agent/vendor/campaign joins.
3. **Agent identity/history fan-out.** The 30,000-row agent source contains only 1,000 agent IDs. Latest `updated_at` provides one current snapshot per ID; joining all versions to calls would multiply activity. After canonicalization, agent-call totals reconcile to 89,921 conflict-free calls. 262 employee codes map to multiple current agent IDs, so no automatic identity merge is safe.
4. **Borrower version history.** After 600 exact duplicates, 30,000 records remain; 8,518 borrower IDs have multiple rows. 18,985 older rows are preserved in superseded-version quarantine. Latest `updated_at` is suitable only for the current dimension, not a historical borrower profile. Repeated emails/phones are not used for fuzzy entity resolution.
5. **Survivorship/denominator leakage.** A month-end status can drop accounts that became PAID/CLOSED/WRITEOFF during the month. The panel now uses status known at month start, but start-status coverage is incomplete: 0.0% Jan, 24.17% Feb, 41.20% Mar, 55.73% Apr, 66.32% May, 74.57% Jun, 80.75% Jul, and 85.62% Aug. The observed subpopulation is not a full-portfolio denominator. January has no prior status history.
6. **Timestamp bitemporality.** `recorded_at - event_at` has median -0.13h, p95 21.56h and 30,191 negative lags. Event time and ingestion/recorded time are separate; a historical as-known snapshot must apply both. Payment timestamps have no row-level timezone. Call timezone labels exist but it is not documented whether `event_at` is UTC or local wall time.
7. **Schema/version drift.** Disposition versions include `legacy`, `v1`, and `v2`; codes include CALLBACK, DISPUTE, NO_CONTACT, PAID, PROMISE_TO_PAY, PTP, PTP_BROKEN, REFUSED and WRONG_NUMBER. Vendor metadata includes v1-v3 but no effective-dated response-code mapping. Semantic drift is a risk, not a proven mapping change.
8. **Field visit and session quality.** 250 of 25,000 scheduled timestamps fail parsing. Among 15,000 sessions, 215 adjacent overlaps total 716.1 hours; zero sessions were non-positive or longer than 24 hours. Logged-in time is not productive time.
9. **Missing dimensions and keys.** No client or language field, no distinct/effective-dated borrower-segment field (only a current account-level `risk_segment` proxy), no dialer mode (human/predictive/progressive/IVR/agentic voice), no historical exposure balance, no payment-to-touch/agent/campaign/PTP key, and no channel/agent/vendor cost ledger. These omissions prevent several requested dimensions and all ROI measures.
10. **Attribution-window sensitivity.** Of 17,523 successful payments, candidate-touch proximity is 3.24% at 1 day, 20.16% at 7 days and 59.76% at 30 days. This sensitivity is documented in `data/golden/payment_touch_window_sensitivity.csv`; none of the windows is a validated attribution rule.

## Payment control totals

- 17,523 successful payment events; gross successful cash **₹1,314,693,465.14 (₹131.47 Cr)**.
- 1,253 reversal events; **₹94,658,651.01 (₹9.47 Cr)**, disclosed separately.
- Payment coverage: 1 Jan 2026 00:14:40 through 8 Aug 2026 23:50:23; seven complete months and a partial August.
- Gross successful cash is not net settled recovery. There is no reliable original-payment reversal link.

## Detection and ongoing controls

Every source is checked for required columns, exact duplicate payloads, key-level conflicts, nulls and date parse failures. Production should add schema-version contracts, freshness/late-arrival alerts, stable key uniqueness tests, referential-integrity checks, status transition validation, bitemporal backfill checks and financial reconciliation to bank/settlement ledger. See the SQL and dbt folders for reproducible implementations and the production architecture.

## Reproducibility and lineage

`data/processed/pipeline_manifest.json` records the UTC run ID, Python/pandas/numpy versions, source file SHA-256 hashes and row counts, plus generated CSV artifact hashes/row counts. Re-run `python scripts/run_pipeline.py` to regenerate the full layer. Raw CSVs remain unchanged; the manifest allows reviewers to detect source-package or output drift.
