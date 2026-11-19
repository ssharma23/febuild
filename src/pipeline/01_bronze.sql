-- =====================================================================================
-- BRONZE · Lakeflow file ingestion (Auto Loader via read_files) of MeridianLink Data Connect extracts
-- Append-only, schema-on-read, full lineage to the source file. No custom ingestion code.
-- =====================================================================================

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_bronze.applications_raw
COMMENT 'Raw Data Connect loan application extracts (CSV). One row per application record per extract file; the same application can re-appear when its status changes (PENDING -> APPROVED/DECLINED) or when an extract is re-sent.'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, _metadata.file_modification_time AS _file_ts, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/applications/', format => 'csv', header => true,
  schemaHints => 'requested_amount DOUBLE, term_months INT, stated_monthly_income DOUBLE, denial_reason_id INT, approved_amount DOUBLE, apr DOUBLE, funded_amount DOUBLE, funded_flag BOOLEAN, income_verified_flag BOOLEAN, model_override_flag BOOLEAN, is_reapplication BOOLEAN, submitted_ts TIMESTAMP, decision_ts TIMESTAMP, funded_ts TIMESTAMP, record_updated_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_bronze.members_cdc_raw
COMMENT 'Raw Data Connect member (applicant) change events (JSON lines). Each event is a full-row UPSERT ordered by event_ts. Contains PII (SSN, DOB, email, phone, address).'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/members/', format => 'json',
  schemaHints => 'credit_score INT, stated_monthly_income DOUBLE, monthly_debt_payments DOUBLE, event_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_bronze.loan_payments_raw
COMMENT 'Raw Data Connect servicing payment extracts (CSV): one row per scheduled installment with payment outcome and days past due.'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/loan_payments/', format => 'csv', header => true,
  schemaHints => 'installment_number INT, due_date TIMESTAMP, days_past_due INT, scheduled_amount DOUBLE, payment_amount DOUBLE, interest_amount DOUBLE, late_fee_amount DOUBLE, principal_amount DOUBLE, payment_date TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_bronze.member_notes_raw
COMMENT 'Raw free-text notes from members, loan officers and underwriters attached to applications (JSON lines).'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/member_notes/', format => 'json', schemaHints => 'created_ts TIMESTAMP');

CREATE OR REFRESH STREAMING TABLE demo_dnb_catalog.ml_lend_bronze.documents_raw
COMMENT 'Member-submitted application documents (pay-stub PDFs) ingested as binary from the documents Volume. File name convention: <application_id>_paystub.pdf'
TBLPROPERTIES ('quality' = 'bronze')
AS SELECT path AS doc_path, regexp_extract(path, '(APP-[0-9]+)', 1) AS application_id, length AS file_bytes, modificationTime AS uploaded_ts, content, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/documents/paystubs/', format => 'binaryFile');

-- Reference data (full snapshots)
CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_bronze.ref_institutions COMMENT 'Credit unions (MeridianLink customers) in the Data Connect feed, with pilot/control cohort and Lending Intelligence go-live date.'
AS SELECT * FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/institutions/', format => 'csv', header => true);
CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_bronze.ref_branches COMMENT 'Credit-union branches.'
AS SELECT * FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/branches/', format => 'csv', header => true);
CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_bronze.ref_products COMMENT 'Consumer lending products.'
AS SELECT * FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/products/', format => 'csv', header => true);
CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_bronze.ref_denial_reasons COMMENT 'Standardized adverse-action (denial) reasons.'
AS SELECT * FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/denial_reasons/', format => 'csv', header => true);
CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_bronze.ref_dealers COMMENT 'Indirect-lending auto dealers.'
AS SELECT * FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/dealers/', format => 'csv', header => true);
