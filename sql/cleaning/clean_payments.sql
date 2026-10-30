-- PostgreSQL-compatible, non-destructive payment cleaning.
-- List business payload columns explicitly: raw.* also carries ingestion metadata,
-- which must never prevent exact source-row deduplication.
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS quarantine;

CREATE OR REPLACE VIEW clean.payments_exact_dedup AS
SELECT DISTINCT payment_id, account_id, borrower_id, event_at, payment_reference,
       amount, payment_status, payment_method, provider_id
FROM raw.payments;

CREATE OR REPLACE VIEW quarantine.payment_id_conflicts AS
SELECT p.*
FROM clean.payments_exact_dedup p
JOIN (
  SELECT payment_id
  FROM clean.payments_exact_dedup
  GROUP BY payment_id
  HAVING COUNT(*) > 1
) c USING (payment_id);

CREATE OR REPLACE VIEW clean.payments AS
SELECT p.*
FROM clean.payments_exact_dedup p
WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.payment_id_conflicts q WHERE q.payment_id=p.payment_id
);

-- Repeated payment_reference values are review candidates, not deduplication keys.
CREATE OR REPLACE VIEW quarantine.repeated_payment_references AS
SELECT payment_reference, COUNT(*) AS rows,
       COUNT(DISTINCT account_id) AS account_count,
       COUNT(DISTINCT (account_id, amount, payment_status)) AS business_payload_count
FROM clean.payments_exact_dedup
WHERE NULLIF(payment_reference,'') IS NOT NULL
GROUP BY payment_reference
HAVING COUNT(*) > 1;
