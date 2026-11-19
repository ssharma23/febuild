# Genie Ontology — "MeridianLink Consumer Lending" domain (create in UI when a tag policy frees up)

**Status:** All assets exist (3 metric views, Genie space, dashboard). Domain creation is blocked only by the FEVM account
tag-policy cap (`domains create-domain` requires an existing governed tag). Steps once the quota allows:

```bash
databricks tag-policies create-tag-policy --json '{"tag_key":"meridianlink_consumer_lending","description":"MeridianLink Consumer Lending domain membership","values":[{"name":"true"}]}' -p fevm-demo-dnb
databricks domains create-domain meridianlink_consumer_lending --name "MeridianLink Consumer Lending" \
  --subtitle "Speed and trust in consumer lending: decision speed, pull-through, AI income verification and early-default risk for MeridianLink credit unions." -p fevm-demo-dnb
```
```sql
ALTER SCHEMA demo_dnb_catalog.ml_lend_semantic SET TAGS ('meridianlink_consumer_lending' = 'true');
ALTER SCHEMA demo_dnb_catalog.ml_lend_gold     SET TAGS ('meridianlink_consumer_lending' = 'true');
ALTER SCHEMA demo_dnb_catalog.ml_lend_ml       SET TAGS ('meridianlink_consumer_lending' = 'true');
```

## Domain
| Field | Value |
|---|---|
| Name | MeridianLink Consumer Lending |
| Icon / color | `BANK` (or `CHART`), `#004268` |
| Owners | sonam.s@databricks.com (MeridianLink data platform) |
| Description | Governed consumer-lending knowledge for MeridianLink's credit-union customers. Covers the application → decision → funding → repayment lifecycle across 4 credit unions (PILOT: Summit Valley, Harbor Point — live on Lending Intelligence since 2025-11-01; CONTROL: Riverside Community, Prairie Federal). Certified metrics live in three metric views. PII is masked and each credit union sees only its own data (ABAC). Synthetic data. |
| Metric views | `ml_lend_semantic.mv_loan_funnel`, `mv_decision_speed`, `mv_portfolio_risk` |
| Genie agent | MeridianLink Lending Intelligence — Speed & Trust (`01f1e3d666d91574bd4ffb20588c2ed6`) |
| Dashboard | MeridianLink Lending Intelligence — Outcomes (`01f1e3d70b0c18ed82e52bd9e2d637b6`) |

## Page 1 — "Loan Funnel & Decision Speed"
**Purpose:** how fast we say yes, and what speed is worth.
- **Key definitions:** Pull-through = funded ÷ approved. Auto-decision rate = AUTO decisions ÷ decided. The 24-hour cliff = pull-through drops ~10 pts when a decision takes more than 24h (dealers shop the deal).
- **Certified metrics:** Applications, Approval Rate, Pull-Through Rate, Funded Amount, Est. First-Year NII (`mv_loan_funnel`); Auto-Decision Rate, Median Time to Decision, Decided Within 24h, Manual Reviews, Underwriter Override Rate (`mv_decision_speed`).
- **Headline (difference-in-differences):** auto-decision 31% → 58%; median decision 17 h → 8 min; pull-through +5.5 pts vs control.
- **Ask Genie:** "Did Lending Intelligence improve pull-through?", "Show the 24-hour cliff", "Why did dealer auto loans fund more after go-live?"

## Page 2 — "Credit Risk & Trust"
**Purpose:** speed without losing trust: verified income, explainable risk, governed data.
- **Key definitions:** EPD = 60+ DPD within first 6 installments on seasoned loans. AI income mismatch = stated income > 120% of income extracted from the pay stub by `ai_parse_document` + `ai_extract`.
- **Certified metrics:** Early Payment Default Rate, Est. Loss on Early Defaults, 30+ DPD Rate, Outstanding Principal (`mv_portfolio_risk`); Documents AI-Verified, AI-Detected Income Mismatches (`mv_decision_speed`).
- **Model:** `ml_lend_ml.epd_risk_model@champion` (LightGBM + SHAP reason codes, time-based validation).
- **Governance:** PII auto-classified (`class.*`), masked by ABAC; tenant isolation via `tenant_isolation_key`; SDP expectations + quarantine.
- **Ask Genie:** "What happened to early payment defaults after go-live?", "How many stated-income mismatches did AI catch last month?"
