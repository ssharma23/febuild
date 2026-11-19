"""Collect text evidence that the build ran: live SQL results, pipeline event log, governance proofs, model + serving output,
Genie transcripts, dashboard definition + dataset results, app + Lakebase status. Writes evidence/*.md.
Usage: python3 scripts/collect_evidence.py   (Databricks CLI profile fevm-demo-dnb)"""
import json, subprocess, time, os, datetime, re
PROFILE = "fevm-demo-dnb"; WH = "6ea47fe72fea6233"; CLI = ["/opt/homebrew/bin/databricks", "-p", PROFILE]
C = "demo_dnb_catalog"; OUT = os.path.join(os.path.dirname(__file__), "..", "evidence")
PIPELINE = "98881b13-1625-4b3d-810c-ad987acd8c9e"; GENIE = "01f1e3d666d91574bd4ffb20588c2ed6"; DASH = "01f1e3d70b0c18ed82e52bd9e2d637b6"
APP = "meridianlink-lending-workbench"; ENDPOINT = "ml-lend-epd-risk"
NOW = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

def cli(*args, body=None):
    cmd = CLI + list(args) + (["--json", json.dumps(body)] if body is not None else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"_raw": r.stdout[:4000], "_err": r.stderr[:2000]}

def sql(stmt):
    r = cli("api", "post", "/api/2.0/sql/statements", body={"statement": stmt, "warehouse_id": WH, "wait_timeout": "50s",
            "on_wait_timeout": "CONTINUE", "format": "JSON_ARRAY", "disposition": "INLINE"})
    while r.get("status", {}).get("state") in ("PENDING", "RUNNING"):
        time.sleep(3); r = cli("api", "get", f"/api/2.0/sql/statements/{r['statement_id']}")
    if r.get("status", {}).get("state") != "SUCCEEDED":
        return None, None, r.get("status", {}).get("error", {}).get("message", str(r))[:800]
    cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
    return cols, r.get("result", {}).get("data_array", []) or [], None

def md_table(cols, rows, limit=40):
    if cols is None: return ""
    def cell(v): return "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")[:160]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows[:limit]]
    if len(rows) > limit: lines.append(f"\n_{len(rows)} rows, first {limit} shown_")
    return "\n".join(lines)

class Doc:
    def __init__(self, fname, title, intro=""):
        self.f, self.parts = fname, [f"# {title}\n", f"_Collected {NOW} from workspace `fevm-demo-dnb` (catalog `{C}`) by `scripts/collect_evidence.py`. Live results, not screenshots._\n", intro]
    def q(self, heading, stmt, note=""):
        cols, rows, err = sql(stmt)
        self.parts += [f"\n## {heading}\n", (note + "\n") if note else "", "```sql\n" + stmt.strip() + "\n```\n",
                       ("**Result:**\n\n" + md_table(cols, rows)) if err is None else f"**Error:** `{err}`", "\n"]
        return cols, rows
    def text(self, heading, body, lang="text"):
        self.parts += [f"\n## {heading}\n", f"```{lang}\n{body.strip()}\n```\n"]
    def raw(self, s): self.parts.append(s)
    def save(self):
        open(os.path.join(OUT, self.f), "w").write("\n".join(self.parts)); print("wrote", self.f)

# ---------------------------------------------------------------- 1. data + medallion
d = Doc("01_data_and_medallion.md", "Evidence · Lakeflow ingestion + medallion")
d.q("Landing files (Data Connect extracts in a UC Volume)", f"""SELECT regexp_extract(_metadata.file_path, 'dataconnect/([a-z_]+)/', 1) entity, count(DISTINCT _metadata.file_path) files, count(*) rows
FROM read_files('/Volumes/{C}/ml_lend_landing/dataconnect/applications/', format=>'csv', header=>true) GROUP BY 1""")
d.q("Row counts by medallion layer", f"""SELECT 'bronze.applications_raw' t, count(*) n FROM {C}.ml_lend_bronze.applications_raw UNION ALL
SELECT 'bronze.members_cdc_raw', count(*) FROM {C}.ml_lend_bronze.members_cdc_raw UNION ALL
SELECT 'bronze.loan_payments_raw', count(*) FROM {C}.ml_lend_bronze.loan_payments_raw UNION ALL
SELECT 'bronze.member_notes_raw', count(*) FROM {C}.ml_lend_bronze.member_notes_raw UNION ALL
SELECT 'bronze.documents_raw (pay-stub PDFs)', count(*) FROM {C}.ml_lend_bronze.documents_raw UNION ALL
SELECT 'silver.applications (AUTO CDC SCD1)', count(*) FROM {C}.ml_lend_silver.applications UNION ALL
SELECT 'silver.applications_quarantine', count(*) FROM {C}.ml_lend_silver.applications_quarantine UNION ALL
SELECT 'silver.members (AUTO CDC SCD2, all versions)', count(*) FROM {C}.ml_lend_silver.members UNION ALL
SELECT 'silver.members_quarantine', count(*) FROM {C}.ml_lend_silver.members_quarantine UNION ALL
SELECT 'silver.loan_payments', count(*) FROM {C}.ml_lend_silver.loan_payments UNION ALL
SELECT 'silver.document_income_extraction (AI)', count(*) FROM {C}.ml_lend_silver.document_income_extraction UNION ALL
SELECT 'silver.member_notes', count(*) FROM {C}.ml_lend_silver.member_notes UNION ALL
SELECT 'gold.fact_application', count(*) FROM {C}.ml_lend_gold.fact_application UNION ALL
SELECT 'gold.fact_loan_performance', count(*) FROM {C}.ml_lend_gold.fact_loan_performance UNION ALL
SELECT 'gold.dim_member', count(*) FROM {C}.ml_lend_gold.dim_member""")
d.q("CDC proof: re-sent duplicates collapse (bronze rows vs distinct application_id)", f"""SELECT count(*) bronze_rows, count(DISTINCT application_id) distinct_apps,
 (SELECT count(*) FROM {C}.ml_lend_silver.applications) silver_rows FROM {C}.ml_lend_bronze.applications_raw""")
d.q("SCD2 proof: members with more than one version", f"""SELECT count(*) members_with_history FROM (SELECT member_id FROM {C}.ml_lend_silver.members GROUP BY member_id HAVING count(*) > 1)""")
d.q("Quarantine by failed rule", f"""SELECT 'applications' entity, failed_rule, count(*) n FROM {C}.ml_lend_silver.applications_quarantine GROUP BY ALL
UNION ALL SELECT 'members', failed_rule, count(*) FROM {C}.ml_lend_silver.members_quarantine GROUP BY ALL""")
d.q("Pipeline updates (event log)", f"""SELECT origin.update_id, min(timestamp) started, max(timestamp) ended,
 max_by(details:update_progress:state::string, timestamp) final_state
FROM event_log('{PIPELINE}') WHERE event_type = 'update_progress' GROUP BY 1 ORDER BY started""")
d.q("Data-quality expectations (event log, all runs)", f"""SELECT e.dataset, e.name expectation, sum(e.passed_records) passed, sum(e.failed_records) failed
FROM event_log('{PIPELINE}'), LATERAL explode(from_json(details:flow_progress:data_quality:expectations,
 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t(e)
WHERE event_type='flow_progress' GROUP BY ALL ORDER BY 1,2""")
d.q("Rows written per flow (latest completed update)", f"""WITH u AS (SELECT origin.update_id id FROM event_log('{PIPELINE}') WHERE event_type='update_progress'
   AND details:update_progress:state::string='COMPLETED' ORDER BY timestamp DESC LIMIT 1)
SELECT origin.flow_name, max(details:flow_progress:metrics:num_output_rows::bigint) num_output_rows
FROM event_log('{PIPELINE}') WHERE event_type='flow_progress' AND origin.update_id=(SELECT id FROM u) GROUP BY 1 ORDER BY 1""")
d.save()

# ---------------------------------------------------------------- 2. AI functions
a = Doc("02_ai_functions.md", "Evidence · AI Functions (ai_parse_document, ai_extract, ai_classify, ai_query)")
a.q("ai_parse_document + ai_extract: sample extracted pay-stub facts", f"""SELECT application_id, employer_name, pay_frequency_raw, gross_pay_period, verified_monthly_income, left(doc_text, 90) doc_text_start
FROM {C}.ml_lend_silver.document_income_extraction ORDER BY application_id LIMIT 8""")
a.q("Extraction accuracy vs hidden ground truth", f"""SELECT count(*) documents, round(avg(CASE WHEN abs(d.verified_monthly_income - t.true_monthly_income)/t.true_monthly_income < 0.02 THEN 1.0 ELSE 0 END),4) within_2pct,
 sum(CASE WHEN d.verified_monthly_income IS NULL THEN 1 ELSE 0 END) failed_extractions
FROM {C}.ml_lend_silver.document_income_extraction d JOIN {C}.ml_lend_ml.eval_income_truth t USING (application_id)""",
 "Ground truth (`eval_income_truth`) is produced by the synthetic generator and never shown to the pipeline.")
a.q("Income-misstatement detection: confusion matrix", f"""SELECT t.income_misstated, f.ai_income_mismatch_flag, count(*) n
FROM {C}.ml_lend_silver.document_income_extraction d JOIN {C}.ml_lend_ml.eval_income_truth t USING (application_id)
JOIN {C}.ml_lend_gold.fact_application f USING (application_id) GROUP BY ALL ORDER BY 1,2""")
a.q("ai_classify accuracy vs human-labelled notes", f"""SELECT count(*) labelled, round(avg(CASE WHEN n.note_category = l.human_label THEN 1.0 ELSE 0 END),3) accuracy
FROM {C}.ml_lend_ml.eval_note_labels l JOIN {C}.ml_lend_silver.member_notes n USING (note_id) WHERE n.note_category IS NOT NULL""")
a.q("ai_classify output distribution", f"""SELECT note_category, count(*) n FROM {C}.ml_lend_silver.member_notes WHERE note_category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
a.q("ai_query: generated 'path to yes' letters", f"""SELECT reason_code, count(*) letters FROM {C}.ml_lend_ml.path_to_yes_letters GROUP BY 1 ORDER BY 2 DESC""")
cols, rows, err = sql(f"SELECT reason_code, letter_text FROM {C}.ml_lend_ml.path_to_yes_letters WHERE reason_code IN ('INC-UNVER','DTI-HIGH') LIMIT 2")
for r in rows or []: a.text(f"Sample letter ({r[0]})", r[1])
a.save()

# ---------------------------------------------------------------- 3. governance
g = Doc("03_governance_abac_rbac.md", "Evidence · Data Classification, ABAC, RBAC, tenant isolation")
g.q("Column tags (Data Classification class.* + tenant_isolation_key)", f"""SELECT schema_name, table_name, column_name, tag_name FROM {C}.information_schema.column_tags
WHERE schema_name LIKE 'ml_lend%' ORDER BY 1,2,3""")
cfg = cli("data-classification", "get-catalog-config", f"catalogs/{C}/config", "-o", "json")
g.text("Data Classification catalog config (auto-tagging enabled)", json.dumps(cfg, indent=1), "json")
for sch in ["ml_lend_gold", "ml_lend_ml"]:
    pol = cli("policies", "list-policies", "SCHEMA", f"{C}.{sch}", "-o", "json")
    pl = pol if isinstance(pol, list) else pol.get("policies", [])
    g.text(f"ABAC policies on schema {sch}", json.dumps([{k: p.get(k) for k in ["name", "policy_type", "match_columns", "column_mask", "row_filter", "to_principals"]} for p in pl], indent=1), "json")
g.q("Entitlements (who sees which credit union / how much PII)", f"SELECT * FROM {C}.ml_lend_gov.tenant_entitlements")
g.q("As platform analyst (all CUs, PII NONE): masked PII", f"SELECT member_id, institution_id, first_name, ssn, date_of_birth, email, credit_score FROM {C}.ml_lend_gold.dim_member LIMIT 3")
g.q("As platform analyst: rows per credit union", f"SELECT institution_id, count(*) apps FROM {C}.ml_lend_gold.fact_application GROUP BY 1 ORDER BY 1")
sql(f"UPDATE {C}.ml_lend_gov.tenant_entitlements SET institution_id='CU-HPCU', pii_access='LAST4' WHERE principal = current_user()")
g.raw("\n> **Persona switch:** `UPDATE ml_lend_gov.tenant_entitlements SET institution_id='CU-HPCU', pii_access='LAST4' WHERE principal = current_user()`\n")
g.q("As Harbor Point underwriter: only Harbor Point rows", f"SELECT institution_id, count(*) apps FROM {C}.ml_lend_gold.fact_application GROUP BY 1")
g.q("As Harbor Point underwriter: same metric view, filtered", f"SELECT credit_union, MEASURE(applications) applications FROM {C}.ml_lend_semantic.mv_loan_funnel GROUP BY 1")
g.q("As Harbor Point underwriter: names visible, SSN last-4", f"SELECT first_name, ssn, date_of_birth FROM {C}.ml_lend_gold.dim_member LIMIT 3")
sql(f"UPDATE {C}.ml_lend_gov.tenant_entitlements SET institution_id='*', pii_access='NONE' WHERE principal = current_user()")
g.raw("\n> **Reset:** entitlement restored to `*` / `NONE`.\n")
g.q("RBAC grants on schemas", f"SHOW GRANTS ON SCHEMA {C}.ml_lend_semantic")
g.save()

# ---------------------------------------------------------------- 4. ML + serving
m = Doc("04_ml_model_and_serving.md", "Evidence · EPD model (MLflow / UC) + Model Serving")
mv = cli("api", "get", f"/api/2.1/unity-catalog/models/{C}.ml_lend_ml.epd_risk_model/versions")
m.text("UC registered model versions", "\n".join(f"v{v['version']}: {v.get('comment','')}" for v in mv.get("model_versions", [])))
al = cli("api", "get", f"/api/2.1/unity-catalog/models/{C}.ml_lend_ml.epd_risk_model", )
m.text("Aliases", json.dumps(al.get("aliases"), indent=1), "json")
m.q("Batch scores: risk band distribution vs realized EPD (seasoned loans)", f"""SELECT s.risk_band, count(*) applications, round(avg(s.epd_probability),4) avg_predicted
FROM {C}.ml_lend_ml.application_risk_scores s GROUP BY 1 ORDER BY 3""")
m.q("Sample scored applications with SHAP reason codes", f"SELECT application_id, round(epd_probability,4) p, risk_band, reason_1, reason_2, reason_3, model_version FROM {C}.ml_lend_ml.application_risk_scores ORDER BY epd_probability DESC LIMIT 5")
ep = cli("serving-endpoints", "get", ENDPOINT, "-o", "json")
m.text("Serving endpoint state", json.dumps({"name": ep.get("name"), "state": ep.get("state"), "served_entities": [{k: e.get(k) for k in ["entity_name", "entity_version", "workload_size", "scale_to_zero_enabled"]} for e in ep.get("config", {}).get("served_entities", [])]}, indent=1), "json")
rec = {"credit_score": 702.0, "stated_monthly_income": 7500.0, "monthly_debt_payments": 900.0, "dti_stated": 0.2027, "loan_to_income": 0.3556,
       "requested_amount": 32000.0, "term_months": 60.0, "apr": 0.0599, "product_AUTO": 1.0, "product_PERSONAL": 0.0, "product_CARD": 0.0, "product_HELOC": 0.0,
       "channel_DEALER": 1.0, "channel_ONLINE": 0.0, "channel_MOBILE": 0.0, "channel_BRANCH": 0.0, "member_tenure_years": 6.0}
pred = cli("serving-endpoints", "query", ENDPOINT, body={"dataframe_records": [rec]})
m.text("Live endpoint request (Jordan Whitaker, live-demo applicant)", json.dumps({"dataframe_records": [rec]}, indent=1), "json")
m.text("Live endpoint response", json.dumps(pred, indent=1), "json")
m.save()

# ---------------------------------------------------------------- 5. semantic layer, outcomes, Genie, dashboard
s = Doc("05_metric_views_outcomes_genie_dashboard.md", "Evidence · Metric views, outcomes (difference-in-differences), Genie, AI/BI dashboard")
s.q("mv_loan_funnel: pilot vs control, before vs after", f"""SELECT cohort, period, MEASURE(applications) applications, round(MEASURE(approval_rate),4) approval_rate,
 round(MEASURE(pull_through_rate),4) pull_through, round(MEASURE(funded_amount)/1e6,1) funded_mm FROM {C}.ml_lend_semantic.mv_loan_funnel GROUP BY ALL ORDER BY 1 DESC,2 DESC""")
s.q("mv_decision_speed", f"""SELECT cohort, period, round(MEASURE(auto_decision_rate),4) auto_rate, MEASURE(median_decision_minutes) median_min,
 round(MEASURE(decided_within_24h_rate),4) within_24h FROM {C}.ml_lend_semantic.mv_decision_speed GROUP BY ALL ORDER BY 1 DESC,2 DESC""")
s.q("mv_portfolio_risk", f"""SELECT cohort, period, MEASURE(seasoned_loans) seasoned, round(MEASURE(epd_rate),4) epd_rate,
 round(MEASURE(est_loss_on_epd),0) est_loss FROM {C}.ml_lend_semantic.mv_portfolio_risk GROUP BY ALL ORDER BY 1 DESC,2 DESC""")
s.q("Value bridge (every $ in the deck)", f"SELECT to_json(struct(*)) value_bridge FROM {C}.ml_lend_semantic.v_value_bridge")
s.q("ROI assumptions", f"SELECT * FROM {C}.ml_lend_gold.roi_assumptions")
# Genie transcripts
def ask(question):
    r = cli("api", "post", f"/api/2.0/genie/spaces/{GENIE}/start-conversation", body={"content": question})
    cid, mid = r.get("conversation_id"), r.get("message_id")
    for _ in range(80):
        msg = cli("api", "get", f"/api/2.0/genie/spaces/{GENIE}/conversations/{cid}/messages/{mid}")
        if msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"): break
        time.sleep(3)
    out = [f"**Q:** {question}  \n**Status:** {msg.get('status')}"]
    for att in msg.get("attachments", []):
        if "query" in att:
            out.append("**Generated SQL:**\n```sql\n" + att["query"]["query"] + "\n```")
            qr = cli("api", "get", f"/api/2.0/genie/spaces/{GENIE}/conversations/{cid}/messages/{mid}/attachments/{att['attachment_id']}/query-result")
            sr = qr.get("statement_response", {})
            cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            out.append("**Result:**\n\n" + md_table(cols, sr.get("result", {}).get("data_array", []) or [], 12))
        if "text" in att: out.append("**Answer:** " + att["text"]["content"])
    return "\n\n".join(out)
s.raw(f"\n## Genie space `{GENIE}`: live transcripts\n")
for qn in ["Did Lending Intelligence improve pull-through? Compare pilot vs control before and after go-live",
           "Show the 24-hour cliff: pull-through by time to decision",
           "What happened to early payment defaults after go-live?",
           "Why did auto loans through dealers fund more after go-live?"]:
    s.raw("\n---\n" + ask(qn) + "\n")
dash = cli("lakeview", "get", DASH, "-o", "json")
ser = json.loads(dash.get("serialized_dashboard", "{}"))
json.dump(ser, open(os.path.join(OUT, "..", "dashboards", "lending_intelligence_outcomes.lvdash.json"), "w"), indent=1)
s.raw(f"\n## AI/BI dashboard `{DASH}`\nPages: {', '.join(p['displayName'] for p in ser.get('pages', []))} · datasets: {len(ser.get('datasets', []))} · widgets: {sum(len(p.get('layout', [])) for p in ser.get('pages', []))}. Definition committed at `dashboards/lending_intelligence_outcomes.lvdash.json`. Each dataset's live result:\n")
for ds in ser.get("datasets", []):
    q = " ".join(ds.get("queryLines", []))
    cols, rows, err = sql(q)
    s.raw(f"\n### Dataset: {ds['displayName']}\n" + (md_table(cols, rows, 12) if err is None else f"Error: {err}") + "\n")
s.save()

# ---------------------------------------------------------------- 6. app + lakebase
p = Doc("06_app_and_lakebase.md", "Evidence · Databricks App (Lending Intelligence Workbench) + Lakebase")
app = cli("apps", "get", APP, "-o", "json")
p.text("App status", json.dumps({"name": app.get("name"), "url": app.get("url"), "app_status": app.get("app_status"), "compute_status": app.get("compute_status"),
        "active_deployment": {k: app.get("active_deployment", {}).get(k) for k in ["deployment_id", "status", "create_time"]},
        "resources": [r.get("name") for r in app.get("resources", [])], "service_principal_client_id": app.get("service_principal_client_id")}, indent=1), "json")
logs = subprocess.run(CLI + ["apps", "logs", APP], capture_output=True, text=True).stdout
logs = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "x.x.x.x", logs)
logs = "\n".join(l for l in logs.splitlines() if "[APP]" in l or "[SYSTEM]" in l)[-6000:]
p.text("App logs (app/system lines; client IPs redacted)", logs or "(no app/system lines)")
proj = cli("postgres", "get-project", "projects/meridianlink-lending", "-o", "json")
p.text("Lakebase project", json.dumps({k: proj.get(k) for k in ["name", "spec", "status"]}, indent=1, default=str)[:3000], "json")
cdf = cli("postgres", "list-cdf-configs", "projects/meridianlink-lending/branches/production/databases/lending", "-o", "json")
p.text("Lakebase CDF config (Postgres workbench schema → UC ml_lend_ops)", json.dumps(cdf, indent=1), "json")
p.q("Synced table (Delta → Lakebase) visible in UC", f"SELECT routing_reason, count(*) n FROM {C}.ml_lend_ml.underwriting_queue_synced GROUP BY 1")
p.q("Round trip: underwriter decision made in the app, now in Delta (ml_lend_ops)", f"""SELECT application_id, institution_id, decision, underwriter, model_risk_band, ai_income_mismatch, decided_at, left(member_letter, 120) letter_start
FROM {C}.ml_lend_ops.underwriting_decisions ORDER BY decided_at DESC""")
p.q("Live applications submitted through the app", f"""SELECT application_id, product_code, requested_amount, stated_monthly_income, ai_verified_monthly_income, ai_income_variance_pct, risk_band, routing_reason, processing_ms
FROM {C}.ml_lend_ops.live_applications ORDER BY submitted_at DESC""")
p.save()
