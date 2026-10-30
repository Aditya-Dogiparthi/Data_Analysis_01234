# Executive Memo — Collections Intelligence

**Decision:** the reported “+11% month-on-month recovery improvement” is **INCONCLUSIVE and not independently verified**. The supplied package is synthetic challenge data (seed 42), spanning 1 January–8 August 2026: seven complete months plus eight days of August, not twelve months.

## What happened?

After exact-row deduplication and conflict quarantine, there are 24,986 conflict-free payment rows, including 17,523 successful events totaling **₹131.47 Cr gross**. A further 1,253 reversal events totaling **₹9.47 Cr** are disclosed separately because the source does not reliably link reversals to original payments. Across the 17 operational source tables, 2,957 exact duplicate rows were removed. Fourteen payment IDs (28 rows) and 79 call IDs (158 rows) with conflicting payloads were quarantined.

Monthly gross successful cash was ₹18.72 Cr in January and ₹18.72 Cr in July, a Jan-to-Jul change of **+0.004%**. Month-on-month cash changes were -9.20%, +10.96%, -7.20%, +5.21%, -4.83% and +6.83%. The near-11% move occurred only from February to March and was not sustained. August is partial and not comparable. Cash-event growth is not a recovery-rate trend.

## Why did it happen?

The data does not identify a reliable cause of a recovery-rate change. Risk, DPD, loan type and geography cuts use current account/borrower snapshots, not historical effective-dated attributes. The fixed-February risk-mix proxy is a sensitivity check, not a point-in-time or exposure-weighted rate. Cohort and segment differences are descriptive. Campaign, channel, vendor, agent-tenure, call-hour and attempt-frequency results are correlations; cash has no linked touch, campaign, agent or PTP key. Selection into targeting is not random.

The source contains 30,000 agent rows but only 1,000 distinct agent IDs. Latest `updated_at` is used for the current dimension to avoid join fan-out; 262 employee codes map to multiple current agent IDs, so no automatic identity merge is safe. Disposition versions and vendor schema versions exist, but no approved semantic mapping proves RPC or code drift. Client and language fields, dialer mode, historical point-in-time exposure, and fully loaded costs are absent.

## Is the +11% claim real?

It cannot be proven or disproven as a **recovery-rate** change because the original KPI formula, complete 12-month window, historical eligible exposure and net-settlement basis are missing. Gross successful cash is measurable; recovery rate, verified contact/RPC, PTP conversion/kept rate, channel conversion, agent-hour productivity and cost per ₹ recovered are not certified. Start-of-month status coverage ranges from 0% in January to 85.62% in August; the observed account panel is not a full-portfolio denominator.

## What should we do?

**Test better borrower targeting first, but do not commit the full ₹10 Cr.** It is the most directly randomizable option, not a proven ROI winner. Run a pre-registered 1:1 borrower-cluster randomized pilot with frozen eligibility and intention-to-treat measurement. Use 60-day net settled cash per assigned unit, linked reversals, complete channel/agent costs and complaint/opt-out guardrails. Power the test using a valid baseline and minimum economic lift; retain a holdout for scale-up.

**Expected incremental recovery, cost, ROI and break-even are not estimable** from this package. The downside is zero incremental lift with positive pilot spend. Keep the remaining capital uncommitted until the lower confidence bound on incremental net contribution clears zero and the agreed ROI and customer-harm gates.

**Confidence:** high in source coverage, cash-event totals, dedup/conflict counts and missing-data findings; moderate in the measured survivorship and agent fan-out risks; low in any historical recovery-rate trend or causal driver.
