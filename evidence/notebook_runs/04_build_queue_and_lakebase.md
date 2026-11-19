# Run evidence: `04_build_queue_and_lakebase`

- Job run id: `489599535356057` · task run id: `task` · exported from Databricks job run (serverless)

# 04 · Underwriting queue (Delta → Lakebase) + Workbench operational tables
* Builds `ml_lend_ml.underwriting_queue`: the **Summit Valley CU** slice of open applications that need a human,
  enriched with AI-verified income, EPD model score + reason codes and the latest AI-classified note.
  PII is minimized at the source: SSN is stored as last-4 only.
* Creates the Workbench OLTP schema in **Lakebase** (`lending.workbench`): decisions, live applications, audit.
  Decisions flow back to the lakehouse through Lakebase change-data-feed (CDF) into `ml_lend_ops`.

```python
%pip install "psycopg[binary]==3.2.3" -q
```

**Output:**
```text
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
CAT = "demo_dnb_catalog"; TENANT = "CU-SVCU"
spark.sql(f"""
CREATE OR REPLACE TABLE {CAT}.ml_lend_ml.underwriting_queue
COMMENT 'Open applications awaiting an underwriter at Summit Valley CU, with AI income verification, EPD risk score and reason codes. Source of the Lakebase synced table used by the Lending Intelligence Workbench app.'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
AS
WITH cur AS (SELECT * FROM {CAT}.ml_lend_silver.members WHERE __END_AT IS NULL),
     note AS (SELECT application_id, max_by(note_text, created_ts) latest_note, max_by(note_category, created_ts) latest_note_category
              FROM {CAT}.ml_lend_silver.member_notes GROUP BY application_id)
SELECT a.application_id, a.institution_id, a.member_id,
       concat(m.first_name, ' ', m.last_name) AS member_name, concat('XXX-XX-', right(m.ssn, 4)) AS ssn_last4,
       m.employer_name AS stated_employer, m.credit_score, a.product_code, a.channel, a.dealer_id, a.branch_id,
       a.requested_amount, a.term_months, a.stated_monthly_income, a.submitted_ts,
       d.verified_monthly_income AS ai_verified_monthly_income, d.employer_name AS ai_employer_name, d.pay_frequency_raw AS ai_pay_frequency,
       d.doc_path, round((a.stated_monthly_income - d.verified_monthly_income)/nullif(d.verified_monthly_income,0), 3) AS ai_income_variance_pct,
       (d.verified_monthly_income IS NOT NULL AND a.stated_monthly_income > d.verified_monthly_income*1.2) AS ai_income_mismatch_flag,
       s.epd_probability, s.risk_band, s.reason_1, s.reason_2, s.reason_3, s.model_version,
       n.latest_note, n.latest_note_category,
       CASE WHEN d.verified_monthly_income IS NOT NULL AND a.stated_monthly_income > d.verified_monthly_income*1.2 THEN 'INCOME_MISMATCH'
            WHEN s.risk_band = 'HIGH' THEN 'HIGH_RISK'
            WHEN a.product_code = 'HELOC' THEN 'PRODUCT_POLICY'
            ELSE 'STANDARD_REVIEW' END AS routing_reason,
       'AWAITING_UNDERWRITER' AS queue_status
FROM {CAT}.ml_lend_silver.applications a
JOIN cur m USING (member_id)
LEFT JOIN {CAT}.ml_lend_silver.document_income_extraction d USING (application_id)
LEFT JOIN {CAT}.ml_lend_ml.application_risk_scores s USING (application_id)
LEFT JOIN note n USING (application_id)
WHERE a.application_status = 'PENDING' AND a.institution_id = '{TENANT}'
""")
display(spark.sql(f"SELECT routing_reason, risk_band, count(*) n FROM {CAT}.ml_lend_ml.underwriting_queue GROUP BY ALL"))
```

**Output:**
```text
| routing_reason | risk_band | n |
|---|---|---|
| STANDARD_REVIEW | LOW | 2 |
| PRODUCT_POLICY | LOW | 1 |
| HIGH_RISK | HIGH | 7 |
| STANDARD_REVIEW | MEDIUM | 4 |
| PRODUCT_POLICY | MEDIUM | 2 |
```

```python
import psycopg, requests
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
EP = "projects/meridianlink-lending/branches/production/endpoints/primary"
host = [e for e in w.api_client.do("GET", "/api/2.0/postgres/projects/meridianlink-lending/branches/production/endpoints")["endpoints"]][0]["status"]["hosts"]["host"]
tok = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": EP})["token"]
user = w.current_user.me().user_name
conn = psycopg.connect(host=host, dbname="lending", user=user, password=tok, sslmode="require", autocommit=True)
DDL = """
CREATE SCHEMA IF NOT EXISTS workbench;
CREATE TABLE IF NOT EXISTS workbench.underwriting_decisions (
  decision_id      BIGSERIAL PRIMARY KEY,
  application_id   TEXT NOT NULL,
  institution_id   TEXT NOT NULL,
  decision         TEXT NOT NULL CHECK (decision IN ('APPROVE','APPROVE_WITH_CONDITIONS','DECLINE','REQUEST_DOCUMENTS')),
  approved_amount  NUMERIC(12,2),
  conditions       TEXT,
  underwriter      TEXT NOT NULL,
  model_epd_probability NUMERIC(8,5),
  model_risk_band  TEXT,
  followed_model   BOOLEAN,
  ai_income_mismatch BOOLEAN,
  rationale        TEXT,
  member_letter    TEXT,
  decided_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workbench.live_applications (
  application_id   TEXT PRIMARY KEY,
  institution_id   TEXT NOT NULL,
  member_name      TEXT, product_code TEXT, channel TEXT,
  requested_amount NUMERIC(12,2), term_months INT, stated_monthly_income NUMERIC(12,2), credit_score INT,
  monthly_debt_payments NUMERIC(12,2), doc_path TEXT,
  ai_verified_monthly_income NUMERIC(12,2), ai_employer_name TEXT, ai_pay_frequency TEXT, ai_income_variance_pct NUMERIC(8,3),
  epd_probability NUMERIC(8,5), risk_band TEXT, reason_1 TEXT, reason_2 TEXT, reason_3 TEXT,
  routing TEXT, routing_reason TEXT, processing_ms INT,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workbench.audit_log (
  event_id BIGSERIAL PRIMARY KEY, actor TEXT, action TEXT, application_id TEXT, detail JSONB, event_at TIMESTAMPTZ DEFAULT now()
);
"""
with conn.cursor() as cur:
    cur.execute(DDL)
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='workbench'")
    print(cur.fetchall())
conn.close()
```

**Output:**
```text
[('live_applications',), ('audit_log',), ('underwriting_decisions',)]
```
