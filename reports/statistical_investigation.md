# Statistical Investigation

## Time-series result: the apparent +11% is one cash-event move, not a sustained recovery trend

| Month | Gross successful cash (₹ Cr) | MoM change | Period status |
|---|---:|---:|---|
| Jan 2026 | 18.72 | — | Complete |
| Feb 2026 | 17.00 | -9.20% | Complete |
| Mar 2026 | 18.86 | +10.96% | Complete |
| Apr 2026 | 17.50 | -7.20% | Complete |
| May 2026 | 18.42 | +5.21% | Complete |
| Jun 2026 | 17.53 | -4.83% | Complete |
| Jul 2026 | 18.72 | +6.83% | Complete |
| Aug 2026 | 4.71 | Not comparable | Partial through 8 Aug |

January and July gross cash differ by **+0.004%**. Average arithmetic month-on-month change across the six comparable transitions Feb–Jul is **+0.29%**. The only +11%-like transition is February→March (+10.96%), followed by a decline in April. This is a cash-event series, not an amount-weighted or net recovery rate.

## Mix and segment effects

- **Risk mix:** a fixed-February risk-segment weighting proxy is produced for February–August. For the February→March transition, the observed gross cash per start-eligible account proxy rose 9.20%; the fixed risk-mix proxy rose about 9.27%. That small similarity suggests this particular current-risk weighting does not explain the February→March movement, but it is not historical point-in-time standardization and not exposure-weighted.
- **Within-segment divergence:** February→March saw 3 of 4 current risk segments and 4 of 5 DPD buckets increase in gross cash per observed eligible account; LOW risk fell 14.75%, and the 91–180 DPD bucket fell 23.46%. By loan type, 3 of 5 groups declined even though the aggregate account-count proxy rose; by state, 5 of 10 categories (including unknown) were down. This is a Simpson-style warning that aggregate movement masks heterogeneous subgroup results, **not proof of a strict Simpson's paradox**.
- **Formal screen:** `data/golden/simpsons_paradox_pair_summary.csv` tests month-pair direction changes by current risk segment, DPD, loan type and state. It flags an aggregate-up / majority-segments-down pattern for loan type in February→March, but no strict all-segment reversal. Because the dimensions are current snapshots and the observed population is incomplete, no historical Simpson's paradox conclusion is claimed.
- **Cohort:** account-opening-month vintage cohorts are built. Historical exposure, eligibility and segment attributes at cohort entry are incomplete, so vintage differences are descriptive rather than causal.
- **Portfolio mix:** loan type, risk, DPD, state and city are available only from current snapshots. The source has no historical client or language dimension. The separate borrower-segment field is unavailable; current account `risk_segment` is only a proxy.

## Selection, survivorship and attribution bias

- **Selection bias:** daily targeting and campaigns are non-random. Higher cash among targeted accounts may reflect higher starting risk, priority, outstanding balance or prior payment propensity. No regression on these observed fields can remove unobserved selection.
- **Survivorship bias:** month-end status can exclude accounts that paid, closed or were written off during the month. Start-of-month status known before the period begins is the correct temporal ordering, but coverage is 0.0% in January, 24.17% in February and 85.62% in August. It is not a full-portfolio denominator.
- **Attribution-window bias:** changing only the preceding look-back changes the share of successful payments with any candidate touch from **3.24% at 1 day** (568/17,523) to **20.16% at 7 days** (3,533/17,523) to **59.76% at 30 days** (10,471/17,523). The share of gross cash on payments with at least one candidate touch moves from 3.19% to 20.18% to 59.97%. For the seven-day window, 13,990 payments have zero candidate touches, 3,132 have one and 401 have 2–5. See `data/golden/payment_touch_window_sensitivity.csv`. The 30-day window captures over 56 percentage points more payments than the 1-day window, showing that an arbitrary attribution window can dominate apparent channel reach. This is temporal proximity only: one account can have multiple channels, one touch can be near multiple payments, and the source has no payment-to-touch ID.
- **Time-series effects:** only seven complete months exist. No seasonality or trend model is fit to such a short series. August is excluded from comparable month-on-month movement. Bootstrap intervals on the observed account-month proxy do not repair denominator coverage or historical exposure gaps.

## Operational driver review

| Requested driver | What is available | Evidence classification / limitation |
|---|---|---|
| Portfolio mix | Current risk, DPD, loan type, opening vintage, geography | **Correlation**; not point-in-time or exposure-weighted |
| Client | No `client_id` or client history | **Unavailable** |
| Language | No language preference | **Unavailable** |
| Borrower segment | No separate borrower segment; account `risk_segment` only | **Partial proxy / correlation** |
| Agent | Current agent snapshot, agent IDs and employee-code aliases | **Correlation**; historical identity not resolved |
| Agent tenure | Call outcomes by tenure band | **Correlation**; answered is not RPC and payments are not agent-linked |
| Campaign / targeting | Campaign and targeting strategy versions | **Correlation**; strategy assignment overlaps and is non-random |
| Channel | Call, WhatsApp, SMS and field activity volumes | **Activity only**; no linked conversion |
| Telephony vendor | Vendor IDs/names and schema versions v1–v3 | **Correlation**; semantic code changes are not established |
| Calling time | Source-recorded hour and timezone labels | **Correlation**; timestamp storage semantics are uncertified |
| Attempt frequency | Account/month attempt bands and cash outcomes | **Correlation**; intensity is selected, not randomized |
| PTP | PTP source status and maturity diagnostics | **Source status only**; payments have no `ptp_id` link |

## Evidence classification

- **FACT:** source inventory and date coverage; gross successful payment totals; reversal amounts separately; duplicate/conflict counts; status-history coverage; agent version/alias counts; timestamp-quality diagnostics; missing fields and cost ledger.
- **STRONG EVIDENCE:** the current gross-cash series does not show sustained +11% growth; month-end status is outcome-dependent; a many-version agent join would inflate activity; no historical amount denominator exists.
- **CORRELATION:** current segment, vintage, geography, campaign, channel, vendor, calling-hour, attempt-frequency, tenure and targeting-strategy differences.
- **HYPOTHESIS:** an operational change caused any movement in true recovery rate; targeting/channel/vendor changes generated incremental net cash.

The assignment's causal driver question is not identified by these data. See `reports/counterfactual_design.md` for the experiment required to estimate targeting lift.
