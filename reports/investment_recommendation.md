# ₹10 Cr Investment Recommendation

## Recommendation: prioritize better borrower targeting as a controlled pilot — do not deploy the full ₹10 Cr yet

This is the single area I would test first, not a claim that targeting has already won. It is directly testable through a frozen eligible population and account/borrower-cluster randomization. The supplied campaign/targeting comparisons are observational, overlap across channels and have no valid untreated counterfactual. They do not establish incremental recovery.

**Capital decision:** do not commit the full ₹10 Cr to any option on this evidence. Approve only a separately costed, capped experiment after a power calculation and procurement review; keep the remaining capital uncommitted until the experiment clears the investment gate.

## Financial case required by the assignment

| Required item | Evidence-based conclusion now | Why it is unavailable |
|---|---|---|
| Expected incremental recovery | **Not estimable** | No randomized treatment effect, reliable payment-to-assignment link, historical exposure denominator or net-settlement linkage |
| Estimated pilot / scale cost | **Not estimable** | No payroll-loaded, telephony, messaging, field, vendor, platform or implementation cost ledger/quotes |
| Expected ROI | **Not estimable** | Both incremental net contribution and fully loaded cost are unknown |
| Break-even | **Not estimable** | Requires contribution margin, pilot cost and an estimated distribution of incremental net settled cash |
| Confidence / range | No defensible numeric interval can be calculated from the observational data | Confidence is high that the current inputs are insufficient; confidence in any treatment-effect estimate is low |

Do not convert gross historical cash, targeted-account cash, or cash within a seven-day touch window into incremental recovery. Those are not causal estimates.

## Why targeting is the first test, not the proven winner

| Option | Main unresolved evidence | Decision now |
|---|---|---|
| Better telephony infrastructure | Versioned RPC mapping, uptime, link to incremental net cash and vendor cost | Do not scale; technical answered is not RPC |
| More collection agents | Productive time, marginal output per paid hour, payment-agent linkage and hiring cost | Do not scale; session login is not productive time |
| AI voice automation | Randomized lift, dialer-mode field, consent/complaint guardrails and platform/telephony cost | Not comparable; mode is not recorded |
| **Better borrower targeting** | Randomized lift, stable eligibility, payment linkage and full operating cost | **First pilot candidate; no proven lift** |
| WhatsApp / digital | Delivery/read/response-to-settled-cash linkage, incremental lift, pricing and opt-outs | Activity only; not conversion |
| Field operations | Visit-to-payment linkage, travel/staff cost, schedule quality and control | Activity only; 250 scheduled timestamps fail parsing |

## Experiment needed before release

1. Freeze eligibility once per test using point-in-time exposure, DPD, risk, vintage, client, region, language and prior contact. These attributes must be effective-dated and present; unavailable fields must not be imputed.
2. Randomize 1:1 at borrower-cluster level (account level only where a borrower has one account), stratified on pre-registered risk/DPD/exposure and historical contact bands. Persist assignment, policy version, seed, assignment time and all deviations.
3. Analyze **intention-to-treat (ITT)**. The primary outcome is 60-day net settled cash per assigned eligible unit. Link reversals to original settlements. Secondary outcomes include paid-account share, matured PTP kept, complaints, opt-outs, contact burden and treatment adherence.
4. Capture fully loaded experiment costs by treatment and control: agent, vendor, channel, platform, messaging, telephony, incentives and implementation. Maintain equal payment capture across arms.
5. Power the test from a clean baseline variance and a pre-agreed minimum economically meaningful INR lift. Pre-register the analysis, confidence interval, contribution margin, ROI hurdle and stop rules before exposing treatment.

## Financial formulas and decision gate

- `Incremental net contribution = (ITT incremental net settled cash × contribution margin) − fully loaded incremental cost`
- `ROI = incremental net contribution ÷ fully loaded incremental cost`
- `Break-even incremental net settled cash = fully loaded incremental cost ÷ contribution margin`

Scale only if the lower confidence bound on incremental net contribution clears zero and the pre-agreed ROI hurdle, while complaint, opt-out and policy guardrails pass. The estimate and interval must include settlement maturity, reversals and cost uncertainty.

**Key assumptions:** random assignment is preserved; no material cross-arm contamination; outcome capture is symmetric; the 60-day window is mature; costs are completely allocated; and concurrent policy changes are logged.

**Downside scenario:** zero incremental lift with positive experiment/implementation spend. The loss equals the pilot spend; it cannot be quantified until a cap and supplier/staffing costs are known. A negative lift or guardrail breach triggers pause/stop. Retain a randomized holdout during scale-up.

**Confidence:** high that no six-option full-deployment ROI can be responsibly ranked from the supplied data; low that targeting will outperform the other options until tested.
