-- Current snapshot distribution is not historical eligible exposure.
SELECT UPPER(TRIM(status)) AS current_status,
       COUNT(*) AS current_accounts,
       SUM(NULLIF(outstanding_amount,'')::numeric) AS current_outstanding_amount
FROM clean.accounts_current
GROUP BY 1 ORDER BY 2 DESC;

-- Historical denominator coverage and start-vs-end survivor comparison.
SELECT month_start,
       COUNT(*) AS accounts_in_snapshot,
       COUNT(*) FILTER (WHERE status_known_at_month_start) AS accounts_with_known_start_status,
       100.0 * COUNT(*) FILTER (WHERE status_known_at_month_start) / NULLIF(COUNT(*),0) AS start_status_coverage_pct,
       COUNT(*) FILTER (WHERE eligible_at_month_start) AS eligible_at_start,
       COUNT(*) FILTER (WHERE UPPER(COALESCE(status_at_month_end,'')) IN ('ACTIVE','DELINQUENT','NPA','PTP')) AS eligible_at_end,
       COUNT(*) FILTER (WHERE eligible_at_month_start AND UPPER(COALESCE(status_at_month_end,'')) IN ('PAID','CLOSED','WRITEOFF')) AS start_eligible_now_paid_closed_writeoff,
       SUM(gross_successful_cash) FILTER (WHERE eligible_at_month_start) AS cash_from_observed_start_eligible
FROM golden.account_month_status
GROUP BY month_start ORDER BY month_start;
