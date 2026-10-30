-- Point-in-time status snapshot: status must be effective before month start AND
-- known/recorded by month start. Current attributes are deliberately marked as such.
CREATE OR REPLACE VIEW golden.account_month_status AS
WITH months AS (
  SELECT date_trunc('month', MIN(NULLIF(event_at,'')::timestamp))::date AS first_month,
         date_trunc('month', MAX(NULLIF(event_at,'')::timestamp))::date AS last_month
  FROM clean.payments
), month_grid AS (
  SELECT generate_series(first_month, last_month, interval '1 month')::date AS month_start
  FROM months
), account_month AS (
  SELECT a.account_id, m.month_start
  FROM clean.accounts_current a CROSS JOIN month_grid m
), status_asof AS (
  SELECT am.account_id, am.month_start, h.status, h.event_at, h.recorded_at,
         ROW_NUMBER() OVER (PARTITION BY am.account_id, am.month_start
           ORDER BY NULLIF(h.event_at,'')::timestamp DESC NULLS LAST,
                    NULLIF(h.recorded_at,'')::timestamp DESC NULLS LAST,
                    h.history_id DESC) AS rn
  FROM account_month am
  LEFT JOIN clean.account_status_history h
    ON h.account_id=am.account_id
   AND NULLIF(h.event_at,'')::timestamp < am.month_start::timestamp
   AND NULLIF(h.recorded_at,'')::timestamp <= am.month_start::timestamp
), cash AS (
  SELECT account_id, date_trunc('month', NULLIF(event_at,'')::timestamp)::date AS month_start,
         SUM(GREATEST(NULLIF(amount,'')::numeric,0)) FILTER (WHERE UPPER(TRIM(payment_status))='SUCCESS') AS gross_successful_cash,
         COUNT(*) FILTER (WHERE UPPER(TRIM(payment_status))='SUCCESS') AS successful_payment_events
  FROM clean.payments
  GROUP BY 1,2
)
SELECT am.account_id, am.month_start, s.status AS status_at_month_start,
       (s.status IS NOT NULL) AS status_known_at_month_start,
       UPPER(COALESCE(s.status,'')) IN ('ACTIVE','DELINQUENT','NPA','PTP') AS eligible_at_month_start,
       s.event_at AS status_event_at, s.recorded_at AS status_recorded_at,
       a.borrower_id, a.loan_type, a.risk_segment, a.dpd, a.outstanding_amount,
       a.timezone, a.state, a.city,
       COALESCE(c.gross_successful_cash,0) AS gross_successful_cash,
       COALESCE(c.successful_payment_events,0) AS successful_payment_events,
       'CURRENT SNAPSHOT ATTRIBUTES; NOT HISTORICAL'::text AS dimension_timing,
       'OBSERVED STATUS SUBPOPULATION; NO POINT-IN-TIME EXPOSURE'::text AS denominator_limitation
FROM account_month am
LEFT JOIN status_asof s ON s.account_id=am.account_id AND s.month_start=am.month_start AND s.rn=1
LEFT JOIN clean.account_dimension_current a USING (account_id)
LEFT JOIN cash c USING (account_id, month_start);
