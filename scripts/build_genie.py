"""Build / update the Genie space 'MeridianLink Lending Intelligence'. Usage: python3 build_genie.py [create|<space_id>]"""
import sys, json, uuid, subprocess, os
sys.path.insert(0, "/Users/sonam.s/.vibe/marketplace/plugins/fe-internal-tools/skills/genie-rooms/resources")
from genie_space_builder import GenieSpaceBuilder

C = "demo_dnb_catalog"; G = f"{C}.ml_lend_gold"; S = f"{C}.ml_lend_semantic"; M = f"{C}.ml_lend_ml"
WH = "6ea47fe72fea6233"

space = GenieSpaceBuilder(
    title="MeridianLink Lending Intelligence — Speed & Trust",
    description=("Ask about consumer lending outcomes at MeridianLink credit unions: time-to-decision, auto-decision rate, approvals, "
                 "pull-through, funded volume, early payment default, AI income verification and member notes. Compare PILOT credit unions "
                 "(live on Lending Intelligence since 2025-11-01) with CONTROL credit unions, before vs after go-live."),
    warehouse_id=WH,
)
space.set_instructions(
    "ROLE: You support credit-union lending executives (e.g. Priya, VP Lending at Summit Valley CU) and MeridianLink product leaders.\n\n"
    "PREFER THE METRIC VIEWS: mv_loan_funnel (applications, approvals, pull-through, funded amount, NII), mv_decision_speed (auto-decision rate, "
    "time to decision, 24-hour cliff, AI mismatches) and mv_portfolio_risk (early payment default, expected loss). Query them with MEASURE(<measure>) "
    "and GROUP BY dimensions. Use fact tables only for row-level detail.\n\n"
    "KEY RULES:\n"
    "- Do NOT apply a default 30-day window. Unless the user gives a time range, use ALL data and split by period (BEFORE / AFTER).\n"
    "- cohort: PILOT = Summit Valley CU + Harbor Point CU (live on Lending Intelligence from 2025-11-01). CONTROL = Riverside Community CU + Prairie Federal CU "
    "(legacy rules engine + manual underwriting). period: BEFORE = submitted before 2025-11-01, AFTER = on/after.\n"
    "- 'Impact', 'lift' or 'did it work' = difference-in-differences: (PILOT AFTER - PILOT BEFORE) - (CONTROL AFTER - CONTROL BEFORE). Always show all four cells.\n"
    "- Pull-through rate = funded loans / approved applications. Approval rate = approved / all applications.\n"
    "- Early payment default (EPD) = 60+ days past due within the first 6 installments; compute only on seasoned loans (is_seasoned = TRUE). Use mv_portfolio_risk.epd_rate.\n"
    "- Dollar value: first-year net interest income = funded amount x 3.5%; expected loss on EPD = outstanding principal x 55%; underwriter time = 45 min per manual file "
    "(20 min when AI-assisted) at $48/hour. These assumptions live in ml_lend_gold.roi_assumptions — cite them when you show dollars.\n"
    "- decision_engine: LEGACY_RULES, LENDING_INTELLIGENCE (EPD model + AI document verification), UNDERWRITER (manual).\n"
    "- AI income mismatch = stated income more than 20% above the income AI extracted from the member's pay stub (ai_income_mismatch_flag).\n"
    "- Never return SSN, date of birth, email, phone or street address. Member-level PII is masked by policy for analysts.\n"
    "- Format rates as percentages with one decimal, money in USD with no decimals, time to decision in minutes if < 120 else hours.\n"
    "- Keep answers short: lead with the headline number, then a compact table."
)
for t in [f"{S}.mv_loan_funnel", f"{S}.mv_decision_speed", f"{S}.mv_portfolio_risk",
          f"{G}.fact_application", f"{G}.fact_loan_performance", f"{G}.dim_institution", f"{G}.dim_product", f"{G}.dim_denial_reason",
          f"{G}.member_notes_enriched", f"{G}.roi_assumptions", f"{M}.application_risk_scores"]:
    space.add_table(t)

def join(l, r, cond, rt="FROM_RELATIONSHIP_TYPE_MANY_TO_ONE"):
    ln, rn = l.split(".")[-1], r.split(".")[-1]
    space.add_join_spec({"left": {"identifier": l, "alias": ln}, "right": {"identifier": r, "alias": rn},
                         "sql": [cond.format(l=ln, r=rn), f"--rt={rt}--"]})
join(f"{G}.fact_application", f"{G}.dim_institution", "`{l}`.`institution_id` = `{r}`.`institution_id`")
join(f"{G}.fact_application", f"{G}.dim_product", "`{l}`.`product_code` = `{r}`.`product_code`")
join(f"{G}.fact_application", f"{G}.dim_denial_reason", "`{l}`.`denial_reason_id` = `{r}`.`denial_reason_id`")
join(f"{G}.fact_loan_performance", f"{G}.fact_application", "`{l}`.`application_id` = `{r}`.`application_id`", "FROM_RELATIONSHIP_TYPE_ONE_TO_ONE")
join(f"{G}.member_notes_enriched", f"{G}.fact_application", "`{l}`.`application_id` = `{r}`.`application_id`")
join(f"{M}.application_risk_scores", f"{G}.fact_application", "`{l}`.`application_id` = `{r}`.`application_id`", "FROM_RELATIONSHIP_TYPE_ONE_TO_ONE")

ex = [
 ("Did Lending Intelligence improve pull-through? Show the difference-in-differences",
  f"SELECT cohort, period, MEASURE(applications) AS applications, MEASURE(approved_applications) AS approved, MEASURE(funded_loans) AS funded,\n"
  f"  ROUND(MEASURE(pull_through_rate), 4) AS pull_through_rate\nFROM {S}.mv_loan_funnel GROUP BY cohort, period ORDER BY cohort DESC, period DESC"),
 ("How fast are we deciding loans and how many are automated, pilot vs control?",
  f"SELECT cohort, period, ROUND(MEASURE(auto_decision_rate), 4) AS auto_decision_rate, MEASURE(median_decision_minutes) AS median_minutes,\n"
  f"  ROUND(MEASURE(p90_decision_hours), 1) AS p90_hours, ROUND(MEASURE(decided_within_24h_rate), 4) AS within_24h\n"
  f"FROM {S}.mv_decision_speed GROUP BY cohort, period ORDER BY cohort DESC, period DESC"),
 ("Show the 24-hour cliff: pull-through by time to decision",
  f"SELECT CASE WHEN decision_minutes <= 60 THEN '1 · under 1 hour' WHEN decision_minutes <= 240 THEN '2 · 1-4 hours' WHEN decision_minutes <= 1440 THEN '3 · 4-24 hours' ELSE '4 · over 24 hours' END AS decision_time_bucket,\n"
  f"  COUNT(*) AS approved, ROUND(AVG(CASE WHEN is_funded THEN 1.0 ELSE 0 END), 4) AS pull_through_rate\n"
  f"FROM {G}.fact_application WHERE is_approved GROUP BY 1 ORDER BY 1"),
 ("What happened to early payment defaults after go-live?",
  f"SELECT cohort, period, MEASURE(seasoned_loans) AS seasoned_loans, MEASURE(epd_loans) AS epd_loans, ROUND(MEASURE(epd_rate), 4) AS epd_rate,\n"
  f"  ROUND(MEASURE(est_loss_on_epd), 0) AS est_loss_on_epd FROM {S}.mv_portfolio_risk GROUP BY cohort, period ORDER BY cohort DESC, period DESC"),
 ("Monthly pull-through trend pilot vs control",
  f"SELECT submitted_month, cohort, ROUND(MEASURE(pull_through_rate), 4) AS pull_through_rate, MEASURE(applications) AS applications\n"
  f"FROM {S}.mv_loan_funnel GROUP BY submitted_month, cohort ORDER BY submitted_month, cohort"),
 ("How many stated-income mismatches did AI catch by month?",
  f"SELECT submitted_month, MEASURE(documents_ai_verified) AS documents_verified, MEASURE(ai_income_mismatches) AS mismatches\n"
  f"FROM {S}.mv_decision_speed WHERE cohort = 'PILOT' GROUP BY submitted_month HAVING MEASURE(documents_ai_verified) > 0 ORDER BY submitted_month"),
 ("Top denial reasons after go-live by cohort",
  f"SELECT f.cohort, r.reason_code, r.reason_description, COUNT(*) AS declines\nFROM {G}.fact_application f JOIN {G}.dim_denial_reason r ON f.denial_reason_id = r.denial_reason_id\n"
  f"WHERE f.is_declined AND f.period = 'AFTER' GROUP BY ALL ORDER BY f.cohort, declines DESC"),
 ("How many declines turned into funded loans?",
  f"SELECT cohort, period, MEASURE(declined_applications) AS declines, MEASURE(reapplications_funded) AS declines_turned_into_funded_loans\n"
  f"FROM {S}.mv_loan_funnel GROUP BY cohort, period ORDER BY cohort DESC, period DESC"),
 ("What are members and loan officers writing about in notes recently?",
  f"SELECT note_category, cohort, COUNT(*) AS notes FROM {G}.member_notes_enriched WHERE note_category IS NOT NULL GROUP BY ALL ORDER BY notes DESC"),
 ("Funded volume and first-year interest income by credit union after go-live",
  f"SELECT credit_union, cohort, MEASURE(funded_loans) AS funded_loans, ROUND(MEASURE(funded_amount), 0) AS funded_amount,\n"
  f"  ROUND(MEASURE(est_first_year_interest_income), 0) AS first_year_nii FROM {S}.mv_loan_funnel WHERE period = 'AFTER' GROUP BY ALL ORDER BY funded_amount DESC"),
]
for q, s in ex:
    space.add_example_sql(title=q, sql=s)

samples = [
    "Did Lending Intelligence improve pull-through? Compare pilot vs control before and after go-live",
    "How has median time to decision changed for Summit Valley CU?",
    "Show the 24-hour cliff: pull-through by time to decision",
    "What happened to early payment defaults after go-live?",
    "How many stated-income mismatches did AI catch last month?",
    "Why did auto loans through dealers fund more after go-live?",
]
d = space.to_dict()
d.setdefault("config", {})["sample_questions"] = [{"id": uuid.uuid4().hex, "question": [q]} for q in samples]
for path in GenieSpaceBuilder.ID_LIST_PATHS:
    cur = d
    for p in path[:-1]:
        cur = cur.get(p, {})
    if isinstance(cur.get(path[-1]), list):
        cur[path[-1]].sort(key=lambda x: x["id"])
os.makedirs("/Users/sonam.s/meridianlink_lending_story/genie", exist_ok=True)
open("/Users/sonam.s/meridianlink_lending_story/genie/serialized_space.json", "w").write(json.dumps(d, indent=1))
body = {"title": space.title, "description": space.description, "warehouse_id": WH, "serialized_space": json.dumps(d)}
open("/tmp/genie_body.json", "w").write(json.dumps(body))
mode = sys.argv[1] if len(sys.argv) > 1 else "create"
cmd = (["/opt/homebrew/bin/databricks", "api", "post", "/api/2.0/genie/spaces", "--json", "@/tmp/genie_body.json"] if mode == "create"
       else ["/opt/homebrew/bin/databricks", "api", "patch", f"/api/2.0/genie/spaces/{mode}", "--json", "@/tmp/genie_body.json"])
out = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "DATABRICKS_CONFIG_PROFILE": "fevm-demo-dnb"})
print(out.stdout[:600], out.stderr[:1500])
