-- A one-row-per-clean-call fact. Current agent/vendor labels are descriptive snapshots.
CREATE OR REPLACE VIEW golden.call_events AS
SELECT c.call_id, c.account_id, c.borrower_id,
       NULLIF(c.event_at,'')::timestamp AS event_ts_source,
       c.agent_id, a.employee_code, a.team,
       c.campaign_id, c.direction,
       c.vendor_id, v.vendor_name, v.schema_version AS vendor_schema_version,
       UPPER(TRIM(c.call_status)) AS call_status_norm,
       NULLIF(c.duration_sec,'')::numeric AS duration_sec,
       c.timezone AS call_timezone,
       EXTRACT(HOUR FROM NULLIF(c.event_at,'')::timestamp)::int AS source_recorded_hour,
       'SOURCE TIMESTAMP SEMANTICS NOT CERTIFIED; TECHNICAL ANSWER IS NOT RPC'::text AS limitation
FROM clean.calls c
LEFT JOIN clean.agents_current a USING (agent_id)
LEFT JOIN raw.vendor_telephony v USING (vendor_id);

CREATE OR REPLACE VIEW golden.call_attempt_events AS
SELECT a.attempt_id, a.account_id, a.borrower_id,
       NULLIF(a.event_at,'')::timestamp AS event_ts_source,
       a.call_id, a.agent_id, a.vendor_id,
       NULLIF(a.attempt_no,'')::int AS attempt_no,
       UPPER(TRIM(a.attempt_status)) AS attempt_status_norm
FROM clean.call_attempts a;
