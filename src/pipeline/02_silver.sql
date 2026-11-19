-- =====================================================================================
-- SILVER · Trusted, conformed entities
--   * Data-quality expectations (warn / drop / fail) + quarantine tables for rejected records
--   * AUTO CDC: SCD1 for applications (latest status wins), SCD2 for members (full history)
--   * AI Functions on unstructured data: ai_parse_document + ai_extract (pay stubs), ai_classify (notes)
-- =====================================================================================

-- ---------- Applications: validate -> quarantine -> CDC (SCD1, re-sent / updated records collapse to latest)
CREATE TEMPORARY VIEW applications_validated (
  CONSTRAINT application_id_present  EXPECT (application_id IS NOT NULL)                       ON VIOLATION FAIL UPDATE,
  CONSTRAINT positive_requested_amt  EXPECT (requested_amount > 0)                             ON VIOLATION DROP ROW,
  CONSTRAINT known_product           EXPECT (product_code IN ('AUTO','PERSONAL','CARD','HELOC')) ON VIOLATION DROP ROW,
  CONSTRAINT member_present          EXPECT (member_id IS NOT NULL)                            ON VIOLATION DROP ROW,
  CONSTRAINT decision_after_submit   EXPECT (decision_ts IS NULL OR decision_ts >= submitted_ts)
)
AS SELECT * EXCEPT (_rescued_data) FROM STREAM(demo_dnb_catalog.ml_lend_bronze.applications_raw);

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.applications_quarantine
COMMENT 'Application records rejected by silver data-quality rules, with the failed rule for remediation by the MeridianLink data team.'
AS SELECT *, CASE WHEN requested_amount <= 0 THEN 'positive_requested_amt'
                  WHEN product_code NOT IN ('AUTO','PERSONAL','CARD','HELOC') THEN 'known_product'
                  WHEN member_id IS NULL THEN 'member_present' END AS failed_rule
FROM STREAM(demo_dnb_catalog.ml_lend_bronze.applications_raw)
WHERE requested_amount <= 0 OR product_code NOT IN ('AUTO','PERSONAL','CARD','HELOC') OR member_id IS NULL;

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.applications
COMMENT 'Current state of every loan application (SCD Type 1 via AUTO CDC on application_id, sequenced by record_updated_ts). Duplicate re-sent extract rows collapse automatically.'
TBLPROPERTIES ('quality' = 'silver', 'delta.enableChangeDataFeed' = 'true');

CREATE FLOW applications_cdc AS AUTO CDC INTO demo_dnb_catalog.ml_lend_silver.applications
FROM STREAM(applications_validated)
KEYS (application_id)
SEQUENCE BY record_updated_ts
COLUMNS * EXCEPT (_file_ts, _ingested_at)
STORED AS SCD TYPE 1;

-- ---------- Members: validate -> SCD2 history
CREATE TEMPORARY VIEW members_validated (
  CONSTRAINT member_id_present EXPECT (member_id IS NOT NULL)                       ON VIOLATION DROP ROW,
  CONSTRAINT valid_ssn_format  EXPECT (ssn RLIKE '^[0-9]{3}-[0-9]{2}-[0-9]{4}$')     ON VIOLATION DROP ROW,
  CONSTRAINT credit_score_range EXPECT (credit_score BETWEEN 300 AND 850)
)
AS SELECT * EXCEPT (_rescued_data) FROM STREAM(demo_dnb_catalog.ml_lend_bronze.members_cdc_raw);

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.members_quarantine
COMMENT 'Member change events rejected by silver data-quality rules (missing member_id or malformed SSN).'
AS SELECT *, CASE WHEN member_id IS NULL THEN 'member_id_present' ELSE 'valid_ssn_format' END AS failed_rule
FROM STREAM(demo_dnb_catalog.ml_lend_bronze.members_cdc_raw)
WHERE member_id IS NULL OR NOT (ssn RLIKE '^[0-9]{3}-[0-9]{2}-[0-9]{4}$');

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.members
COMMENT 'Credit-union members / loan applicants with full change history (SCD Type 2 via AUTO CDC). Current row has __END_AT IS NULL. Contains PII protected by ABAC masking.'
TBLPROPERTIES ('quality' = 'silver');

CREATE FLOW members_cdc AS AUTO CDC INTO demo_dnb_catalog.ml_lend_silver.members
FROM STREAM(members_validated)
KEYS (member_id)
SEQUENCE BY event_ts
COLUMNS * EXCEPT (op, _source_file, _ingested_at)
STORED AS SCD TYPE 2;

-- ---------- Payments
CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.loan_payments (
  CONSTRAINT valid_dpd        EXPECT (days_past_due >= 0)                       ON VIOLATION DROP ROW,
  CONSTRAINT valid_status     EXPECT (payment_status IN ('COMPLETED','LATE','MISSED','REVERSED')),
  CONSTRAINT amounts_balance  EXPECT (abs(payment_amount - principal_amount - interest_amount - late_fee_amount) < 1 OR payment_status = 'MISSED')
)
COMMENT 'Validated loan installment outcomes (one row per scheduled installment).'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT * EXCEPT (_rescued_data, _source_file, _ingested_at) FROM STREAM(demo_dnb_catalog.ml_lend_bronze.loan_payments_raw);

-- ---------- AI: pay-stub documents -> verified income (ai_parse_document + ai_extract)
CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.document_income_extraction
COMMENT 'AI-extracted pay-stub facts. ai_parse_document turns each PDF into text; ai_extract pulls employer, pay frequency and gross pay; verified_monthly_income normalizes to monthly. Processed incrementally: each document is parsed once.'
TBLPROPERTIES ('quality' = 'silver')
AS
WITH parsed AS (
  SELECT doc_path, application_id, uploaded_ts, ai_parse_document(content) AS parsed
  FROM STREAM(demo_dnb_catalog.ml_lend_bronze.documents_raw)
), txt AS (
  SELECT doc_path, application_id, uploaded_ts,
         concat_ws('\n', transform(try_cast(parsed:document:elements AS ARRAY<VARIANT>), e -> try_cast(e:content AS STRING))) AS doc_text,
         try_cast(parsed:error_status AS STRING) AS parse_error
  FROM parsed
), ext AS (
  SELECT *, ai_extract(doc_text, array('employer_name','employee_name','pay_frequency','pay_period_end_date','gross_pay_this_period','year_to_date_gross')) AS f
  FROM txt
)
SELECT doc_path, application_id, uploaded_ts, doc_text, parse_error,
       f.employer_name AS employer_name, f.employee_name AS employee_name, f.pay_frequency AS pay_frequency_raw,
       f.pay_period_end_date AS pay_period_end_raw,
       try_cast(regexp_replace(f.gross_pay_this_period, '[^0-9.]', '') AS DOUBLE) AS gross_pay_period,
       try_cast(regexp_replace(f.year_to_date_gross, '[^0-9.]', '') AS DOUBLE)   AS ytd_gross,
       CASE WHEN lower(f.pay_frequency) LIKE '%bi%week%' OR lower(f.pay_frequency) LIKE '%every two%' THEN 26.0/12
            WHEN lower(f.pay_frequency) LIKE '%semi%' OR lower(f.pay_frequency) LIKE '%twice%' THEN 2.0
            WHEN lower(f.pay_frequency) LIKE '%week%' THEN 52.0/12
            WHEN lower(f.pay_frequency) LIKE '%month%' THEN 1.0 END AS periods_per_month,
       round(try_cast(regexp_replace(f.gross_pay_this_period, '[^0-9.]', '') AS DOUBLE) *
             CASE WHEN lower(f.pay_frequency) LIKE '%bi%week%' OR lower(f.pay_frequency) LIKE '%every two%' THEN 26.0/12
                  WHEN lower(f.pay_frequency) LIKE '%semi%' OR lower(f.pay_frequency) LIKE '%twice%' THEN 2.0
                  WHEN lower(f.pay_frequency) LIKE '%week%' THEN 52.0/12
                  WHEN lower(f.pay_frequency) LIKE '%month%' THEN 1.0 END, 0) AS verified_monthly_income,
       current_timestamp() AS extracted_at
FROM ext;

-- ---------- AI: classify free-text notes (recent window keeps token spend bounded)
CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_silver.member_notes
COMMENT 'Member / loan-officer / underwriter notes. note_category is assigned by ai_classify for notes from 2026-08-01 onward (HARDSHIP, RATE_SHOPPING, DOCUMENT_ISSUE, FRAUD_CONCERN, STATUS_INQUIRY, COMPLAINT).'
TBLPROPERTIES ('quality' = 'silver')
AS SELECT note_id, application_id, member_id, institution_id, created_ts, author_role, note_text,
          CASE WHEN created_ts >= '2026-08-01'
               THEN ai_classify(note_text, array('HARDSHIP','RATE_SHOPPING','DOCUMENT_ISSUE','FRAUD_CONCERN','STATUS_INQUIRY','COMPLAINT')) END AS note_category
FROM STREAM(demo_dnb_catalog.ml_lend_bronze.member_notes_raw);
