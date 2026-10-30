# Data-forensics decisions and evidence ledger

## Source-of-truth hierarchy
Raw CSVs are immutable evidence. Exact-row-deduplicated copies are derived only. A stable event key with multiple non-identical payloads is quarantined in full rather than resolved by arbitrary recency. Current dimensions use latest source `updated_at` only when the row is a versioned snapshot (borrowers, agents); original rows remain available in raw and superseded-version quarantine. Account status is reconstructed from event history with both event time and recorded time.

## Decisions
| Topic | Evidence | Treatment / limit |
|---|---|---|
| Duplicate rows | 2,957 exact duplicate rows across 17 operational sources | Remove from derived copies only; raw unchanged |
| Payment identifiers | 25,500 raw; 486 exact duplicates; 14 IDs / 28 non-identical rows | Quarantine all 28; 24,986 conflict-free golden payment rows |
| Payment references | 3,403 references repeat; references span multiple accounts | Never deduplicate on reference alone |
| Calls | 91,350 raw; 1,271 exact duplicates; 79 IDs / 158 conflicting payload rows | 89,921 conflict-free calls; quarantine all conflicting variants |
| Borrower versions | 30,600 raw; 600 exact dupes; 30,000 retained; 8,518 borrower IDs repeated; 18,985 superseded versions | Latest `updated_at` current snapshot; no fuzzy phone/email merge |
| Agent versions | 30,000 rows, 1,000 distinct agent IDs; 29,000 superseded versions | Latest `updated_at` dimension; join yields exactly 89,921 calls |
| Agent aliasing | 262 employee codes map to multiple current agent IDs; employee-code changes also exist in history | Do not merge until HR provides a crosswalk |
| Status bitemporality | Median recorded-event lag -0.13h; p95 21.56h; 30,191 negative lags | Preserve both clocks; start-of-month state uses event time before month start and recorded by month start |
| Denominator | Status coverage grows 0% Jan to 85.62% Aug | Unknown status excluded and shown; cannot represent full portfolio |
| Field schedule | 250 / 25,000 scheduled timestamps unparseable | Preserve raw value; exclude from schedule-adherence calculations |
| Agent sessions | 15,000 sessions; 0 invalid/>24h; 215 adjacent overlaps, 716.1h | Login time is not productive time; do not calculate recovery/hour |
| Vendor and dispositions | Vendor has schema versions v1-v3; disposition has legacy/v1/v2 | Code distribution only; no approved semantic map, so no RPC classification |
| Time zones | Payment rows have no timezone; call timestamps have labels but storage semantics undefined | Keep as recorded; do not convert or claim borrower-local hour |
| Attribution | Payment rows have no interaction/campaign/agent/PTP key | Seven-day prior touches are candidate exposure only; no last-touch credit |
| Financial unit economics | No fully loaded cost ledger; no causal effect | ROI/break-even not estimable |

## Exclusion rules
- Payment: exclude invalid timestamp and non-SUCCESS for gross successful cash; reversals are separate; quarantine conflicting payment IDs.
- Calls: remove exact duplicate payloads and exclude all call IDs with conflicting payloads from golden calls.
- Start-of-month denominator: require a status known by the beginning of the month; status unknown at that time remains unknown.
- Current dimensions: label DPD/risk/loan type/geography as current snapshot, not historical features.
- PTP: report source-status diagnostics only; do not classify kept PTPs from a payment unless a reliable PTP link exists.
- Channel/campaign/agent: describe activity only; do not assign payments by nearest interaction.

## Impact summary
See `reports/reconciliation_flow.csv`, `reports/forensic_findings.csv`, `reports/unavailable_dimensions.csv`, and the `data/quarantine/` folder for machine-readable counts and excluded payloads. No quarantined amount is labelled as loss or missed revenue.
