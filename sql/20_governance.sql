-- =====================================================================================
-- GOVERNANCE · ABAC (tag-driven) masking + multi-tenant row isolation, RBAC grants
--   PII columns are found and tagged automatically by Unity Catalog Data Classification (class.* system tags).
--   Policies attach to TAGS, not to tables: any new table with an SSN column is protected on day one.
--   Tenant isolation: columns tagged tenant_isolation_key=true are filtered to the caller's credit union.
-- =====================================================================================

-- Entitlements: who may see which credit union, and how much PII
-- (principal = current_user(): user email or service-principal application id)
MERGE INTO demo_dnb_catalog.ml_lend_gov.tenant_entitlements t
USING (SELECT 'sonam.s@databricks.com' principal, 'MeridianLink Platform Analyst' persona, '*' institution_id, 'NONE' pii_access) s
ON t.principal = s.principal
WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE FUNCTION demo_dnb_catalog.ml_lend_gov.caller_pii_access()
RETURNS STRING
COMMENT 'PII access level of the calling principal from tenant_entitlements: FULL | LAST4 | NONE (default NONE).'
RETURN coalesce((SELECT first(pii_access) FROM demo_dnb_catalog.ml_lend_gov.tenant_entitlements WHERE principal = current_user()), 'NONE');

CREATE OR REPLACE FUNCTION demo_dnb_catalog.ml_lend_gov.mask_ssn(ssn STRING)
RETURNS STRING
COMMENT 'ABAC column mask for class.us_ssn: FULL -> clear, LAST4 -> XXX-XX-1234, otherwise fully redacted.'
RETURN CASE demo_dnb_catalog.ml_lend_gov.caller_pii_access()
         WHEN 'FULL'  THEN ssn
         WHEN 'LAST4' THEN concat('XXX-XX-', right(ssn, 4))
         ELSE '***-**-****' END;

CREATE OR REPLACE FUNCTION demo_dnb_catalog.ml_lend_gov.mask_contact(val STRING)
RETURNS STRING
COMMENT 'ABAC column mask for names, email, phone, street address: visible to FULL and LAST4 (underwriters), redacted for analysts.'
RETURN CASE WHEN demo_dnb_catalog.ml_lend_gov.caller_pii_access() IN ('FULL','LAST4') THEN val ELSE '[REDACTED]' END;

CREATE OR REPLACE FUNCTION demo_dnb_catalog.ml_lend_gov.mask_dob(dob DATE)
RETURNS DATE
COMMENT 'ABAC column mask for class.date_of_birth: analysts see Jan-1 of the birth year (age analytics still work), underwriters see the full date.'
RETURN CASE WHEN demo_dnb_catalog.ml_lend_gov.caller_pii_access() IN ('FULL','LAST4') THEN dob ELSE make_date(year(dob), 1, 1) END;

CREATE OR REPLACE FUNCTION demo_dnb_catalog.ml_lend_gov.tenant_filter(row_institution_id STRING)
RETURNS BOOLEAN
COMMENT 'ABAC row filter for columns tagged tenant_isolation_key: a principal sees only the credit unions granted in tenant_entitlements (* = all).'
RETURN EXISTS (SELECT 1 FROM demo_dnb_catalog.ml_lend_gov.tenant_entitlements e
               WHERE e.principal = current_user() AND (e.institution_id = '*' OR e.institution_id = row_institution_id));

-- Tenant tag on the credit-union key of every consumption table
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.fact_application ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.fact_loan_performance ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.outcome_monthly ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.member_notes_enriched ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');
ALTER TABLE demo_dnb_catalog.ml_lend_ml.application_risk_scores ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true');

-- ABAC policies on the GOLD (consumption) schema
CREATE OR REPLACE POLICY ml_lend_mask_ssn ON SCHEMA demo_dnb_catalog.ml_lend_gold
COMMENT 'Mask any column auto-classified as a US SSN.'
COLUMN MASK demo_dnb_catalog.ml_lend_gov.mask_ssn
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag('class.us_ssn') AS c
ON COLUMN c;

CREATE OR REPLACE POLICY ml_lend_mask_contact ON SCHEMA demo_dnb_catalog.ml_lend_gold
COMMENT 'Mask names, email, phone and street address found by Data Classification.'
COLUMN MASK demo_dnb_catalog.ml_lend_gov.mask_contact
TO `account users`
FOR TABLES
MATCH COLUMNS (has_tag('class.email_address') OR has_tag('class.phone_number') OR has_tag('class.name') OR has_tag('class.street_address')) AS c
ON COLUMN c;

CREATE OR REPLACE POLICY ml_lend_mask_dob ON SCHEMA demo_dnb_catalog.ml_lend_gold
COMMENT 'Generalize date of birth to birth year for non-underwriters.'
COLUMN MASK demo_dnb_catalog.ml_lend_gov.mask_dob
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag('class.date_of_birth') AS c
ON COLUMN c;

CREATE OR REPLACE POLICY ml_lend_tenant_isolation ON SCHEMA demo_dnb_catalog.ml_lend_gold
COMMENT 'Multi-tenant isolation: each credit union sees only its own members, applications and loans.'
ROW FILTER demo_dnb_catalog.ml_lend_gov.tenant_filter
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag_value('tenant_isolation_key', 'true') AS inst
USING COLUMNS (inst);

CREATE OR REPLACE POLICY ml_lend_tenant_isolation_ml ON SCHEMA demo_dnb_catalog.ml_lend_ml
COMMENT 'Multi-tenant isolation on model scores.'
ROW FILTER demo_dnb_catalog.ml_lend_gov.tenant_filter
TO `account users`
FOR TABLES
MATCH COLUMNS has_tag_value('tenant_isolation_key', 'true') AS inst
USING COLUMNS (inst)
