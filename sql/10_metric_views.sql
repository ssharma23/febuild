CREATE OR REPLACE VIEW demo_dnb_catalog.ml_lend_semantic.mv_loan_funnel
WITH METRICS LANGUAGE YAML
COMMENT 'Consumer Lending ontology · Loan funnel: applications -> approvals -> funded loans. Pull-through = funded / approved. Use cohort (PILOT vs CONTROL) x period (BEFORE vs AFTER 2025-11-01 go-live) to measure the Lending Intelligence lift.'
AS $$
version: 1.1
source: demo_dnb_catalog.ml_lend_gold.fact_application
joins:
  - name: inst
    source: demo_dnb_catalog.ml_lend_gold.dim_institution
    on: source.institution_id = inst.institution_id
  - name: prod
    source: demo_dnb_catalog.ml_lend_gold.dim_product
    on: source.product_code = prod.product_code
dimensions:
  - name: credit_union
    expr: inst.institution_name
    display_name: Credit Union
    synonyms: [CU, institution, lender, client]
  - name: cohort
    expr: source.cohort
    display_name: Cohort
    comment: PILOT = live on Lending Intelligence from 2025-11-01; CONTROL = legacy process
  - name: period
    expr: source.period
    display_name: Period
    comment: BEFORE or AFTER the 2025-11-01 go-live
  - name: submitted_month
    expr: source.submitted_month
    display_name: Application Month
  - name: product
    expr: prod.product_name
    display_name: Product
    synonyms: [loan type]
  - name: channel
    expr: source.channel
    display_name: Channel
    comment: DEALER (indirect auto), ONLINE, MOBILE, BRANCH
  - name: credit_band
    expr: source.credit_band
    display_name: Credit Band
  - name: decision_source
    expr: source.decision_source
    display_name: Decision Source
    comment: AUTO or MANUAL
  - name: is_reapplication
    expr: source.is_reapplication
    display_name: Is Re-application
measures:
  - name: applications
    expr: COUNT(1)
    display_name: Applications
  - name: approved_applications
    expr: SUM(CASE WHEN source.is_approved THEN 1 ELSE 0 END)
    display_name: Approved Applications
  - name: declined_applications
    expr: SUM(CASE WHEN source.is_declined THEN 1 ELSE 0 END)
    display_name: Declined Applications
  - name: withdrawn_applications
    expr: SUM(CASE WHEN source.is_withdrawn THEN 1 ELSE 0 END)
    display_name: Withdrawn Applications
    synonyms: [abandoned]
  - name: funded_loans
    expr: SUM(CASE WHEN source.is_funded THEN 1 ELSE 0 END)
    display_name: Funded Loans
  - name: approval_rate
    expr: SUM(CASE WHEN source.is_approved THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
    display_name: Approval Rate
    format: {type: percentage}
  - name: pull_through_rate
    expr: SUM(CASE WHEN source.is_funded THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN source.is_approved THEN 1 ELSE 0 END), 0)
    display_name: Pull-Through Rate
    comment: Funded loans / approved applications. The core speed-to-yes outcome metric.
    synonyms: [pull through, conversion, funding rate]
    format: {type: percentage}
  - name: withdrawal_rate
    expr: SUM(CASE WHEN source.is_withdrawn THEN 1 ELSE 0 END) / NULLIF(COUNT(1), 0)
    display_name: Withdrawal Rate
    format: {type: percentage}
  - name: funded_amount
    expr: SUM(source.funded_amount)
    display_name: Funded Amount
    synonyms: [originations, funded volume]
    format: {type: currency, currency_code: USD}
  - name: avg_funded_amount
    expr: AVG(source.funded_amount)
    display_name: Average Funded Amount
    format: {type: currency, currency_code: USD}
  - name: est_first_year_interest_income
    expr: SUM(source.funded_amount) * 0.035
    display_name: Est. First-Year Net Interest Income
    comment: Funded amount x 3.5% net interest margin (see ml_lend_gold.roi_assumptions)
    format: {type: currency, currency_code: USD}
  - name: reapplications_funded
    expr: SUM(CASE WHEN source.is_reapplication AND source.is_funded THEN 1 ELSE 0 END)
    display_name: Declines Turned Into Funded Loans
    comment: Re-applications from previously declined members that were funded ("path to yes")
$$;

CREATE OR REPLACE VIEW demo_dnb_catalog.ml_lend_semantic.mv_decision_speed
WITH METRICS LANGUAGE YAML
COMMENT 'Consumer Lending ontology · Decision speed & automation: time-to-decision, auto-decision rate, the 24-hour cliff, underwriter workload and AI income verification.'
AS $$
version: 1.1
source: demo_dnb_catalog.ml_lend_gold.fact_application
filter: source.decision_ts IS NOT NULL
joins:
  - name: inst
    source: demo_dnb_catalog.ml_lend_gold.dim_institution
    on: source.institution_id = inst.institution_id
dimensions:
  - name: credit_union
    expr: inst.institution_name
    display_name: Credit Union
    synonyms: [CU, institution]
  - name: cohort
    expr: source.cohort
    display_name: Cohort
  - name: period
    expr: source.period
    display_name: Period
  - name: submitted_month
    expr: source.submitted_month
    display_name: Application Month
  - name: product_code
    expr: source.product_code
    display_name: Product Code
  - name: channel
    expr: source.channel
    display_name: Channel
  - name: decision_source
    expr: source.decision_source
    display_name: Decision Source
  - name: decision_engine
    expr: source.decision_engine
    display_name: Decision Engine
    comment: LEGACY_RULES, LENDING_INTELLIGENCE (model + AI document verification) or UNDERWRITER
  - name: decision_time_bucket
    expr: "CASE WHEN source.decision_minutes <= 60 THEN '1 · under 1 hour' WHEN source.decision_minutes <= 240 THEN '2 · 1-4 hours' WHEN source.decision_minutes <= 1440 THEN '3 · 4-24 hours' ELSE '4 · over 24 hours' END"
    display_name: Decision Time Bucket
measures:
  - name: decided_applications
    expr: COUNT(1)
    display_name: Decided Applications
  - name: auto_decision_rate
    expr: AVG(CASE WHEN source.is_auto_decision THEN 1.0 ELSE 0 END)
    display_name: Auto-Decision Rate
    synonyms: [automation rate, straight-through rate, instant decision rate]
    format: {type: percentage}
  - name: median_decision_minutes
    expr: PERCENTILE_APPROX(source.decision_minutes, 0.5)
    display_name: Median Time to Decision (min)
    synonyms: [time to decision, TTD, decision time]
  - name: p90_decision_hours
    expr: PERCENTILE_APPROX(source.decision_minutes, 0.9) / 60
    display_name: P90 Time to Decision (hours)
  - name: decided_within_1h_rate
    expr: AVG(CASE WHEN source.decided_within_1h THEN 1.0 ELSE 0 END)
    display_name: Decided Within 1 Hour
    format: {type: percentage}
  - name: decided_within_24h_rate
    expr: AVG(CASE WHEN source.decided_within_24h THEN 1.0 ELSE 0 END)
    display_name: Decided Within 24 Hours
    format: {type: percentage}
  - name: manual_reviews
    expr: SUM(CASE WHEN source.decision_source = 'MANUAL' THEN 1 ELSE 0 END)
    display_name: Manual Reviews
  - name: underwriter_hours_legacy_equivalent
    expr: SUM(CASE WHEN source.decision_source = 'MANUAL' THEN 1 ELSE 0 END) * 45.0 / 60
    display_name: Underwriter Hours (at 45 min/file)
  - name: model_override_rate
    expr: AVG(CASE WHEN source.decision_source = 'MANUAL' THEN CASE WHEN source.model_override_flag THEN 1.0 ELSE 0 END END)
    display_name: Underwriter Override Rate
    format: {type: percentage}
  - name: documents_ai_verified
    expr: SUM(CASE WHEN source.ai_verified_monthly_income IS NOT NULL THEN 1 ELSE 0 END)
    display_name: Documents AI-Verified
  - name: ai_income_mismatches
    expr: SUM(CASE WHEN source.ai_income_mismatch_flag THEN 1 ELSE 0 END)
    display_name: AI-Detected Income Mismatches
    comment: Stated income > 120% of income verified by AI from the pay stub
$$;

CREATE OR REPLACE VIEW demo_dnb_catalog.ml_lend_semantic.mv_portfolio_risk
WITH METRICS LANGUAGE YAML
COMMENT 'Consumer Lending ontology · Credit risk & portfolio: early payment default (60+ DPD in first 6 installments) on seasoned funded loans, expected loss, delinquency and model risk bands.'
AS $$
version: 1.1
source: demo_dnb_catalog.ml_lend_gold.fact_loan_performance
joins:
  - name: inst
    source: demo_dnb_catalog.ml_lend_gold.dim_institution
    on: source.institution_id = inst.institution_id
dimensions:
  - name: credit_union
    expr: inst.institution_name
    display_name: Credit Union
    synonyms: [CU, institution]
  - name: cohort
    expr: source.cohort
    display_name: Cohort
  - name: period
    expr: source.period
    display_name: Period
  - name: funded_month
    expr: source.funded_month
    display_name: Funded Month
  - name: product_code
    expr: source.product_code
    display_name: Product Code
  - name: channel
    expr: source.channel
    display_name: Channel
  - name: credit_band
    expr: source.credit_band
    display_name: Credit Band
  - name: decision_source
    expr: source.decision_source
    display_name: Decision Source
  - name: is_seasoned
    expr: source.is_seasoned
    display_name: Is Seasoned (6+ installments due)
measures:
  - name: funded_loans
    expr: COUNT(1)
    display_name: Funded Loans
  - name: seasoned_loans
    expr: SUM(CASE WHEN source.is_seasoned THEN 1 ELSE 0 END)
    display_name: Seasoned Loans
  - name: epd_loans
    expr: SUM(CASE WHEN source.is_seasoned AND source.epd_flag THEN 1 ELSE 0 END)
    display_name: Early Payment Defaults
  - name: epd_rate
    expr: SUM(CASE WHEN source.is_seasoned AND source.epd_flag THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN source.is_seasoned THEN 1 ELSE 0 END), 0)
    display_name: Early Payment Default Rate
    comment: Share of seasoned loans that went 60+ days past due within the first 6 installments
    synonyms: [EPD, EPD rate, early default rate]
    format: {type: percentage}
  - name: funded_amount
    expr: SUM(source.funded_amount)
    display_name: Funded Amount
    format: {type: currency, currency_code: USD}
  - name: outstanding_principal
    expr: SUM(source.outstanding_principal)
    display_name: Outstanding Principal
    format: {type: currency, currency_code: USD}
  - name: est_loss_on_epd
    expr: SUM(CASE WHEN source.is_seasoned AND source.epd_flag THEN source.outstanding_principal ELSE 0 END) * 0.55
    display_name: Est. Loss on Early Defaults
    comment: Outstanding principal on EPD loans x 55% loss given default (see roi_assumptions)
    format: {type: currency, currency_code: USD}
  - name: delinquency_30plus_rate
    expr: AVG(CASE WHEN source.max_dpd_ever >= 30 THEN 1.0 ELSE 0 END)
    display_name: 30+ DPD Rate (ever)
    format: {type: percentage}
  - name: interest_collected
    expr: SUM(source.interest_paid)
    display_name: Interest Collected
    format: {type: currency, currency_code: USD}
$$
