-- Descriptive screen for aggregate-vs-segment directional divergence.
-- Current account attributes and incomplete observed-status denominators mean this
-- cannot establish historical Simpson's paradox or a causal mix effect.
WITH segment_month AS (
  SELECT month_start, risk_segment AS segment,
         COUNT(DISTINCT account_id) FILTER (WHERE eligible_at_month_start) AS eligible_accounts,
         SUM(gross_successful_cash) FILTER (WHERE eligible_at_month_start) AS gross_cash
  FROM golden.account_month_status
  GROUP BY 1,2
), rates AS (
  SELECT *, gross_cash / NULLIF(eligible_accounts,0) AS cash_per_eligible
  FROM segment_month
), changes AS (
  SELECT curr.segment, prev.month_start AS previous_month, curr.month_start AS current_month,
         prev.cash_per_eligible AS previous_cash_per_eligible,
         curr.cash_per_eligible AS current_cash_per_eligible,
         100.0 * (curr.cash_per_eligible / NULLIF(prev.cash_per_eligible,0)-1) AS segment_change_pct
  FROM rates curr
  JOIN rates prev ON prev.segment=curr.segment
    AND prev.month_start=curr.month_start - interval '1 month'
)
SELECT *, 'CURRENT SNAPSHOT; OBSERVED ACCOUNT-COUNT DENOMINATOR; SCREEN ONLY'::text AS limitation
FROM changes ORDER BY previous_month, segment;
