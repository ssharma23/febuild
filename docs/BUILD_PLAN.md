# Build Plan — MeridianLink "Speed AND Trust"  (workspace fevm-demo-dnb, us-east-1)
Profile: fevm-demo-dnb | Warehouse: 6ea47fe72fea6233 | Catalog: demo_dnb_catalog (no CREATE CATALOG on metastore)
Models: databricks-claude-haiku-5-5 / sonnet-5-5, databricks-gte-large-en
Account constraint: tag-policy cap reached -> reuse system class.* tags + existing `tenant_isolation_key`; domain needs a tag (OPEN).

## Schemas (prefix ml_lend_)
landing (Volume dataconnect/ + docs/) | bronze | silver | gold | ml | gov | semantic

## Data (own synthetic generator; no customer data)
dim: institutions(4 CUs), branches(~40), products(AUTO/PERSONAL/CARD/HELOC), denial_reasons(12)
members ~60K (SSN, DOB, email, phone, address, stated income, credit score, DTI) - SCD2 changes
applications ~100K over 24 mo: submitted_ts, decided_ts, decision_source AUTO/MANUAL, channel, status, funded_flag
  months 1-12 = BEFORE (manual), months 13-24 = AFTER (auto-decisioning) -> ROI provable from data
documents ~3K pay-stub PDFs (+ live-demo PDF with income mismatch) | member_notes ~20K
loan_payments ~1M (EPD = 60+ DPD in first 6 months)

## Pipeline (Lakeflow SDP, serverless) + Job with FILE-ARRIVAL trigger
bronze: Auto Loader read_files from Volume (Lakeflow Connect file ingestion)
silver: expectations (warn/drop/fail) + quarantine, AUTO CDC SCD2 members
AI: ai_parse_document -> ai_extract income -> income_variance; ai_classify notes; ai_query "path to yes" letters
gold: fact_application, fact_loan_performance, dims, outcome_kpis_monthly
ML: PD/EPD model (LightGBM) MLflow -> UC registry @champion -> serving endpoint + batch score; SHAP reason codes

## Governance
Data Classification on schemas -> class.us_ssn / date_of_birth / email ... auto-tagged
ABAC: mask class.* PII for all except grp ml_lend_pii_readers; row filter on col tagged tenant_isolation_key (group->institution map)
RBAC groups: ml_lend_underwriters, ml_lend_analysts, ml_lend_cu_exec_summit, ml_lend_platform_admins
DQ: expectation metrics + anomaly detection on gold + DQ dashboard page

## Consumption
Metric views: mv_loan_funnel, mv_decision_speed, mv_portfolio_risk
Genie space "Lending Intelligence" (metric views + instructions + benchmarks)
AI/BI dashboard: Executive Outcome | Funnel & Speed | Risk & Trust
Ontology domain "MeridianLink Consumer Lending": pages Loan Funnel & Speed, Credit Risk & Portfolio
Databricks One: CU-exec persona sees dashboard + Genie
App (Streamlit) "Lending Intelligence Workbench" on Lakebase Autoscaling:
  synced table underwriting_queue (gold -> PG), decisions write-back table, PG registered as UC catalog for Genie
  tabs: Queue | Application detail (AI evidence + SHAP + approve/decline) | New Application (live) | Outcomes

## Delivery
DAB repo ~/meridianlink_lending_story/bundle | Deck 7 slides | Demo script 11 min | Q&A bank ~20
