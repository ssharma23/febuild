"""AI/BI dashboard 'MeridianLink Lending Intelligence — Outcomes'. Usage: python3 build_dashboard.py [create|<dashboard_id>]"""
import json, secrets, subprocess, sys
C = "demo_dnb_catalog"; G = f"{C}.ml_lend_gold"; S = f"{C}.ml_lend_semantic"; M = f"{C}.ml_lend_ml"
WH = "6ea47fe72fea6233"; PROFILE = "fevm-demo-dnb"; HOST = "https://fevm-demo-dnb.cloud.databricks.com"
PARENT = "/Workspace/Users/sonam.s@databricks.com/meridianlink_lending"
PIPELINE_ID = open("/Users/sonam.s/meridianlink_lending_story/.pipeline_id").read().strip()
GENIE = open("/Users/sonam.s/meridianlink_lending_story/.genie_space_id").read().strip()
NAVY, DEEP, BLUE, TEAL, CYAN, GREEN, SLATE, RED = "#004268", "#15295A", "#0061A4", "#007FA4", "#00B9F2", "#6EC068", "#727D82", "#C62828"
COHORT_COLORS = [{"value": "PILOT", "color": BLUE}, {"value": "CONTROL", "color": SLATE}]

def hid(): return secrets.token_hex(4)
datasets = []
def ds(display, query):
    n = "ds_" + hid(); datasets.append({"name": n, "displayName": display, "queryLines": [query]}); return n

# ------------------------------------------------------------------ datasets
d_val = ds("Value bridge", f"""SELECT round(100*auto_decision_rate_before,1) auto_before, round(100*auto_decision_rate_after,1) auto_after,
  round(median_decision_minutes_before/60,1) median_hours_before, round(median_decision_minutes_after,1) median_minutes_after,
  round(100*pull_through_lift_did,1) pull_through_lift_pts, round(100*epd_change_did,2) epd_change_pts,
  round((value_pull_through_nii+value_underwriter_capacity+value_epd_losses_avoided+value_declines_recovered_nii)*scale_to_reference_cu/1e6,2) value_ref_cu_mm,
  round((value_pull_through_nii+value_underwriter_capacity+value_epd_losses_avoided+value_declines_recovered_nii)/1e6,2) value_pilot_mm,
  extra_funded_loans_yr, underwriter_hours_saved_yr, declines_recovered_yr
FROM {S}.v_value_bridge""")
d_bridge = ds("Value components (reference CU)", f"""SELECT * FROM (SELECT stack(4,
  '1 · Faster decisions → more funded loans', round(CAST(value_pull_through_nii AS DOUBLE)*scale_to_reference_cu),
  '2 · Underwriter capacity released', round(CAST(value_underwriter_capacity AS DOUBLE)*scale_to_reference_cu),
  '3 · Early-default losses avoided (AI income check)', round(CAST(value_epd_losses_avoided AS DOUBLE)*scale_to_reference_cu),
  '4 · Declines turned into funded loans', round(CAST(value_declines_recovered_nii AS DOUBLE)*scale_to_reference_cu)) AS (value_lever, annual_value_usd)
FROM {S}.v_value_bridge)""")
d_did = ds("Pilot vs control", f"""SELECT cohort, period, MEASURE(applications) applications, round(100*MEASURE(approval_rate),1) approval_rate_pct,
  round(100*MEASURE(pull_through_rate),1) pull_through_pct, round(MEASURE(funded_amount)/1e6,1) funded_mm
FROM {S}.mv_loan_funnel GROUP BY ALL ORDER BY cohort DESC, period DESC""")
d_speed = ds("Pilot vs control speed", f"""SELECT cohort, period, round(100*MEASURE(auto_decision_rate),1) auto_decision_pct,
  MEASURE(median_decision_minutes) median_minutes, round(100*MEASURE(decided_within_24h_rate),1) within_24h_pct
FROM {S}.mv_decision_speed GROUP BY ALL ORDER BY cohort DESC, period DESC""")
d_trend = ds("Monthly pull-through", f"""SELECT submitted_month, cohort, round(100*MEASURE(pull_through_rate),1) pull_through_pct
FROM {S}.mv_loan_funnel WHERE submitted_month < '2026-11-01' GROUP BY ALL""")
d_ttd = ds("Monthly median decision time", f"""SELECT submitted_month, cohort, round(MEASURE(median_decision_minutes)/60,2) median_hours,
  round(100*MEASURE(auto_decision_rate),1) auto_decision_pct FROM {S}.mv_decision_speed GROUP BY ALL""")
d_cliff = ds("24-hour cliff", f"""SELECT CASE WHEN decision_minutes <= 60 THEN '1 · under 1 hour' WHEN decision_minutes <= 240 THEN '2 · 1-4 hours'
  WHEN decision_minutes <= 1440 THEN '3 · 4-24 hours' ELSE '4 · over 24 hours' END decision_time,
  round(100*avg(CASE WHEN is_funded THEN 1.0 ELSE 0 END),1) pull_through_pct, count(*) approved
FROM {G}.fact_application WHERE is_approved GROUP BY 1""")
d_engine = ds("Decision engine mix (pilot)", f"""SELECT submitted_month, decision_engine, MEASURE(decided_applications) decisions
FROM {S}.mv_decision_speed WHERE cohort = 'PILOT' GROUP BY ALL""")
d_channel = ds("Channel lift (pilot)", f"""SELECT channel, period, round(100*MEASURE(pull_through_rate),1) pull_through_pct
FROM {S}.mv_loan_funnel WHERE cohort = 'PILOT' GROUP BY ALL""")
d_epd = ds("EPD by cohort", f"""SELECT concat(cohort, ' · ', period) cohort_period, cohort, period, round(100*MEASURE(epd_rate),2) epd_pct, MEASURE(seasoned_loans) seasoned
FROM {S}.mv_portfolio_risk GROUP BY ALL""")
d_ai = ds("AI income verification", f"""SELECT date_trunc('WEEK', submitted_ts) week, count(*) documents_verified,
  sum(CASE WHEN ai_income_mismatch_flag THEN 1 ELSE 0 END) mismatches FROM {G}.fact_application WHERE ai_verified_monthly_income IS NOT NULL GROUP BY 1""")
d_band = ds("Model risk bands", f"""SELECT risk_band, count(*) applications, round(100*avg(epd_probability),2) avg_epd_pct FROM {M}.application_risk_scores GROUP BY 1""")
d_notes = ds("AI note categories", f"""SELECT note_category, count(*) notes FROM {G}.member_notes_enriched WHERE note_category IS NOT NULL GROUP BY 1""")
d_dq = ds("Expectations", f"""WITH exp AS (
  SELECT e.name expectation, e.dataset dataset, coalesce(e.passed_records,0) passed, coalesce(e.failed_records,0) failed
  FROM event_log('{PIPELINE_ID}'), LATERAL explode(from_json(details:flow_progress:data_quality:expectations,
       'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t(e)
  WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality:expectations IS NOT NULL)
SELECT expectation, sum(passed) passed_records, sum(failed) failed_records,
  round(100*sum(passed)/nullif(sum(passed+failed),0),3) pass_rate_pct FROM exp GROUP BY expectation""")
d_quar = ds("Quarantine", f"""SELECT 'applications' entity, failed_rule, count(*) records FROM {C}.ml_lend_silver.applications_quarantine GROUP BY ALL
UNION ALL SELECT 'members', failed_rule, count(*) FROM {C}.ml_lend_silver.members_quarantine GROUP BY ALL""")
d_tags = ds("Governed columns", f"""SELECT schema_name || '.' || table_name tbl, column_name, tag_name, coalesce(tag_value,'') tag_value
FROM {C}.information_schema.column_tags WHERE schema_name LIKE 'ml_lend%' AND (tag_name LIKE 'class.%' OR tag_name = 'tenant_isolation_key')""")

# ------------------------------------------------------------------ widgets
def text(md): return {"name": "t_" + hid(), "multilineTextboxSpec": {"lines": [md]}}
def qry(dsn, fields): return [{"name": "main_query", "query": {"datasetName": dsn, "fields": [{"name": f, "expression": f"`{f}`"} for f in fields], "disaggregated": True}}]
def counter(dsn, field, title):
    return {"name": "c_" + hid(), "queries": qry(dsn, [field]), "spec": {"version": 2, "widgetType": "counter",
            "encodings": {"value": {"fieldName": field, "displayName": title}}, "frame": {"showTitle": True, "title": title}}}
def bar(dsn, x, y, title, color=NAVY, xt="", yt="", horizontal=False, series=None, colors=None, stack=False):
    cat = {"fieldName": x, "scale": {"type": "categorical", "sort": {"by": "natural-order"}}, "displayName": xt or x}
    val = {"fieldName": y, "scale": {"type": "quantitative"}, "displayName": yt or y}
    enc = {"y": cat, "x": val} if horizontal else {"x": cat, "y": val}
    fields = [x, y]
    if series:
        enc["color"] = {"fieldName": series, "scale": {"type": "categorical", **({"mappings": colors} if colors else {})}, "displayName": series}
        fields.append(series)
    enc["label"] = {"show": True}
    spec = {"version": 3, "widgetType": "bar", "encodings": enc, "frame": {"showTitle": True, "title": title}}
    if not series: spec["mark"] = {"colors": [color]}
    if series and not stack: spec["mark"] = {"layout": "group"}
    return {"name": "b_" + hid(), "queries": qry(dsn, fields), "spec": spec}
def line(dsn, x, y, title, series=None, colors=None, yt=""):
    enc = {"x": {"fieldName": x, "scale": {"type": "temporal"}, "displayName": "Month"},
           "y": {"fieldName": y, "scale": {"type": "quantitative"}, "displayName": yt or y}}
    fields = [x, y]
    if series:
        enc["color"] = {"fieldName": series, "scale": {"type": "categorical", **({"mappings": colors} if colors else {})}, "displayName": series}; fields.append(series)
    spec = {"version": 3, "widgetType": "line", "encodings": enc, "frame": {"showTitle": True, "title": title}}
    if not series: spec["mark"] = {"colors": [NAVY]}
    return {"name": "l_" + hid(), "queries": qry(dsn, fields), "spec": spec}
def table(dsn, cols, title):
    return {"name": "tb_" + hid(), "queries": qry(dsn, [c for c, _ in cols]), "spec": {"version": 2, "widgetType": "table",
            "encodings": {"columns": [{"fieldName": c, "displayName": d} for c, d in cols]}, "frame": {"showTitle": True, "title": title}}}
def pie(dsn, cat, val, title):
    return {"name": "p_" + hid(), "queries": qry(dsn, [val, cat]), "spec": {"version": 3, "widgetType": "pie",
            "encodings": {"angle": {"fieldName": val, "scale": {"type": "quantitative"}, "displayName": val},
                          "color": {"fieldName": cat, "scale": {"type": "categorical"}, "displayName": cat}}, "frame": {"showTitle": True, "title": title}}}

pages = []
def page(name, items):
    pages.append({"name": "pg_" + hid(), "displayName": name, "pageType": "PAGE_TYPE_CANVAS",
                  "layout": [{"widget": w, "position": {"x": x, "y": y, "width": wd, "height": h}} for w, x, y, wd, h in items]})

HDR = ("## MeridianLink Lending Intelligence · Speed **and** Trust\n"
       "PILOT credit unions (Summit Valley, Harbor Point) live since **2025-11-01** vs CONTROL (Riverside, Prairie Federal). "
       "All lifts are difference-in-differences. Synthetic data.")
LINKS = f"###### [Ask Genie →]({HOST}/genie/rooms/{GENIE})  \n###### [Lakeflow pipeline →]({HOST}/pipelines/{PIPELINE_ID})"

page("Executive Outcome", [
  (text(HDR), 0, 0, 5, 2), (text(LINKS), 5, 0, 1, 2),
  (counter(d_val, "auto_after", "Auto-decision rate after (%)"), 0, 2, 1, 3),
  (counter(d_val, "median_minutes_after", "Median time to decision after (min)"), 1, 2, 1, 3),
  (counter(d_val, "pull_through_lift_pts", "Pull-through lift vs control (pts)"), 2, 2, 1, 3),
  (counter(d_val, "epd_change_pts", "Early-default change vs control (pts)"), 3, 2, 1, 3),
  (counter(d_val, "value_ref_cu_mm", "Annual value per 40K-app CU ($M)"), 4, 2, 1, 3),
  (counter(d_val, "value_pilot_mm", "Annual value, pilot CUs ($M)"), 5, 2, 1, 3),
  (bar(d_bridge, "value_lever", "annual_value_usd", "Where the value comes from (reference 40K-app credit union, USD / year)", BLUE, "Lever", "USD / year", horizontal=True), 0, 5, 3, 6),
  (line(d_trend, "submitted_month", "pull_through_pct", "Pull-through by month: pilot vs control (go-live Nov-2025)", "cohort", COHORT_COLORS, "Pull-through %"), 3, 5, 3, 6),
  (table(d_did, [("cohort","Cohort"),("period","Period"),("applications","Applications"),("approval_rate_pct","Approval %"),("pull_through_pct","Pull-through %"),("funded_mm","Funded $M")], "Funnel: the four cells of the experiment"), 0, 11, 3, 5),
  (table(d_speed, [("cohort","Cohort"),("period","Period"),("auto_decision_pct","Auto-decision %"),("median_minutes","Median minutes"),("within_24h_pct","Decided < 24h %")], "Speed: the four cells of the experiment"), 3, 11, 3, 5),
])
page("Funnel & Speed", [
  (text("### The 24-hour cliff: every hour of waiting costs funded loans"), 0, 0, 6, 1),
  (bar(d_cliff, "decision_time", "pull_through_pct", "Pull-through by time to decision (all approved applications)", NAVY, "Time to decision", "Pull-through %"), 0, 1, 3, 6),
  (line(d_ttd, "submitted_month", "median_hours", "Median time to decision (hours) by month", "cohort", COHORT_COLORS, "Median hours"), 3, 1, 3, 6),
  (bar(d_engine, "submitted_month", "decisions", "Pilot decisions by engine: legacy rules → Lending Intelligence", series="decision_engine", stack=True,
       colors=[{"value": "LENDING_INTELLIGENCE", "color": GREEN}, {"value": "LEGACY_RULES", "color": CYAN}, {"value": "UNDERWRITER", "color": DEEP}]), 0, 7, 4, 6),
  (bar(d_channel, "channel", "pull_through_pct", "Pilot pull-through by channel, before vs after", series="period",
       colors=[{"value": "BEFORE", "color": SLATE}, {"value": "AFTER", "color": BLUE}]), 4, 7, 2, 6),
])
page("Risk & Trust", [
  (text("### Trust: AI-verified income, explainable risk, governed and quality-checked data"), 0, 0, 6, 1),
  (bar(d_epd, "cohort_period", "epd_pct", "Early payment default rate (60+ DPD in first 6 payments, seasoned loans)", RED, "Cohort · period", "EPD %"), 0, 1, 2, 6),
  (bar(d_ai, "week", "mismatches", "AI pay-stub verification: stated-income mismatches caught per week", TEAL, "Week", "Mismatches"), 2, 1, 2, 6),
  (bar(d_band, "risk_band", "applications", "EPD model risk bands (recent applications)", BLUE, "Risk band", "Applications"), 4, 1, 2, 6),
  (table(d_dq, [("expectation","Expectation"),("passed_records","Passed"),("failed_records","Failed"),("pass_rate_pct","Pass %")], "Lakeflow expectations (pipeline event log)"), 0, 7, 2, 6),
  (table(d_quar, [("entity","Entity"),("failed_rule","Rule"),("records","Quarantined")], "Quarantined records by rule"), 2, 7, 2, 6),
  (pie(d_notes, "note_category", "notes", "Member & officer notes by AI category (ai_classify)"), 4, 7, 2, 6),
  (table(d_tags, [("tbl","Table"),("column_name","Column"),("tag_name","Tag"),("tag_value","Value")], "Columns governed by tags (Data Classification + tenant isolation → ABAC)"), 0, 13, 6, 6),
])

serialized = {"datasets": datasets, "pages": pages}
body = {"display_name": "MeridianLink Lending Intelligence — Outcomes", "warehouse_id": WH, "parent_path": PARENT, "serialized_dashboard": json.dumps(serialized)}
open("/tmp/lend_dash.json", "w").write(json.dumps(body))
D = ["/opt/homebrew/bin/databricks", "--profile", PROFILE]
mode = sys.argv[1] if len(sys.argv) > 1 else "create"
if mode == "create":
    out = subprocess.run(D + ["api", "post", "/api/2.0/lakeview/dashboards", "--json", "@/tmp/lend_dash.json"], capture_output=True, text=True)
else:
    body.pop("parent_path"); open("/tmp/lend_dash.json", "w").write(json.dumps(body))
    out = subprocess.run(D + ["api", "patch", f"/api/2.0/lakeview/dashboards/{mode}", "--json", "@/tmp/lend_dash.json"], capture_output=True, text=True)
r = json.loads(out.stdout or "{}"); did = r.get("dashboard_id")
print("DASHBOARD_ID:", did, out.stderr[:800])
if did:
    pub = subprocess.run(D + ["api", "post", f"/api/2.0/lakeview/dashboards/{did}/published", "--json", json.dumps({"warehouse_id": WH, "embed_credentials": False})], capture_output=True, text=True)
    print("PUBLISH:", pub.stdout[:200], pub.stderr[:300])
    open("/Users/sonam.s/meridianlink_lending_story/.dashboard_id", "w").write(did)
