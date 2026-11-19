# Evidence · Lakeflow ingestion + medallion

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## Landing files (Data Connect extracts in a UC Volume)


```sql
SELECT regexp_extract(_metadata.file_path, 'dataconnect/([a-z_]+)/', 1) entity, count(DISTINCT _metadata.file_path) files, count(*) rows
FROM read_files('/Volumes/demo_dnb_catalog/ml_lend_landing/dataconnect/applications/', format=>'csv', header=>true) GROUP BY 1
```

**Result:**

| entity | files | rows |
|---|---|---|
| applications | 25 | 208697 |



## Row counts by medallion layer


```sql
SELECT 'bronze.applications_raw' t, count(*) n FROM demo_dnb_catalog.ml_lend_bronze.applications_raw UNION ALL
SELECT 'bronze.members_cdc_raw', count(*) FROM demo_dnb_catalog.ml_lend_bronze.members_cdc_raw UNION ALL
SELECT 'bronze.loan_payments_raw', count(*) FROM demo_dnb_catalog.ml_lend_bronze.loan_payments_raw UNION ALL
SELECT 'bronze.member_notes_raw', count(*) FROM demo_dnb_catalog.ml_lend_bronze.member_notes_raw UNION ALL
SELECT 'bronze.documents_raw (pay-stub PDFs)', count(*) FROM demo_dnb_catalog.ml_lend_bronze.documents_raw UNION ALL
SELECT 'silver.applications (AUTO CDC SCD1)', count(*) FROM demo_dnb_catalog.ml_lend_silver.applications UNION ALL
SELECT 'silver.applications_quarantine', count(*) FROM demo_dnb_catalog.ml_lend_silver.applications_quarantine UNION ALL
SELECT 'silver.members (AUTO CDC SCD2, all versions)', count(*) FROM demo_dnb_catalog.ml_lend_silver.members UNION ALL
SELECT 'silver.members_quarantine', count(*) FROM demo_dnb_catalog.ml_lend_silver.members_quarantine UNION ALL
SELECT 'silver.loan_payments', count(*) FROM demo_dnb_catalog.ml_lend_silver.loan_payments UNION ALL
SELECT 'silver.document_income_extraction (AI)', count(*) FROM demo_dnb_catalog.ml_lend_silver.document_income_extraction UNION ALL
SELECT 'silver.member_notes', count(*) FROM demo_dnb_catalog.ml_lend_silver.member_notes UNION ALL
SELECT 'gold.fact_application', count(*) FROM demo_dnb_catalog.ml_lend_gold.fact_application UNION ALL
SELECT 'gold.fact_loan_performance', count(*) FROM demo_dnb_catalog.ml_lend_gold.fact_loan_performance UNION ALL
SELECT 'gold.dim_member', count(*) FROM demo_dnb_catalog.ml_lend_gold.dim_member
```

**Result:**

| t | n |
|---|---|
| silver.applications (AUTO CDC SCD1) | 208217 |
| silver.members (AUTO CDC SCD2, all versions) | 132500 |
| gold.fact_application | 208217 |
| gold.fact_loan_performance | 76554 |
| gold.dim_member | 125000 |
| bronze.applications_raw | 208697 |
| bronze.members_cdc_raw | 132720 |
| bronze.loan_payments_raw | 881390 |
| bronze.member_notes_raw | 25949 |
| bronze.documents_raw (pay-stub PDFs) | 2374 |
| silver.applications_quarantine | 180 |
| silver.members_quarantine | 220 |
| silver.loan_payments | 881390 |
| silver.document_income_extraction (AI) | 2374 |
| silver.member_notes | 25949 |



## CDC proof: re-sent duplicates collapse (bronze rows vs distinct application_id)


```sql
SELECT count(*) bronze_rows, count(DISTINCT application_id) distinct_apps,
 (SELECT count(*) FROM demo_dnb_catalog.ml_lend_silver.applications) silver_rows FROM demo_dnb_catalog.ml_lend_bronze.applications_raw
```

**Result:**

| bronze_rows | distinct_apps | silver_rows |
|---|---|---|
| 208697 | 208217 | 208217 |



## SCD2 proof: members with more than one version


```sql
SELECT count(*) members_with_history FROM (SELECT member_id FROM demo_dnb_catalog.ml_lend_silver.members GROUP BY member_id HAVING count(*) > 1)
```

**Result:**

| members_with_history |
|---|
| 7500 |



## Quarantine by failed rule


```sql
SELECT 'applications' entity, failed_rule, count(*) n FROM demo_dnb_catalog.ml_lend_silver.applications_quarantine GROUP BY ALL
UNION ALL SELECT 'members', failed_rule, count(*) FROM demo_dnb_catalog.ml_lend_silver.members_quarantine GROUP BY ALL
```

**Result:**

| entity | failed_rule | n |
|---|---|---|
| applications | positive_requested_amt | 120 |
| applications | known_product | 60 |
| members | valid_ssn_format | 180 |
| members | member_id_present | 40 |



## Pipeline updates (event log)


```sql
SELECT origin.update_id, min(timestamp) started, max(timestamp) ended,
 max_by(details:update_progress:state::string, timestamp) final_state
FROM event_log('98881b13-1625-4b3d-810c-ad987acd8c9e') WHERE event_type = 'update_progress' GROUP BY 1 ORDER BY started
```

**Result:**

| update_id | started | ended | final_state |
|---|---|---|---|
| c79e50c6-3aca-4074-a5ec-4708e2e60501 | 2026-11-19T04:42:12.191Z | 2026-11-19T04:54:08.165Z | COMPLETED |
| e0d7993a-4e76-4756-bac6-b4ca0aff3441 | 2026-11-19T05:00:46.755Z | 2026-11-19T05:01:51.705Z | COMPLETED |
| 5ab5bbb8-9f9d-4991-bf55-c3f2b732a8e7 | 2026-11-19T05:02:57.512Z | 2026-11-19T05:07:46.231Z | COMPLETED |
| fd7dc4e6-7eb4-48fd-bed5-fba58472a6af | 2026-11-19T05:09:51.978Z | 2026-11-19T05:11:23.300Z | COMPLETED |



## Data-quality expectations (event log, all runs)


```sql
SELECT e.dataset, e.name expectation, sum(e.passed_records) passed, sum(e.failed_records) failed
FROM event_log('98881b13-1625-4b3d-810c-ad987acd8c9e'), LATERAL explode(from_json(details:flow_progress:data_quality:expectations,
 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t(e)
WHERE event_type='flow_progress' GROUP BY ALL ORDER BY 1,2
```

**Result:**

| dataset | expectation | passed | failed |
|---|---|---|---|
| applications_validated | application_id_present | 208697 | 0 |
| applications_validated | decision_after_submit | 208697 | 0 |
| applications_validated | known_product | 208637 | 60 |
| applications_validated | member_present | 208697 | 0 |
| applications_validated | positive_requested_amt | 208577 | 120 |
| demo_dnb_catalog.ml_lend_silver.loan_payments | amounts_balance | 1762780 | 0 |
| demo_dnb_catalog.ml_lend_silver.loan_payments | valid_dpd | 1762780 | 0 |
| demo_dnb_catalog.ml_lend_silver.loan_payments | valid_status | 1762780 | 0 |
| members_validated | credit_score_range | 132720 | 0 |
| members_validated | member_id_present | 132680 | 40 |
| members_validated | valid_ssn_format | 132540 | 180 |



## Rows written per flow (latest completed update)


```sql
WITH u AS (SELECT origin.update_id id FROM event_log('98881b13-1625-4b3d-810c-ad987acd8c9e') WHERE event_type='update_progress'
   AND details:update_progress:state::string='COMPLETED' ORDER BY timestamp DESC LIMIT 1)
SELECT origin.flow_name, max(details:flow_progress:metrics:num_output_rows::bigint) num_output_rows
FROM event_log('98881b13-1625-4b3d-810c-ad987acd8c9e') WHERE event_type='flow_progress' AND origin.update_id=(SELECT id FROM u) GROUP BY 1 ORDER BY 1
```

**Result:**

| flow_name | num_output_rows |
|---|---|
| demo_dnb_catalog.ml_lend_bronze.applications_cdc |  |
| demo_dnb_catalog.ml_lend_bronze.applications_raw |  |
| demo_dnb_catalog.ml_lend_bronze.documents_raw |  |
| demo_dnb_catalog.ml_lend_bronze.loan_payments_raw |  |
| demo_dnb_catalog.ml_lend_bronze.member_notes_raw |  |
| demo_dnb_catalog.ml_lend_bronze.members_cdc |  |
| demo_dnb_catalog.ml_lend_bronze.members_cdc_raw |  |
| demo_dnb_catalog.ml_lend_bronze.ref_branches | 30 |
| demo_dnb_catalog.ml_lend_bronze.ref_dealers | 11 |
| demo_dnb_catalog.ml_lend_bronze.ref_denial_reasons | 12 |
| demo_dnb_catalog.ml_lend_bronze.ref_institutions | 4 |
| demo_dnb_catalog.ml_lend_bronze.ref_products | 4 |
| demo_dnb_catalog.ml_lend_gold.dim_branch | 30 |
| demo_dnb_catalog.ml_lend_gold.dim_dealer | 11 |
| demo_dnb_catalog.ml_lend_gold.dim_denial_reason | 12 |
| demo_dnb_catalog.ml_lend_gold.dim_institution | 4 |
| demo_dnb_catalog.ml_lend_gold.dim_member | 125000 |
| demo_dnb_catalog.ml_lend_gold.dim_product | 4 |
| demo_dnb_catalog.ml_lend_gold.fact_application | 208217 |
| demo_dnb_catalog.ml_lend_gold.fact_loan_performance | 76554 |
| demo_dnb_catalog.ml_lend_gold.member_notes_enriched | 25949 |
| demo_dnb_catalog.ml_lend_gold.outcome_monthly | 100 |
| demo_dnb_catalog.ml_lend_gold.roi_assumptions | 7 |
| demo_dnb_catalog.ml_lend_silver.applications_quarantine |  |
| demo_dnb_catalog.ml_lend_silver.document_income_extraction |  |
| demo_dnb_catalog.ml_lend_silver.loan_payments |  |
| demo_dnb_catalog.ml_lend_silver.member_notes |  |
| demo_dnb_catalog.ml_lend_silver.members_quarantine |  |
| pipelines.flowTimeMetrics.missingFlowName |  |

