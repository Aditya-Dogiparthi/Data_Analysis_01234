-- Current snapshot dimensions are for descriptive drilldowns only. They must not be
-- treated as historically valid segment values. Preserve superseded source records in raw.
CREATE OR REPLACE VIEW clean.accounts_current AS
SELECT DISTINCT account_id, borrower_id, loan_type, principal_amount, outstanding_amount,
       dpd, risk_segment, status, opened_at, timezone, schema_version
FROM raw.accounts;

CREATE OR REPLACE VIEW quarantine.borrower_superseded_versions AS
WITH d AS (
  SELECT DISTINCT borrower_id, name, phone, email, city, created_at, updated_at, state
  FROM raw.borrowers
), r AS (
  SELECT d.*, ROW_NUMBER() OVER (PARTITION BY borrower_id
      ORDER BY NULLIF(updated_at,'')::timestamp DESC NULLS LAST,
               NULLIF(created_at,'')::timestamp DESC NULLS LAST) AS version_rank
  FROM d
)
SELECT * FROM r WHERE version_rank > 1;

CREATE OR REPLACE VIEW clean.borrowers_current AS
WITH d AS (
  SELECT DISTINCT borrower_id, name, phone, email, city, created_at, updated_at, state
  FROM raw.borrowers
), r AS (
  SELECT d.*, ROW_NUMBER() OVER (PARTITION BY borrower_id
      ORDER BY NULLIF(updated_at,'')::timestamp DESC NULLS LAST,
               NULLIF(created_at,'')::timestamp DESC NULLS LAST) AS version_rank
  FROM d
)
SELECT borrower_id, name, phone, email, city, created_at, updated_at, state
FROM r WHERE version_rank=1;

CREATE OR REPLACE VIEW quarantine.agent_superseded_versions AS
WITH d AS (
  SELECT DISTINCT agent_id, employee_code, agent_name, vendor_id, team, status, joined_at, updated_at
  FROM raw.agents
), r AS (
  SELECT d.*, ROW_NUMBER() OVER (PARTITION BY agent_id
      ORDER BY NULLIF(updated_at,'')::timestamp DESC NULLS LAST,
               NULLIF(joined_at,'')::timestamp DESC NULLS LAST) AS version_rank
  FROM d
)
SELECT * FROM r WHERE version_rank > 1;

CREATE OR REPLACE VIEW clean.agents_current AS
WITH d AS (
  SELECT DISTINCT agent_id, employee_code, agent_name, vendor_id, team, status, joined_at, updated_at
  FROM raw.agents
), r AS (
  SELECT d.*, ROW_NUMBER() OVER (PARTITION BY agent_id
      ORDER BY NULLIF(updated_at,'')::timestamp DESC NULLS LAST,
               NULLIF(joined_at,'')::timestamp DESC NULLS LAST) AS version_rank
  FROM d
)
SELECT agent_id, employee_code, agent_name, vendor_id, team, status, joined_at, updated_at
FROM r WHERE version_rank=1;

CREATE OR REPLACE VIEW clean.account_dimension_current AS
SELECT a.*, b.city, b.state
FROM clean.accounts_current a
LEFT JOIN clean.borrowers_current b USING (borrower_id);
