# Databricks notebook source
# MAGIC %md # 05 · Lakebase grants for the Workbench app service principal
# MAGIC Least privilege: SELECT on the synced queue, read/write only on the Workbench tables.

# COMMAND ----------

# MAGIC %pip install "psycopg[binary]==3.2.3" -q

# COMMAND ----------

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
