-- =====================================================================================
-- GOLD · Consumer-lending star schema + outcome KPIs (materialized views, incrementally refreshed)
-- =====================================================================================

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_institution
COMMENT 'Credit unions served by MeridianLink. cohort = PILOT (live on Lending Intelligence from go_live_date) or CONTROL (legacy rules + manual underwriting); the control group isolates the effect of the program from seasonality and market rates.'
AS SELECT institution_id, institution_name, institution_short, hq_state, cohort,
          CAST(annual_app_target AS INT) AS annual_app_target, CAST(total_assets_bn AS DOUBLE) AS total_assets_bn,
          CAST(go_live_date AS DATE) AS go_live_date
FROM demo_dnb_catalog.ml_lend_bronze.ref_institutions;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_branch COMMENT 'Credit-union branches.'
AS SELECT branch_id, institution_id, branch_name, city, state FROM demo_dnb_catalog.ml_lend_bronze.ref_branches;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_product COMMENT 'Consumer lending products (AUTO, PERSONAL, CARD, HELOC).'
AS SELECT product_code, product_name, collateral_type, product_family, CAST(base_apr AS DOUBLE) AS base_apr, CAST(default_term_months AS INT) AS default_term_months
FROM demo_dnb_catalog.ml_lend_bronze.ref_products;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_denial_reason COMMENT 'Adverse-action reasons used on declined applications (supports ECOA/Reg B adverse-action notices).'
AS SELECT CAST(denial_reason_id AS INT) AS denial_reason_id, reason_code, reason_category, reason_description, severity FROM demo_dnb_catalog.ml_lend_bronze.ref_denial_reasons;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_dealer COMMENT 'Indirect-lending auto dealers that submit applications on behalf of members.'
AS SELECT dealer_id, dealer_name, institution_id FROM demo_dnb_catalog.ml_lend_bronze.ref_dealers;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member
COMMENT 'Current profile of each member/applicant (latest SCD2 version). PII columns (ssn, date_of_birth, email, phone, street_address, names) are masked by ABAC for users outside the PII-reader group.'
AS SELECT member_id, institution_id, first_name, last_name, ssn, CAST(date_of_birth AS DATE) AS date_of_birth, email, phone, street_address, city, state, zip,
          CAST(member_since AS DATE) AS member_since, employer_name, employment_status, credit_score,
          CASE WHEN credit_score >= 760 THEN '760+' WHEN credit_score >= 700 THEN '700-759' WHEN credit_score >= 640 THEN '640-699' WHEN credit_score >= 580 THEN '580-639' ELSE '<580' END AS credit_band,
          stated_monthly_income, monthly_debt_payments
FROM demo_dnb_catalog.ml_lend_silver.members WHERE __END_AT IS NULL;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.fact_application
COMMENT 'One row per loan application with decision speed, outcome, funding and AI income-verification results. period = BEFORE/AFTER the 2025-11-01 Lending Intelligence go-live; combine with dim_institution.cohort (PILOT vs CONTROL) for difference-in-differences.'
AS
SELECT a.application_id, a.institution_id, i.cohort, a.branch_id, a.member_id, a.channel, a.dealer_id, a.product_code,
       a.submitted_ts, CAST(a.submitted_ts AS DATE) AS submitted_date, date_trunc('MONTH', a.submitted_ts) AS submitted_month,
       CASE WHEN a.submitted_ts >= TIMESTAMP'2025-11-01' THEN 'AFTER' ELSE 'BEFORE' END AS period,
       (i.cohort = 'PILOT' AND a.submitted_ts >= TIMESTAMP'2025-11-01') AS lending_intelligence_live,
       a.decision_ts, a.decision_source, a.decision_engine, a.application_status,
       round((unix_timestamp(a.decision_ts) - unix_timestamp(a.submitted_ts))/60.0, 1) AS decision_minutes,
       a.decision_ts IS NOT NULL AND (unix_timestamp(a.decision_ts) - unix_timestamp(a.submitted_ts)) <= 3600  AS decided_within_1h,
       a.decision_ts IS NOT NULL AND (unix_timestamp(a.decision_ts) - unix_timestamp(a.submitted_ts)) <= 86400 AS decided_within_24h,
       a.decision_source = 'AUTO' AS is_auto_decision,
       a.application_status = 'APPROVED' AS is_approved, a.application_status = 'DECLINED' AS is_declined,
       a.application_status = 'WITHDRAWN' AS is_withdrawn, coalesce(a.funded_flag, false) AS is_funded,
       a.requested_amount, a.approved_amount, a.funded_amount, a.apr, a.term_months,
       a.denial_reason_id, r.reason_code AS denial_reason_code, r.reason_category AS denial_reason_category,
       a.stated_monthly_income, m.credit_score, m.credit_band,
       a.underwriter_id, coalesce(a.model_override_flag,false) AS model_override_flag,
       coalesce(a.is_reapplication,false) AS is_reapplication, a.prior_application_id, a.loan_account_id,
       d.verified_monthly_income AS ai_verified_monthly_income, d.employer_name AS ai_employer_name,
       round((a.stated_monthly_income - d.verified_monthly_income) / nullif(d.verified_monthly_income,0), 3) AS ai_income_variance_pct,
       d.verified_monthly_income IS NOT NULL AND a.stated_monthly_income > d.verified_monthly_income * 1.20 AS ai_income_mismatch_flag
FROM demo_dnb_catalog.ml_lend_silver.applications a
JOIN demo_dnb_catalog.ml_lend_gold.dim_institution i USING (institution_id)
LEFT JOIN demo_dnb_catalog.ml_lend_gold.dim_member m USING (member_id)
LEFT JOIN demo_dnb_catalog.ml_lend_gold.dim_denial_reason r ON a.denial_reason_id = r.denial_reason_id
LEFT JOIN demo_dnb_catalog.ml_lend_silver.document_income_extraction d ON a.application_id = d.application_id;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.fact_loan_performance
COMMENT 'One row per funded loan with repayment performance. epd_flag = early payment default: 60+ days past due within the first 6 installments; only meaningful when is_seasoned (>= 6 installments due).'
AS
WITH p AS (
  SELECT loan_account_id,
         count(*) AS installments_due,
         sum(CASE WHEN installment_number <= 6 THEN 1 ELSE 0 END) AS first6_due,
         max(CASE WHEN installment_number <= 6 THEN days_past_due ELSE 0 END) AS max_dpd_first6,
         max(days_past_due) AS max_dpd_ever,
         sum(payment_amount) AS total_paid, sum(interest_amount) AS interest_paid, sum(principal_amount) AS principal_paid,
         sum(CASE WHEN payment_status = 'MISSED' THEN 1 ELSE 0 END) AS missed_payments
  FROM demo_dnb_catalog.ml_lend_silver.loan_payments GROUP BY loan_account_id)
SELECT f.loan_account_id, f.application_id, f.institution_id, f.cohort, f.period, f.lending_intelligence_live, f.product_code, f.channel,
       f.member_id, f.credit_band, f.funded_amount, f.apr, f.term_months, f.decision_source,
       date_trunc('MONTH', f.decision_ts) AS funded_month,
       coalesce(p.installments_due,0) AS installments_due, coalesce(p.first6_due,0) >= 6 AS is_seasoned,
       coalesce(p.max_dpd_first6,0) AS max_dpd_first6, coalesce(p.max_dpd_ever,0) AS max_dpd_ever,
       coalesce(p.max_dpd_first6,0) >= 60 AS epd_flag,
       p.total_paid, p.interest_paid, p.principal_paid, p.missed_payments,
       greatest(f.funded_amount - coalesce(p.principal_paid,0), 0) AS outstanding_principal
FROM demo_dnb_catalog.ml_lend_gold.fact_application f
LEFT JOIN p ON f.loan_account_id = p.loan_account_id
WHERE f.is_funded;

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.member_notes_enriched
COMMENT 'Notes with AI category joined to application context (product, channel, status, cohort).'
AS SELECT n.*, f.product_code, f.channel, f.application_status, f.cohort, f.period
FROM demo_dnb_catalog.ml_lend_silver.member_notes n LEFT JOIN demo_dnb_catalog.ml_lend_gold.fact_application f USING (application_id);

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.roi_assumptions
COMMENT 'Documented business assumptions used to translate measured operational lifts into dollars. Every dollar figure in the deck = measured metric x one of these assumptions.'
AS SELECT * FROM VALUES
  ('net_interest_margin', 0.035, 'Annual net interest margin on funded consumer loans (NCUA peer average ~3.0-3.5%)'),
  ('avg_loan_life_years', 1.0, 'Value counted for first year of interest only (conservative)'),
  ('loss_given_default', 0.55, 'Share of outstanding balance lost on an early-payment default (consumer unsecured/auto blend)'),
  ('underwriter_loaded_cost_per_hour', 48.0, 'Fully loaded underwriter cost per hour (USD)'),
  ('manual_review_minutes_legacy', 45.0, 'Manual file review incl. income verification, legacy process'),
  ('manual_review_minutes_ai_assisted', 20.0, 'Manual file review when AI has pre-extracted and reconciled income'),
  ('reference_cu_annual_apps', 40000.0, 'Annual applications for the reference mid-size credit union used in the deck')
AS t(assumption_key, assumption_value, assumption_note);

CREATE OR REFRESH MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.outcome_monthly
COMMENT 'Monthly outcome KPIs per credit union: volume, automation, speed, approvals, pull-through, funded dollars, early payment default.'
AS
SELECT f.institution_id, f.cohort, f.submitted_month, f.period,
       count(*) AS applications,
       avg(CASE WHEN f.is_auto_decision THEN 1.0 ELSE 0 END) AS auto_decision_rate,
       percentile_approx(f.decision_minutes, 0.5) AS median_decision_minutes,
       avg(CASE WHEN f.decided_within_24h THEN 1.0 ELSE 0 END) AS decided_within_24h_rate,
       sum(CASE WHEN f.is_approved THEN 1 ELSE 0 END) AS approved,
       sum(CASE WHEN f.is_funded THEN 1 ELSE 0 END) AS funded,
       sum(CASE WHEN f.is_funded THEN 1 ELSE 0 END) / nullif(sum(CASE WHEN f.is_approved THEN 1 ELSE 0 END),0) AS pull_through_rate,
       sum(f.funded_amount) AS funded_amount,
       sum(CASE WHEN f.is_withdrawn THEN 1 ELSE 0 END) AS withdrawn
FROM demo_dnb_catalog.ml_lend_gold.fact_application f
GROUP BY ALL;
