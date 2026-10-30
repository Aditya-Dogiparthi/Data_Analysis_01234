# Assumptions and Limitations

- The supplied dataset is synthetic (seed 42), per source README.
- Data does not cover 12 complete months; event data ends 8 Aug 2026.
- No original definition for the reported 11% KPI was supplied.
- Account status history supports a provisional account-count monthly population; balances are not historically versioned.
- Eligible statuses used for the provisional panel: ACTIVE, DELINQUENT, NPA, PTP.
- Account DPD/risk/loan type and borrower geography are current snapshots, not point-in-time attributes.
- Payments have no row-level timezone field. No UTC conversion is guessed.
- Reversal rows are not netted without explicit original transaction linkage.
- Campaign strategy assignment is observational and may overlap at account level.
- No channel, agent, vendor, field or technology cost ledger was supplied.
- No ROI, causal counterfactual, or verified net recovery rate is claimed.
