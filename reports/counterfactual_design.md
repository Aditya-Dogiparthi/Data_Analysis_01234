# Counterfactual: what if targeting had not changed?

## Identification status in the supplied data
**Not identified.** The `daily_targeting` and `campaigns` records are observational and overlap. There is no stable randomized assignment indicator, verified untreated population, pre-period exposure history, client dimension or payment-to-target/campaign link. An account's later cash cannot be safely attributed to its most recent campaign or touch. A regression on these data would adjust observed fields but would not remove unobserved selection. The counterfactual “recovery if the targeting strategy had not changed” is therefore not identified.

## Preferred design: stratified randomized account/borrower-cluster trial

- **Treatment group:** eligible accounts assigned to the new targeting policy before any campaign touch.
- **Control group:** eligible accounts assigned to business-as-usual targeting.
- **Unit:** borrower cluster, if one borrower has multiple accounts; otherwise account. Cluster avoids spillover and duplicate treatment.
- **Eligibility:** freeze once at assignment using a versioned rule and point-in-time outstanding balance, DPD, risk, client, region, language and prior contact history.
- **Randomization:** 1:1 within pre-specified strata; persist experiment_id, unit_id, assignment, assignment timestamp, seed, targeting-policy version and all deviations.
- **Exposure:** measure both assigned policy (ITT) and actual touches as secondary compliance diagnostics. Do not condition the primary analysis on successful contact.
- **Primary outcome:** net settled collections per assigned eligible unit over a fixed 60-day window, with cash/reversal linkage and a frozen baseline exposure. 30-day cash can be a secondary early outcome.
- **Secondary outcomes:** paid-account share, PTP creation/kept (with explicit ptp_id link and maturity rules), contact burden, complaints, opt-outs, broken promises and fully loaded cost.
- **Estimator:** mean **intention-to-treat (ITT)** difference in outcomes, with pre-registered baseline adjustment and standard errors clustered by randomization unit. Report absolute INR, relative lift, confidence interval and treatment compliance.
- **Power:** estimate outcome variance from a valid historical cohort; define minimum economically meaningful INR lift and power/sample size before launch. Do not select the sample after outcomes are seen.
- **Guardrails:** legal contact policy, per-borrower contact caps, complaint/escalation limits, opt-out handling, reversals, hardship and vulnerable-customer policies.

## Assumptions and confounders
Random assignment is implemented and preserved; no cross-arm policy contamination; outcome capture is equal across arms; experiment windows and settlement maturity are comparable; no concurrent campaign/collections policy changes differentially affect arms; account ownership and client changes are logged. Likely confounders in a non-random design include DPD, outstanding exposure, loan type, risk, geography, language, client, prior payment/contact history, agent capacity, campaign priority, seasonality, vintage and channel availability.

## Fallback if randomization cannot be used
Use difference-in-differences only when a credible untreated/comparison group exists, groups have comparable pre-trends, assignment does not anticipate treatment, no differential concurrent intervention occurs, and composition is stable. Publish event-study pre-trends, placebo treatment dates, sensitivity to changing composition and clustered uncertainty. Matching/propensity scores only address measured confounding and do not make last-touch attribution causal.

## Required data capture
Persist target eligibility, policy version, random assignment, assigned channel, actual touch IDs, channel response semantics by effective-dated vendor/disposition version, account/borrower/client/language history, daily exposure balance, payment settlement and reversal links, complaints and full unit costs. Without these fields the “no targeting change” counterfactual remains a hypothesis.
