# Evidence · Databricks App (Lending Intelligence Workbench) + Lakebase

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## App status

```json
{
 "name": "meridianlink-lending-workbench",
 "url": "https://meridianlink-lending-workbench-7474649251700104.aws.databricksapps.com",
 "app_status": {
  "message": "App has status: App is running",
  "state": "RUNNING"
 },
 "compute_status": {
  "message": "App compute is running.",
  "state": "ACTIVE"
 },
 "active_deployment": {
  "deployment_id": "01f1e3e0ca8d1cc9b9c634059dab831b",
  "status": {
   "message": "App started successfully",
   "state": "SUCCEEDED"
  },
  "create_time": "2026-11-19T06:16:43Z"
 },
 "resources": [
  "sql-warehouse",
  "epd-endpoint",
  "lakebase"
 ],
 "service_principal_client_id": "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
}
```


## App logs (app/system lines; client IPs redacted)

```text
2026-11-19T05:24:36Z [APP] 
2026-11-19T05:24:36Z [APP]   URL: http://x.x.x.x:8000
2026-11-19T05:46:43Z [APP] 2026-11-19 05:46:43.264 Uncaught app exception
2026-11-19T05:50:58Z [APP] 2026-11-19 05:50:58.131 Uncaught app exception
2026-11-19T05:52:27Z [APP]   Stopping...
2026-11-19T05:52:29Z [APP] 
2026-11-19T05:52:29Z [APP] 
2026-11-19T06:16:47Z [APP]   Stopping...
2026-11-19T06:16:48Z [APP] 
2026-11-19T06:16:48Z [APP]
```


## Lakebase project

```json
{
 "name": "projects/meridianlink-lending",
 "spec": {
  "display_name": "MeridianLink Lending Workbench"
 },
 "status": {
  "branch_logical_size_limit_bytes": 35184372088832,
  "compute_last_active_time": "2026-11-19T06:33:16Z",
  "default_branch": "projects/meridianlink-lending/branches/production",
  "default_endpoint_settings": {
   "autoscaling_limit_max_cu": 1,
   "autoscaling_limit_min_cu": 1,
   "suspend_timeout_duration": "86400s"
  },
  "display_name": "MeridianLink Lending Workbench",
  "enable_pg_native_login": false,
  "history_retention_duration": "604800s",
  "owner": "sonam.s@databricks.com",
  "pg_version": 17,
  "project_id": "meridianlink-lending",
  "synthetic_storage_size_bytes": 0
 }
}
```


## Lakebase CDF config (Postgres workbench schema → UC ml_lend_ops)

```json
[
 {
  "catalog": "demo_dnb_catalog",
  "cdf_config_id": "workbench_to_delta",
  "create_time": "2026-11-19T05:11:55.919Z",
  "name": "projects/meridianlink-lending/branches/production/databases/lending/cdf-configs/workbench_to_delta",
  "postgres_schema": "workbench",
  "schema": "ml_lend_ops"
 }
]
```


## Synced table (Delta → Lakebase) visible in UC


```sql
SELECT routing_reason, count(*) n FROM demo_dnb_catalog.ml_lend_ml.underwriting_queue_synced GROUP BY 1
```

**Result:**

| routing_reason | n |
|---|---|
| PRODUCT_POLICY | 3 |
| STANDARD_REVIEW | 6 |
| HIGH_RISK | 7 |



## Round trip: underwriter decision made in the app, now in Delta (ml_lend_ops)


```sql
SELECT application_id, institution_id, decision, underwriter, model_risk_band, ai_income_mismatch, decided_at, left(member_letter, 120) letter_start
FROM demo_dnb_catalog.ml_lend_ops.underwriting_decisions ORDER BY decided_at DESC
```

**Result:**

| application_id | institution_id | decision | underwriter | model_risk_band | ai_income_mismatch | decided_at | letter_start |
|---|---|---|---|---|---|---|---|
| APP-LIVE0001-061239 | CU-SVCU | DECLINE | sonam.s@databricks.com | MEDIUM | true | 2026-11-19T06:15:22.502Z | Dear Jordan Whitaker,  Thank you for applying for a $32,000 auto loan with Summit Valley Credit Union. After careful rev |



## Live applications submitted through the app


```sql
SELECT application_id, product_code, requested_amount, stated_monthly_income, ai_verified_monthly_income, ai_income_variance_pct, risk_band, routing_reason, processing_ms
FROM demo_dnb_catalog.ml_lend_ops.live_applications ORDER BY submitted_at DESC
```

**Result:**

| application_id | product_code | requested_amount | stated_monthly_income | ai_verified_monthly_income | ai_income_variance_pct | risk_band | routing_reason | processing_ms |
|---|---|---|---|---|---|---|---|---|
| APP-LIVE0001-061239 | AUTO | 32000.0 | 7500.0 | 4200.0 | 0.786 | MEDIUM | INCOME_MISMATCH | 16636 |

