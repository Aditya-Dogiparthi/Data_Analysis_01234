-- 1) Primary-key conflict checks. Each result set should be empty for clean golden keys.
SELECT payment_id, COUNT(*) AS payload_versions
FROM clean.payments_exact_dedup GROUP BY payment_id HAVING COUNT(*) > 1;

SELECT call_id, COUNT(*) AS payload_versions
FROM clean.calls_exact_dedup GROUP BY call_id HAVING COUNT(*) > 1;

SELECT attempt_id, COUNT(*) AS payload_versions
FROM clean.call_attempts_exact_dedup GROUP BY attempt_id HAVING COUNT(*) > 1;

-- 2) Referential integrity: unresolved account IDs by source.
SELECT 'payments' AS source, COUNT(*) AS orphan_rows
FROM clean.payments p LEFT JOIN clean.accounts_current a USING(account_id)
WHERE a.account_id IS NULL
UNION ALL
SELECT 'calls', COUNT(*)
FROM clean.calls c LEFT JOIN clean.accounts_current a USING(account_id)
WHERE a.account_id IS NULL
UNION ALL
SELECT 'daily_targeting', COUNT(*)
FROM clean.daily_targeting t LEFT JOIN clean.accounts_current a USING(account_id)
WHERE a.account_id IS NULL;

-- 3) Invalid or unmapped statuses are visible; do not silently classify.
SELECT UPPER(TRIM(payment_status)) AS payment_status, COUNT(*) AS rows
FROM clean.payments GROUP BY 1 ORDER BY 2 DESC;

SELECT disposition_version, UPPER(TRIM(disposition_code)) AS disposition_code, COUNT(*) AS rows
FROM clean.call_dispositions GROUP BY 1,2 ORDER BY 1,2;

-- 4) Timestamp parse failures and recorded-before-event diagnostics.
SELECT COUNT(*) FILTER (WHERE NULLIF(event_at,'') IS NULL) AS missing_event_at,
       COUNT(*) FILTER (WHERE NULLIF(recorded_at,'') IS NULL) AS missing_recorded_at,
       COUNT(*) FILTER (WHERE NULLIF(recorded_at,'')::timestamp < NULLIF(event_at,'')::timestamp) AS negative_recorded_event_lag
FROM clean.account_status_history;
