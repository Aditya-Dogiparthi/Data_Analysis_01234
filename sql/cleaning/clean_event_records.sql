-- Explicit source-column views: ingestion metadata is excluded from business-payload equality.
-- Identical source payloads are deduplicated; all conflicting stable IDs are quarantined.

CREATE OR REPLACE VIEW clean.calls_exact_dedup AS
SELECT DISTINCT call_id, account_id, borrower_id, event_at, agent_id, campaign_id,
       direction, vendor_id, call_status, duration_sec, timezone
FROM raw.calls;
CREATE OR REPLACE VIEW quarantine.call_id_conflicts AS
SELECT d.* FROM clean.calls_exact_dedup d
JOIN (SELECT call_id FROM clean.calls_exact_dedup GROUP BY call_id HAVING COUNT(*) > 1) x USING (call_id);
CREATE OR REPLACE VIEW clean.calls AS
SELECT d.* FROM clean.calls_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.call_id_conflicts q WHERE q.call_id=d.call_id);

CREATE OR REPLACE VIEW clean.call_attempts_exact_dedup AS
SELECT DISTINCT attempt_id, account_id, borrower_id, event_at, call_id, agent_id,
       attempt_no, vendor_id, attempt_status FROM raw.call_attempts;
CREATE OR REPLACE VIEW quarantine.call_attempt_id_conflicts AS
SELECT d.* FROM clean.call_attempts_exact_dedup d
JOIN (SELECT attempt_id FROM clean.call_attempts_exact_dedup GROUP BY attempt_id HAVING COUNT(*) > 1) x USING (attempt_id);
CREATE OR REPLACE VIEW clean.call_attempts AS
SELECT d.* FROM clean.call_attempts_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.call_attempt_id_conflicts q WHERE q.attempt_id=d.attempt_id);

CREATE OR REPLACE VIEW clean.call_dispositions_exact_dedup AS
SELECT DISTINCT disposition_id, account_id, borrower_id, event_at, call_id,
       agent_id, disposition_code, disposition_version FROM raw.call_dispositions;
CREATE OR REPLACE VIEW quarantine.call_disposition_id_conflicts AS
SELECT d.* FROM clean.call_dispositions_exact_dedup d
JOIN (SELECT disposition_id FROM clean.call_dispositions_exact_dedup GROUP BY disposition_id HAVING COUNT(*) > 1) x USING (disposition_id);
CREATE OR REPLACE VIEW clean.call_dispositions AS
SELECT d.* FROM clean.call_dispositions_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.call_disposition_id_conflicts q WHERE q.disposition_id=d.disposition_id);

CREATE OR REPLACE VIEW clean.whatsapp_events_exact_dedup AS
SELECT DISTINCT whatsapp_event_id, account_id, borrower_id, event_at, message_id,
       event_type, template_code, provider_id FROM raw.whatsapp_events;
CREATE OR REPLACE VIEW quarantine.whatsapp_event_id_conflicts AS
SELECT d.* FROM clean.whatsapp_events_exact_dedup d
JOIN (SELECT whatsapp_event_id FROM clean.whatsapp_events_exact_dedup GROUP BY whatsapp_event_id HAVING COUNT(*) > 1) x USING (whatsapp_event_id);
CREATE OR REPLACE VIEW clean.whatsapp_events AS
SELECT d.* FROM clean.whatsapp_events_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.whatsapp_event_id_conflicts q WHERE q.whatsapp_event_id=d.whatsapp_event_id);

CREATE OR REPLACE VIEW clean.sms_events_exact_dedup AS
SELECT DISTINCT sms_event_id, account_id, borrower_id, event_at, message_id,
       event_type, template_code, provider_id FROM raw.sms_events;
CREATE OR REPLACE VIEW quarantine.sms_event_id_conflicts AS
SELECT d.* FROM clean.sms_events_exact_dedup d
JOIN (SELECT sms_event_id FROM clean.sms_events_exact_dedup GROUP BY sms_event_id HAVING COUNT(*) > 1) x USING (sms_event_id);
CREATE OR REPLACE VIEW clean.sms_events AS
SELECT d.* FROM clean.sms_events_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.sms_event_id_conflicts q WHERE q.sms_event_id=d.sms_event_id);

CREATE OR REPLACE VIEW clean.field_visits_exact_dedup AS
SELECT DISTINCT visit_id, account_id, borrower_id, event_at, agent_id,
       visit_type, outcome, latitude, longitude, scheduled_at FROM raw.field_visits;
CREATE OR REPLACE VIEW quarantine.field_visit_id_conflicts AS
SELECT d.* FROM clean.field_visits_exact_dedup d
JOIN (SELECT visit_id FROM clean.field_visits_exact_dedup GROUP BY visit_id HAVING COUNT(*) > 1) x USING (visit_id);
CREATE OR REPLACE VIEW clean.field_visits AS
SELECT d.* FROM clean.field_visits_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.field_visit_id_conflicts q WHERE q.visit_id=d.visit_id);

CREATE OR REPLACE VIEW clean.promises_to_pay_exact_dedup AS
SELECT DISTINCT ptp_id, account_id, borrower_id, event_at, agent_id,
       promised_amount, promised_date, status, source FROM raw.promises_to_pay;
CREATE OR REPLACE VIEW quarantine.ptp_id_conflicts AS
SELECT d.* FROM clean.promises_to_pay_exact_dedup d
JOIN (SELECT ptp_id FROM clean.promises_to_pay_exact_dedup GROUP BY ptp_id HAVING COUNT(*) > 1) x USING (ptp_id);
CREATE OR REPLACE VIEW clean.promises_to_pay AS
SELECT d.* FROM clean.promises_to_pay_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.ptp_id_conflicts q WHERE q.ptp_id=d.ptp_id);

CREATE OR REPLACE VIEW clean.account_status_history AS
SELECT DISTINCT history_id, account_id, borrower_id, event_at, status,
       changed_by, source, recorded_at FROM raw.account_status_history;

-- Additional supporting sources. Keep their raw schema versions in the source record;
-- source-level event contracts should be versioned as mappings are approved.
CREATE OR REPLACE VIEW clean.daily_targeting_exact_dedup AS
SELECT DISTINCT target_id, account_id, campaign_id, target_date, priority, recommended_channel, status
FROM raw.daily_targeting;
CREATE OR REPLACE VIEW quarantine.daily_target_id_conflicts AS
SELECT d.* FROM clean.daily_targeting_exact_dedup d
JOIN (SELECT target_id FROM clean.daily_targeting_exact_dedup GROUP BY target_id HAVING COUNT(*) > 1) x USING (target_id);
CREATE OR REPLACE VIEW clean.daily_targeting AS
SELECT d.* FROM clean.daily_targeting_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.daily_target_id_conflicts q WHERE q.target_id=d.target_id);

CREATE OR REPLACE VIEW clean.campaigns AS
SELECT DISTINCT campaign_id, campaign_name, channel, strategy_version,
       start_at, target_definition, end_at FROM raw.campaigns;
CREATE OR REPLACE VIEW clean.vendor_telephony AS
SELECT DISTINCT vendor_id, vendor_name, vendor_account_id, timezone, status, schema_version
FROM raw.vendor_telephony;

CREATE OR REPLACE VIEW clean.account_status_history_exact_dedup AS
SELECT DISTINCT history_id, account_id, borrower_id, event_at, status,
       changed_by, source, recorded_at FROM raw.account_status_history;
CREATE OR REPLACE VIEW quarantine.account_status_history_id_conflicts AS
SELECT d.* FROM clean.account_status_history_exact_dedup d
JOIN (SELECT history_id FROM clean.account_status_history_exact_dedup GROUP BY history_id HAVING COUNT(*) > 1) x USING (history_id);
CREATE OR REPLACE VIEW clean.account_status_history AS
SELECT d.* FROM clean.account_status_history_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.account_status_history_id_conflicts q WHERE q.history_id=d.history_id);

CREATE OR REPLACE VIEW clean.agent_sessions_exact_dedup AS
SELECT DISTINCT session_id, agent_id, login_at, channel, device_id, timezone, logout_at
FROM raw.agent_sessions;
CREATE OR REPLACE VIEW quarantine.agent_session_id_conflicts AS
SELECT d.* FROM clean.agent_sessions_exact_dedup d
JOIN (SELECT session_id FROM clean.agent_sessions_exact_dedup GROUP BY session_id HAVING COUNT(*) > 1) x USING (session_id);
CREATE OR REPLACE VIEW clean.agent_sessions AS
SELECT d.* FROM clean.agent_sessions_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.agent_session_id_conflicts q WHERE q.session_id=d.session_id);

CREATE OR REPLACE VIEW clean.complaints_exact_dedup AS
SELECT DISTINCT complaint_id, account_id, borrower_id, event_at, complaint_type,
       severity, status, source, resolution_at FROM raw.complaints;
CREATE OR REPLACE VIEW quarantine.complaint_id_conflicts AS
SELECT d.* FROM clean.complaints_exact_dedup d
JOIN (SELECT complaint_id FROM clean.complaints_exact_dedup GROUP BY complaint_id HAVING COUNT(*) > 1) x USING (complaint_id);
CREATE OR REPLACE VIEW clean.complaints AS
SELECT d.* FROM clean.complaints_exact_dedup d
WHERE NOT EXISTS (SELECT 1 FROM quarantine.complaint_id_conflicts q WHERE q.complaint_id=d.complaint_id);
