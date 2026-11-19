# Run evidence: `07_sync_workbench_to_delta`

- Job run id: `199022686708257` · task run id: `task` · exported from Databricks job run (serverless)

# 07 · Workbench decisions: Lakebase → Delta
Fallback/explicit sync of `lending.workbench.*` (Lakebase Postgres) into `ml_lend_ops` Delta tables, so underwriter decisions
and live applications are governed in Unity Catalog and visible to Genie/BI. (Lakebase CDF config `workbench_to_delta` is
also configured — Beta.) Idempotent MERGE on primary keys.

```python
%pip install "psycopg[binary]==3.2.3" -q
```

**Output:**
```text
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
import psycopg, pandas as pd
from databricks.sdk import WorkspaceClient
CAT = "demo_dnb_catalog"
w = WorkspaceClient(); EP = "projects/meridianlink-lending/branches/production/endpoints/primary"
host = w.api_client.do("GET", "/api/2.0/postgres/projects/meridianlink-lending/branches/production/endpoints")["endpoints"][0]["status"]["hosts"]["host"]
tok = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": EP})["token"]
conn = psycopg.connect(host=host, dbname="lending", user=w.current_user.me().user_name, password=tok, sslmode="require")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CAT}.ml_lend_ops COMMENT 'Operational Workbench data replicated from Lakebase (decisions, live applications, audit)'")
for table, key in [("underwriting_decisions", "decision_id"), ("live_applications", "application_id"), ("audit_log", "event_id")]:
    cur = conn.execute(f"SELECT * FROM workbench.{table}")
    pdf = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    if pdf.empty: print(table, 0); continue
    for c in pdf.columns:
        if pdf[c].dtype == object: pdf[c] = pdf[c].map(lambda v: None if v is None else (float(v) if type(v).__name__ == "Decimal" else (str(v) if isinstance(v, (dict, list)) else v)))
        if isinstance(pdf[c].dtype, pd.DatetimeTZDtype): pdf[c] = pdf[c].dt.tz_convert("UTC").dt.tz_localize(None)
    sdf = spark.createDataFrame(pdf); sdf.createOrReplaceTempView("src")
    tgt = f"{CAT}.ml_lend_ops.{table}"
    if not spark.catalog.tableExists(tgt):
        sdf.write.saveAsTable(tgt)
        spark.sql(f"ALTER TABLE {tgt} ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true')") if "institution_id" in pdf.columns else None
    else:
        spark.sql(f"MERGE INTO {tgt} t USING src s ON t.{key} = s.{key} WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
    print(table, len(pdf))
conn.close()
```

**Output:**
```text
underwriting_decisions 1
live_applications 1
audit_log 1
```
