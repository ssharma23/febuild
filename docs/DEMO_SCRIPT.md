# Demo Script — "Speed AND Trust" (MeridianLink Lending Intelligence)
**Slot:** 15–20 min = ~5 min deck → ~11 min demo → Q&A. **Audience:** SA business + technical leadership.
**Workspace:** https://fevm-demo-dnb.cloud.databricks.com (o=7474649251700104)

## Pre-flight (T-30 min)
- [ ] Warm the SQL warehouse `6ea47fe72fea6233` (open the dashboard once).
- [ ] Wake the model serving endpoint `ml-lend-epd-risk` (scale-to-zero → first call ~30-60 s): run the app's New Application once with APP-LIVE0002.
- [ ] App: https://meridianlink-lending-workbench-7474649251700104.aws.databricksapps.com (Okta + consent on first open). Outcomes tab shows Summit Valley only, because the app runs as the SVCU underwriter (that's the row filter working; say so).
- [ ] Lakebase endpoint ACTIVE (`databricks postgres list-endpoints projects/meridianlink-lending/branches/production -p fevm-demo-dnb`).
- [ ] Tabs open, in order: ① Databricks One → dashboard · ② Lakeflow pipeline graph · ③ Catalog Explorer `ml_lend_gold.dim_member` · ④ SQL editor with the governance cells · ⑤ Workbench app · ⑥ Genie space · ⑦ Model registry `ml_lend_ml.epd_risk_model`.
- [ ] Entitlement reset: `SELECT * FROM demo_dnb_catalog.ml_lend_gov.tenant_entitlements` → my row = `*`, `NONE`.
- [ ] Clean Workbench decisions from rehearsals (optional): `DELETE FROM workbench.underwriting_decisions WHERE application_id LIKE 'APP-LIVE%'`.

---

## 0. Deck (≈5 min) — see deck speaker notes
Hook → 24-hour cliff → thesis → architecture → proof → value → ask.

## 1. Outcome first — Databricks One + AI/BI dashboard (1:00)
**Open:** Databricks One → "MeridianLink Lending Intelligence — Outcomes", page *Executive Outcome*.
> "Before I show how it's built, here's what it did. Two credit unions went live on Lending Intelligence in November 2025; two didn't — that's our control group.
> Auto-decisions went from 31% to 58%, median decision time from 17 hours to 8 minutes, pull-through is up 5.5 points *versus control*, and early defaults fell 1.2 points.
> For a 40,000-application credit union that's ~$3.6M a year — and notice the biggest bar isn't speed, it's **trust**: losses avoided because AI verified income."
**Click:** *Funnel & Speed* → the 24-hour cliff bar (73% → 57%).

## 2. Land & trust the data — Lakeflow (2:00)
**Open:** pipeline *MeridianLink Lending · Data Connect Medallion* graph.
> "MeridianLink already ships Data Connect extracts to every credit union. Lakeflow picks the files up incrementally with Auto Loader — no ingestion code."
- Point at **bronze** (files → streaming tables, schema-on-read, source file lineage).
- **silver.applications** = AUTO CDC SCD1 → "re-sent and updated records collapse to the latest status".
- **silver.members** = SCD2 history.
- Click a silver table → **Data quality** tab: expectations (drop / warn / fail-update), **quarantine** tables (400 rejected records with the failed rule).
- **document_income_extraction** → "here AI Functions run *inside* the pipeline: `ai_parse_document` + `ai_extract` on 2,300 pay-stub PDFs, incrementally — each doc parsed once."
**Proof line:** "Against ground truth, extraction was within 2% on 100% of docs, and it flagged all 479 inflated incomes with 2 false positives."

## 3. Protect it — classification, ABAC, RBAC (2:00)
**Open:** Catalog Explorer → `ml_lend_gold.dim_member` → columns show `class.us_ssn`, `class.email_address`… tags; **Policies** tab shows 3 masks + 1 row filter.
> "Data Classification found the PII — we didn't hand-tag it. The policies attach to the *tag*, not the table, so the next table with an SSN is protected on day one."
**SQL editor (prepared cells):**
```sql
-- 1. As MeridianLink platform analyst: all credit unions, no PII
SELECT first_name, ssn, date_of_birth, email, credit_score FROM demo_dnb_catalog.ml_lend_gold.dim_member LIMIT 5;
SELECT credit_union, MEASURE(applications) FROM demo_dnb_catalog.ml_lend_semantic.mv_loan_funnel GROUP BY 1;
-- 2. Become a Harbor Point underwriter (one row in the entitlement table)
UPDATE demo_dnb_catalog.ml_lend_gov.tenant_entitlements SET institution_id='CU-HPCU', pii_access='LAST4' WHERE principal = current_user();
-- re-run both queries → only Harbor Point; names visible, SSN = XXX-XX-1234
-- 3. Reset
UPDATE demo_dnb_catalog.ml_lend_gov.tenant_entitlements SET institution_id='*', pii_access='NONE' WHERE principal = current_user();
```
> "Same table, same metric view, same Genie space — the platform decides what each tenant sees. That's what lets MeridianLink run *one* platform for every credit union."

## 4. Decide & act — the live moment in the Workbench app (3:00)
**Open:** Lending Intelligence Workbench → *New Application*.
> "Jordan applies for a $32,000 auto loan at the dealer and says he earns $7,500 a month."
- Select pay stub **APP-LIVE0001** → **Submit**. Narrate while it runs (~30 s: parse ~23 s, extract ~5 s, score 0.1 s): "it's reading the PDF the way an underwriter would, then the model scores it."
> "The pay stub says $1,938 bi-weekly — $4,200 a month. 79% over. Instead of auto-approving a loan that's likely to default, it routes to Marcus with the evidence."
- Go to *Underwriting Queue* → Jordan is on top (INCOME_MISMATCH). Open *Application Review*: stated vs verified income, extracted fields, EPD score + 3 reason codes.
- Click **Decline** → the "path to yes" letter is drafted live (`ai_query`, Claude) → saved to **Lakebase**.
> "Operational write-back lands in Lakebase Postgres in milliseconds; change-data-feed brings it back to Delta so Genie sees it."
- Back in Databricks: run job **"MeridianLink Lending · Workbench decisions → Delta"** (~1 min, or pre-run it), then show `SELECT * FROM demo_dnb_catalog.ml_lend_ops.underwriting_decisions`: the decision + letter is now governed in UC. (Lakebase CDF `workbench_to_delta` is also configured; it is Beta and had not materialized in testing, so the job is the reliable path.)
- (Optional, if time) submit **APP-LIVE0002** → auto-approved in seconds: "that's the 58%."

## 5. Explain it — Genie + Ontology (2:00)
**Open:** Genie space *MeridianLink Lending Intelligence — Speed & Trust*.
1. "Did Lending Intelligence improve pull-through? Compare pilot vs control before and after go-live" → difference-in-differences +5.5 pts.
2. "Why did auto loans through dealers fund more after go-live?" → pull-through 66.9% → 73.4%, median 1,075 min → 7 min.
> "Genie answers from three certified **metric views** — the same definitions the dashboard and app use. Those metric views plus two curated pages make up the **Consumer Lending** ontology domain."
Mention: "If I were a Riverside CU executive, Genie would only see Riverside — same ABAC."

## 6. The model (0:45) — only if time / or in Q&A
**Open:** UC model `ml_lend_ml.epd_risk_model@champion` → version description (AUC, top-20% capture), MLflow run (feature importance), serving endpoint `ml-lend-epd-risk`.
> "LightGBM with SHAP reason codes — every decline has explainable principal reasons for adverse-action notices. Time-based validation: trained on 2024–25, tested on 2026."

## Close (0:15)
> "Speed **and** trust, on one governed platform — and because it's multi-tenant by policy, MeridianLink can ship it to every credit union it serves."

---
## Fallbacks
| If… | Then… |
|---|---|
| Serving endpoint cold / errors | Show `ml_lend_ml.application_risk_scores` for the app; explain scale-to-zero |
| App slow / down | Screenshot slides in deck appendix; run the same SQL (`ai_parse_document` on `/documents/demo/`) in SQL editor |
| Genie answer drifts | Use the saved example SQL / sample question chips |
| Warehouse cold | Pre-warm; dashboard has cached results |
