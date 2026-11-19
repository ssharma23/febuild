# Run evidence: `05_lakebase_grants`

- Job run id: `208925107614318` · task run id: `task` · exported from Databricks job run (serverless)

# 05 · Lakebase grants for the Workbench app service principal
Least privilege: SELECT on the synced queue, read/write only on the Workbench tables.

```python
%pip install "psycopg[binary]==3.2.3" -q
```

**Output:**
```text
Note: you may need to restart the kernel using %restart_python or dbutils.library.restartPython() to use updated packages.
```

```python
dbutils.widgets.text("app_sp", "85522c3a-a513-4cc7-a183-a8cd4c40a07e")
SP = dbutils.widgets.get("app_sp")
import psycopg
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
EP = "projects/meridianlink-lending/branches/production/endpoints/primary"
host = w.api_client.do("GET", "/api/2.0/postgres/projects/meridianlink-lending/branches/production/endpoints")["endpoints"][0]["status"]["hosts"]["host"]
tok = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": EP})["token"]
conn = psycopg.connect(host=host, dbname="lending", user=w.current_user.me().user_name, password=tok, sslmode="require", autocommit=True)
with conn.cursor() as cur:
    cur.execute("SELECT rolname FROM pg_roles WHERE rolname = %s", (SP,)); print("role exists:", cur.fetchall())
    cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')"); print(cur.fetchall())
    for s in [f'GRANT USAGE ON SCHEMA workbench TO "{SP}"',
              f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA workbench TO "{SP}"',
              f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA workbench TO "{SP}"',
              f'ALTER DEFAULT PRIVILEGES IN SCHEMA workbench GRANT SELECT, INSERT, UPDATE ON TABLES TO "{SP}"',
              f'GRANT USAGE ON SCHEMA ml_lend_ml TO "{SP}"',
              f'GRANT SELECT ON ALL TABLES IN SCHEMA ml_lend_ml TO "{SP}"']:
        cur.execute(s); print("ok:", s)
conn.close()
```

**Output:**
```text
role exists: [('85522c3a-a513-4cc7-a183-a8cd4c40a07e',)]
[('public', 'local_cache'), ('public', 'neon_backend_perf_counters'), ('public', 'neon_perf_counters'), ('public', 'neon_lfc_stats'), ('public', 'neon_stat_file_cache'), ('public', 'neon_lwlsn_cache_stats'), ('__db_system', '__db_prog_4318935c-48ae-4b49-9dc1-8cf14875fc9b'), ('public', 'neon_relsize_cache_stats'), ('public', 'neon_relperst_cache_stats'), ('public', 'neon_backpressure_status'), ('public', 'neon_recovery_time_in_redo'), ('public', 'neon_recovery_top_waits'), ('public', 'databricks_synced_table_managers'), ('public', 'databricks_list_roles'), ('public', 'databricks_auth_metrics'), ('workbench', 'live_applications'), ('__db_system', 'table_pipeline_id'), ('workbench', 'audit_log'), ('wal2delta', 'tables'), ('workbench', 'underwriting_decisions'), ('__db_system', '__db_sync_log_4318935c-48ae-4b49-9dc1-8cf14875fc9b'), ('ml_lend_ml', 'underwriting_queue_synced'), ('__db_system', 'partition_24640')]
ok: GRANT USAGE ON SCHEMA workbench TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
ok: GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA workbench TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
ok: GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA workbench TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
ok: ALTER DEFAULT PRIVILEGES IN SCHEMA workbench GRANT SELECT, INSERT, UPDATE ON TABLES TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
ok: GRANT USAGE ON SCHEMA ml_lend_ml TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
ok: GRANT SELECT ON ALL TABLES IN SCHEMA ml_lend_ml TO "85522c3a-a513-4cc7-a183-a8cd4c40a07e"
```
