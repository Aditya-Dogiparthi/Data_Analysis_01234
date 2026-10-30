-- Month-start account-count proxy. Status must be effective before month start AND
-- known/recorded by month start. Incomplete status coverage is kept visible.
WITH monthly AS (
  SELECT month_start,
         COUNT(*) FILTER (WHERE status_known_at_month_start) AS known_accounts,
         COUNT(*) FILTER (WHERE eligible_at_month_start) AS eligible_accounts,
         COUNT(*) AS account_snapshot_size,
         SUM(gross_successful_cash) FILTER (WHERE eligible_at_month_start) AS gross_cash_from_observed_eligible
  FROM golden.account_month_status
  GROUP BY month_start
)
SELECT month_start,
       account_snapshot_size,
       known_accounts,
       100.0 * known_accounts / NULLIF(account_snapshot_size,0) AS start_status_coverage_pct,
       eligible_accounts,
       gross_cash_from_observed_eligible,
       gross_cash_from_observed_eligible / NULLIF(eligible_accounts,0) AS gross_cash_per_observed_eligible_account,
       'ACCOUNT-COUNT PROXY ONLY; NOT EXPOSURE-WEIGHTED NET RECOVERY'::text AS metric_limitation
FROM monthly
ORDER BY month_start;
