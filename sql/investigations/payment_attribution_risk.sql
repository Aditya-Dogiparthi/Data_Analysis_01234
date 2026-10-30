-- Candidate-touch window sensitivity only. Never selects a last touch or assigns
-- payment credit; one touch can fall inside windows for multiple later payments.
WITH windows AS (
  SELECT unnest(ARRAY[1, 7, 30])::integer AS window_days
), touches AS (
  SELECT account_id, NULLIF(event_at,'')::timestamp AS touch_at, 'VOICE'::text AS channel, call_id::text AS touch_id
  FROM clean.calls
  UNION ALL
  SELECT account_id, NULLIF(event_at,'')::timestamp, 'WHATSAPP', whatsapp_event_id::text
  FROM clean.whatsapp_events
  UNION ALL
  SELECT account_id, NULLIF(event_at,'')::timestamp, 'SMS', sms_event_id::text
  FROM clean.sms_events
  UNION ALL
  SELECT account_id, NULLIF(event_at,'')::timestamp, 'FIELD', visit_id::text
  FROM clean.field_visits
), payment_windows AS (
  SELECT p.payment_id, p.account_id,
         date_trunc('month', NULLIF(p.event_at,'')::timestamp)::date AS payment_month,
         GREATEST(NULLIF(p.amount,'')::numeric, 0) AS gross_success_amount,
         w.window_days, COUNT(t.touch_id) AS candidate_touches
  FROM clean.payments p
  CROSS JOIN windows w
  LEFT JOIN touches t
    ON t.account_id=p.account_id
   AND t.touch_at < NULLIF(p.event_at,'')::timestamp
   AND t.touch_at >= NULLIF(p.event_at,'')::timestamp - make_interval(days => w.window_days)
  WHERE UPPER(TRIM(p.payment_status))='SUCCESS'
  GROUP BY 1,2,3,4,5
)
SELECT payment_month, window_days,
       COUNT(*) AS successful_payment_events,
       COUNT(*) FILTER (WHERE candidate_touches > 0) AS payments_with_candidate_touch,
       100.0 * COUNT(*) FILTER (WHERE candidate_touches > 0) / NULLIF(COUNT(*),0) AS payment_touch_coverage_pct,
       SUM(candidate_touches) AS candidate_touch_events,
       SUM(gross_success_amount) AS gross_successful_cash,
       SUM(gross_success_amount) FILTER (WHERE candidate_touches > 0) AS gross_cash_on_touched_payments,
       'NESTED TEMPORAL CANDIDATE WINDOW; NOT ATTRIBUTION OR CAUSAL CREDIT'::text AS limitation
FROM payment_windows
GROUP BY 1,2
ORDER BY 1,2;
