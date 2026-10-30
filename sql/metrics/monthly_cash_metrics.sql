-- Financial event measure, not net settled recovery. REVERSED amounts are not
-- arbitrarily netted because the source has no reliable original-payment key.
SELECT date_trunc('month', NULLIF(event_at,'')::timestamp)::date AS event_month,
       COUNT(*) FILTER (WHERE UPPER(TRIM(payment_status))='SUCCESS') AS successful_payment_events,
       SUM(GREATEST(NULLIF(amount,'')::numeric,0)) FILTER
         (WHERE UPPER(TRIM(payment_status))='SUCCESS') AS gross_successful_collections,
       COUNT(*) FILTER (WHERE UPPER(TRIM(payment_status))='REVERSED') AS reversal_events,
       SUM(GREATEST(NULLIF(amount,'')::numeric,0)) FILTER
         (WHERE UPPER(TRIM(payment_status))='REVERSED') AS reversal_amount_reported_separately
FROM clean.payments
WHERE NULLIF(event_at,'') IS NOT NULL
GROUP BY 1 ORDER BY 1;
