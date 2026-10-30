# Independent metric contract

## Principles
1. Freeze the eligible population at the start of the measurement period; do not use end-of-period status to define who was at risk during the period.
2. Use point-in-time exposure for an amount-weighted recovery rate. An account-count denominator is a separate proxy and must be named as such.
3. Separate successful payment events from reversals, failed/pending events and net settled cash. Do not net reversals without a reliable original-transaction link.
4. Distinguish technical telephony answers from human contact, verified right-party contact (RPC), promises-to-pay (PTP) and collections.
5. Attribute cash to channels/campaigns only with an explicit assignment or linked interaction design; temporal proximity alone is candidate-touch evidence, not attribution.

## Status of requested measures
| Measure | Independent definition | Current status |
|---|---|---|
| Contact rate | Eligible accounts with a validated contact disposition / eligible accounts attempted | Not computable: disposition mapping absent |
| RPC | Eligible accounts with verified right-party contact / eligible accounts attempted | Not computable: no RPC map or identity verification |
| PTP rate | Accounts with valid PTP / accounts with verified RPC | Not computable: RPC mapping absent |
| PTP kept rate | Matured valid PTPs with linked settled payment in a documented grace window / matured valid PTPs | Not computable: payments have no `ptp_id`; reversals not linked |
| Recovery rate | Net settled cash / frozen period-start eligible exposure | Not computable: no historical exposure and no net settlement linkage |
| Recovery per account | Net settled cash / frozen eligible account count at period start | Proxy only: gross cash per observed-status start account; status coverage incomplete |
| Recovery per agent-hour | Agent-linked net settled cash / productive agent hours | Not computable: no payment-agent link or productive-time source |
| Cost per ₹ recovered | Fully loaded costs / incremental net settled ₹ | Not computable: no cost ledger or causal effect |
| Channel conversion | Net cash under a channel assignment / eligible accounts assigned to that channel | Not computable: no payment-touch key or randomization |

## Computable cash measure
`gross_successful_collections` is the sum of non-negative amounts on conflict-free payment rows with status `SUCCESS`. The reported package contains 17,523 successful payment events totalling ₹1,314,693,465.14. This is gross successful cash, not net recovery. 1,253 reversal events totalling ₹94,658,651.01 are disclosed separately.

## Provisional account-count proxy
For month `m`, status is evaluated as of the first instant of the month using the last event with `event_at < month_start` and `recorded_at <= month_start`. Eligible statuses are `ACTIVE`, `DELINQUENT`, `NPA`, and `PTP`. Accounts without a known status are not silently assumed eligible or ineligible; they are excluded from the observed-status denominator and coverage is reported.

This observed population is not representative by construction: coverage is 0.0% in Jan 2026, 24.17% in Feb, and 85.62% in Aug. The January denominator is unavailable. Do not publish a recovery rate from this panel.

## Operational definitions for future production
- Attempted account: unique eligible account receiving at least one outbound attempt in a fixed window.
- Contact: a disposition mapped and versioned by Operations to a confirmed human answer.
- RPC: verified borrower/authorized-party contact, distinct from technical answer or voicemail.
- Valid PTP: amount and date captured, within policy, with the account/borrower identified.
- Matured PTP: promised due date plus a pre-registered grace interval is before the extraction cutoff.
- Kept PTP: matured PTP linked to settled net cash within the grace interval. Partial keeps should be reported as a separate amount-weighted metric.
- Productive agent hour: scheduled/paid time less breaks, idle time and non-collection activities, with overlaps removed and independently validated.
- Incremental channel conversion: ITT difference in net settled outcome between randomized channel assignments, not last-touch credit.
