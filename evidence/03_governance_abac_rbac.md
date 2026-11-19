# Evidence · Data Classification, ABAC, RBAC, tenant isolation

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## Column tags (Data Classification class.* + tenant_isolation_key)


```sql
SELECT schema_name, table_name, column_name, tag_name FROM demo_dnb_catalog.information_schema.column_tags
WHERE schema_name LIKE 'ml_lend%' ORDER BY 1,2,3
```

**Result:**

| schema_name | table_name | column_name | tag_name |
|---|---|---|---|
| ml_lend_bronze | members_cdc_raw | first_name | class.name |
| ml_lend_bronze | members_cdc_raw | last_name | class.name |
| ml_lend_bronze | members_cdc_raw | phone | class.phone_number |
| ml_lend_bronze | members_cdc_raw | ssn | class.us_ssn |
| ml_lend_bronze | members_cdc_raw | state | class.location |
| ml_lend_bronze | members_cdc_raw | street_address | class.location |
| ml_lend_bronze | members_cdc_raw | street_address | class.street_address |
| ml_lend_bronze | members_cdc_raw | zip | class.location |
| ml_lend_bronze | ref_branches | state | class.location |
| ml_lend_bronze | ref_institutions | hq_state | class.location |
| ml_lend_gold | dim_branch | state | class.location |
| ml_lend_gold | dim_institution | hq_state | class.location |
| ml_lend_gold | dim_member | date_of_birth | class.date_of_birth |
| ml_lend_gold | dim_member | email | class.email_address |
| ml_lend_gold | dim_member | first_name | class.name |
| ml_lend_gold | dim_member | institution_id | tenant_isolation_key |
| ml_lend_gold | dim_member | last_name | class.name |
| ml_lend_gold | dim_member | phone | class.phone_number |
| ml_lend_gold | dim_member | ssn | class.us_ssn |
| ml_lend_gold | dim_member | state | class.location |
| ml_lend_gold | dim_member | street_address | class.street_address |
| ml_lend_gold | dim_member | street_address | class.location |
| ml_lend_gold | dim_member | zip | class.location |
| ml_lend_gold | fact_application | institution_id | tenant_isolation_key |
| ml_lend_gold | fact_loan_performance | institution_id | tenant_isolation_key |
| ml_lend_gold | member_notes_enriched | institution_id | tenant_isolation_key |
| ml_lend_gold | outcome_monthly | institution_id | tenant_isolation_key |
| ml_lend_ml | application_risk_scores | institution_id | tenant_isolation_key |
| ml_lend_ml | path_to_yes_letters | institution_id | tenant_isolation_key |
| ml_lend_ops | live_applications | institution_id | tenant_isolation_key |
| ml_lend_ops | underwriting_decisions | institution_id | tenant_isolation_key |
| ml_lend_silver | document_income_extraction | doc_text | class.name |
| ml_lend_silver | members | first_name | class.name |
| ml_lend_silver | members | last_name | class.name |
| ml_lend_silver | members | phone | class.phone_number |
| ml_lend_silver | members | ssn | class.us_ssn |
| ml_lend_silver | members | state | class.location |
| ml_lend_silver | members | street_address | class.location |
| ml_lend_silver | members | street_address | class.street_address |
| ml_lend_silver | members | zip | class.location |

_48 rows, first 40 shown_



## Data Classification catalog config (auto-tagging enabled)

```json
{
 "auto_tag_configs": [
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.us_ssn"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.date_of_birth"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.email_address"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.phone_number"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.name"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.street_address"
  },
  {
   "auto_tagging_mode": "AUTO_TAGGING_ENABLED",
   "classification_tag": "class.location"
  }
 ],
 "included_schemas": {
  "names": [
   "ml_lend_bronze",
   "ml_lend_silver",
   "ml_lend_gold"
  ]
 },
 "name": "catalogs/demo_dnb_catalog/config"
}
```


## ABAC policies on schema ml_lend_gold

```json
[
 {
  "name": "ml_lend_mask_contact",
  "policy_type": "POLICY_TYPE_COLUMN_MASK",
  "match_columns": [
   {
    "alias": "c",
    "condition": "(has_tag('class.email_address') OR has_tag('class.phone_number') OR has_tag('class.name') OR has_tag('class.street_address'))"
   }
  ],
  "column_mask": {
   "function_name": "demo_dnb_catalog.ml_lend_gov.mask_contact",
   "on_column": "c"
  },
  "row_filter": null,
  "to_principals": [
   "account users"
  ]
 },
 {
  "name": "ml_lend_mask_dob",
  "policy_type": "POLICY_TYPE_COLUMN_MASK",
  "match_columns": [
   {
    "alias": "c",
    "condition": "has_tag('class.date_of_birth')"
   }
  ],
  "column_mask": {
   "function_name": "demo_dnb_catalog.ml_lend_gov.mask_dob",
   "on_column": "c"
  },
  "row_filter": null,
  "to_principals": [
   "account users"
  ]
 },
 {
  "name": "ml_lend_mask_ssn",
  "policy_type": "POLICY_TYPE_COLUMN_MASK",
  "match_columns": [
   {
    "alias": "c",
    "condition": "has_tag('class.us_ssn')"
   }
  ],
  "column_mask": {
   "function_name": "demo_dnb_catalog.ml_lend_gov.mask_ssn",
   "on_column": "c"
  },
  "row_filter": null,
  "to_principals": [
   "account users"
  ]
 },
 {
  "name": "ml_lend_tenant_isolation",
  "policy_type": "POLICY_TYPE_ROW_FILTER",
  "match_columns": [
   {
    "alias": "inst",
    "condition": "has_tag_value('tenant_isolation_key', 'true')"
   }
  ],
  "column_mask": null,
  "row_filter": {
   "function_name": "demo_dnb_catalog.ml_lend_gov.tenant_filter",
   "using": [
    {
     "alias": "inst"
    }
   ]
  },
  "to_principals": [
   "account users"
  ]
 }
]
```


## ABAC policies on schema ml_lend_ml

```json
[
 {
  "name": "ml_lend_tenant_isolation_ml",
  "policy_type": "POLICY_TYPE_ROW_FILTER",
  "match_columns": [
   {
    "alias": "inst",
    "condition": "has_tag_value('tenant_isolation_key', 'true')"
   }
  ],
  "column_mask": null,
  "row_filter": {
   "function_name": "demo_dnb_catalog.ml_lend_gov.tenant_filter",
   "using": [
    {
     "alias": "inst"
    }
   ]
  },
  "to_principals": [
   "account users"
  ]
 }
]
```


## Entitlements (who sees which credit union / how much PII)


```sql
SELECT * FROM demo_dnb_catalog.ml_lend_gov.tenant_entitlements
```

**Result:**

| principal | persona | institution_id | pii_access |
|---|---|---|---|
| sonam.s@databricks.com | MeridianLink Platform Analyst | * | NONE |
| 85522c3a-a513-4cc7-a183-a8cd4c40a07e | Summit Valley CU Underwriter (Workbench app) | CU-SVCU | LAST4 |



## As platform analyst (all CUs, PII NONE): masked PII


```sql
SELECT member_id, institution_id, first_name, ssn, date_of_birth, email, credit_score FROM demo_dnb_catalog.ml_lend_gold.dim_member LIMIT 3
```

**Result:**

| member_id | institution_id | first_name | ssn | date_of_birth | email | credit_score |
|---|---|---|---|---|---|---|
| MBR-0000001 | CU-SVCU | [REDACTED] | ***-**-**** | 1986-01-01 | [REDACTED] | 724 |
| MBR-0000002 | CU-SVCU | [REDACTED] | ***-**-**** | 1979-01-01 | [REDACTED] | 686 |
| MBR-0000003 | CU-SVCU | [REDACTED] | ***-**-**** | 1966-01-01 | [REDACTED] | 604 |



## As platform analyst: rows per credit union


```sql
SELECT institution_id, count(*) apps FROM demo_dnb_catalog.ml_lend_gold.fact_application GROUP BY 1 ORDER BY 1
```

**Result:**

| institution_id | apps |
|---|---|
| CU-HPCU | 54306 |
| CU-PFCU | 28951 |
| CU-RCCU | 45531 |
| CU-SVCU | 79429 |



> **Persona switch:** `UPDATE ml_lend_gov.tenant_entitlements SET institution_id='CU-HPCU', pii_access='LAST4' WHERE principal = current_user()`


## As Harbor Point underwriter: only Harbor Point rows


```sql
SELECT institution_id, count(*) apps FROM demo_dnb_catalog.ml_lend_gold.fact_application GROUP BY 1
```

**Result:**

| institution_id | apps |
|---|---|
| CU-HPCU | 54306 |



## As Harbor Point underwriter: same metric view, filtered


```sql
SELECT credit_union, MEASURE(applications) applications FROM demo_dnb_catalog.ml_lend_semantic.mv_loan_funnel GROUP BY 1
```

**Result:**

| credit_union | applications |
|---|---|
| Harbor Point Credit Union | 54306 |



## As Harbor Point underwriter: names visible, SSN last-4


```sql
SELECT first_name, ssn, date_of_birth FROM demo_dnb_catalog.ml_lend_gold.dim_member LIMIT 3
```

**Result:**

| first_name | ssn | date_of_birth |
|---|---|---|
| Ava | XXX-XX-7215 | 1975-12-24 |
| Nina | XXX-XX-6127 | 1969-05-23 |
| Malik | XXX-XX-8938 | 1999-04-18 |



> **Reset:** entitlement restored to `*` / `NONE`.


## RBAC grants on schemas


```sql
SHOW GRANTS ON SCHEMA demo_dnb_catalog.ml_lend_semantic
```

**Result:**

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 852bd824-1020-495c-a7bd-a8a936f2d21b | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| sonam.s@databricks.com | ALL PRIVILEGES | CATALOG | demo_dnb_catalog |
| sonam.s@databricks.com | MANAGE | CATALOG | demo_dnb_catalog |
| 85522c3a-a513-4cc7-a183-a8cd4c40a07e | SELECT | SCHEMA | demo_dnb_catalog.ml_lend_semantic |
| 85522c3a-a513-4cc7-a183-a8cd4c40a07e | USE SCHEMA | SCHEMA | demo_dnb_catalog.ml_lend_semantic |
| 29d3b98e-b968-4882-b54b-ae42cafd9cb6 | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| 22204953-12c2-4c38-b92b-f1ae7655e921 | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| account users | SELECT | SCHEMA | demo_dnb_catalog.ml_lend_semantic |
| account users | USE SCHEMA | SCHEMA | demo_dnb_catalog.ml_lend_semantic |
| account users | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL PRIVILEGES | CATALOG | demo_dnb_catalog |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | CATALOG | demo_dnb_catalog |
| suraj.bang@databricks.com | READ METADATA | METASTORE | metastore_aws_us_east_1 |

