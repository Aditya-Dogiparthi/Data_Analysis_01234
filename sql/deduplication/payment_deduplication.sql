-- Never deduplicate on amount + timestamp alone: legitimate repeated payments exist.
-- This query reports exact duplicate payloads and conflicting stable identifiers.
SELECT payment_id, COUNT(*) AS rows_per_id,
       COUNT(DISTINCT (account_id, borrower_id, event_at, payment_reference,
                       amount, payment_status, payment_method, provider_id)) AS payload_versions
FROM raw.payments
GROUP BY payment_id
HAVING COUNT(*) > 1
ORDER BY rows_per_id DESC;

-- Duplicate reference review only; references may be reused by providers and are not
-- independently safe as a global deduplication key.
SELECT payment_reference, COUNT(*) AS rows,
       COUNT(DISTINCT (account_id, amount, payment_status)) AS distinct_business_events
FROM raw.payments
GROUP BY payment_reference
HAVING COUNT(*) > 1
ORDER BY rows DESC;
