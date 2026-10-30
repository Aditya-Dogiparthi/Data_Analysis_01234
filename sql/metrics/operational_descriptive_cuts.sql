-- 1) Calls by campaign and vendor: technical answered is not verified RPC.
SELECT date_trunc('month',event_ts_source)::date AS month,
       campaign_id, vendor_id, vendor_name, vendor_schema_version,
       COUNT(*) AS calls,
       COUNT(*) FILTER (WHERE call_status_norm='ANSWERED') AS technical_answered,
       COUNT(DISTINCT account_id) AS accounts,
       AVG(duration_sec) AS mean_duration_sec,
       'NO RPC MAP; NO PAYMENT ATTRIBUTION'::text AS limitation
FROM golden.call_events
GROUP BY 1,2,3,4,5
ORDER BY 1,2,3;

-- 2) Calls by source-recorded hour. Do not call this borrower-local hour.
SELECT call_timezone, source_recorded_hour, call_status_norm,
       COUNT(*) AS calls, COUNT(DISTINCT account_id) AS accounts,
       'EVENT_AT HOUR AS STORED; TIMEZONE SEMANTICS NOT CERTIFIED'::text AS limitation
FROM golden.call_events
GROUP BY 1,2,3 ORDER BY 1,2,3;

-- 3) Attempt frequency by the full observed month-start eligible population.
-- Zero-attempt eligible accounts remain in the denominator; intensity is selected, not causal.
WITH attempts AS (
  SELECT account_id, date_trunc('month',event_ts_source)::date AS month,
         COUNT(*) AS attempts
  FROM golden.call_attempt_events GROUP BY 1,2
), base AS (
  SELECT account_id, month_start AS month, gross_successful_cash AS gross_cash
  FROM golden.account_month_status
  WHERE eligible_at_month_start
), banded AS (
  SELECT b.account_id, b.month, b.gross_cash, COALESCE(a.attempts,0) AS attempts,
         CASE WHEN COALESCE(a.attempts,0)=0 THEN '0'
              WHEN a.attempts=1 THEN '1'
              WHEN a.attempts BETWEEN 2 AND 3 THEN '2-3' ELSE '4+' END AS attempt_band
  FROM base b LEFT JOIN attempts a USING(account_id,month)
)
SELECT month, attempt_band, COUNT(DISTINCT account_id) AS eligible_accounts,
       COUNT(DISTINCT account_id) FILTER (WHERE COALESCE(gross_cash,0)>0) AS paying_accounts,
       SUM(COALESCE(gross_cash,0)) AS gross_cash,
       'OBSERVED MONTH-START ELIGIBLE SUBPOPULATION; ATTEMPT INTENSITY IS NOT RANDOMIZED'::text AS limitation
FROM banded
GROUP BY 1,2 ORDER BY 1,2;

-- 4) Field, WhatsApp and SMS event volume. Volume is not conversion.
SELECT date_trunc('month',NULLIF(event_at,'')::timestamp)::date AS month,
       'WHATSAPP'::text AS channel, COUNT(*) AS events,
       COUNT(DISTINCT account_id) AS event_accounts
FROM clean.whatsapp_events GROUP BY 1
UNION ALL
SELECT date_trunc('month',NULLIF(event_at,'')::timestamp)::date,
       'SMS', COUNT(*), COUNT(DISTINCT account_id)
FROM clean.sms_events GROUP BY 1
UNION ALL
SELECT date_trunc('month',NULLIF(event_at,'')::timestamp)::date,
       'FIELD', COUNT(*), COUNT(DISTINCT account_id)
FROM clean.field_visits GROUP BY 1
ORDER BY 1,2;
