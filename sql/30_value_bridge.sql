CREATE OR REPLACE VIEW demo_dnb_catalog.ml_lend_semantic.v_value_bridge
COMMENT 'Outcome value bridge for the deck. Lifts are difference-in-differences (PILOT after-before minus CONTROL after-before), applied to the PILOT after-period volume, annualized, then scaled to a reference 40K-applications/yr credit union. Assumptions from ml_lend_gold.roi_assumptions.'
AS
WITH a AS (SELECT assumption_key k, assumption_value v FROM demo_dnb_catalog.ml_lend_gold.roi_assumptions),
nim AS (SELECT v FROM a WHERE k='net_interest_margin'), lgd AS (SELECT v FROM a WHERE k='loss_given_default'),
uwc AS (SELECT v FROM a WHERE k='underwriter_loaded_cost_per_hour'), m_leg AS (SELECT v FROM a WHERE k='manual_review_minutes_legacy'),
m_ai AS (SELECT v FROM a WHERE k='manual_review_minutes_ai_assisted'), ref AS (SELECT v FROM a WHERE k='reference_cu_annual_apps'),
f AS (
  SELECT cohort, period,
         count(*) apps,
         sum(CASE WHEN is_approved THEN 1 ELSE 0 END) approved,
         sum(CASE WHEN is_funded THEN 1 ELSE 0 END) / sum(CASE WHEN is_approved THEN 1 ELSE 0 END) pull_through,
         avg(funded_amount) avg_funded,
         avg(CASE WHEN decision_source='MANUAL' THEN 1.0 ELSE 0 END) manual_share,
         avg(CASE WHEN is_auto_decision THEN 1.0 ELSE 0 END) auto_rate,
         percentile_approx(decision_minutes, 0.5) median_minutes,
         sum(CASE WHEN is_reapplication AND is_funded THEN 1 ELSE 0 END) / count(*) reapp_funded_per_app,
         CASE WHEN period='AFTER' THEN 12.0/12.55 ELSE 1.0 END annualize
  FROM demo_dnb_catalog.ml_lend_gold.fact_application GROUP BY cohort, period),
r AS (
  SELECT cohort, period, sum(CASE WHEN is_seasoned AND epd_flag THEN 1 ELSE 0 END)/sum(CASE WHEN is_seasoned THEN 1 ELSE 0 END) epd_rate,
         avg(CASE WHEN is_seasoned AND epd_flag THEN outstanding_principal END) avg_epd_balance
  FROM demo_dnb_catalog.ml_lend_gold.fact_loan_performance GROUP BY cohort, period),
p AS (SELECT
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.apps*f.annualize END) pilot_apps_yr,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.approved*f.annualize END) pilot_approved_yr,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.avg_funded END) pilot_avg_funded,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.approved*f.pull_through*f.annualize END) pilot_funded_yr,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.pull_through END) - max(CASE WHEN f.cohort='PILOT' AND f.period='BEFORE' THEN f.pull_through END)
   - (max(CASE WHEN f.cohort='CONTROL' AND f.period='AFTER' THEN f.pull_through END) - max(CASE WHEN f.cohort='CONTROL' AND f.period='BEFORE' THEN f.pull_through END)) did_pull_through,
  max(CASE WHEN f.cohort='PILOT' AND f.period='BEFORE' THEN f.manual_share END) manual_before,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.manual_share END) manual_after,
  max(CASE WHEN f.cohort='PILOT' AND f.period='BEFORE' THEN f.auto_rate END) auto_before,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.auto_rate END) auto_after,
  max(CASE WHEN f.cohort='PILOT' AND f.period='BEFORE' THEN f.median_minutes END) median_min_before,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.median_minutes END) median_min_after,
  max(CASE WHEN f.cohort='PILOT' AND f.period='AFTER' THEN f.reapp_funded_per_app END) - max(CASE WHEN f.cohort='PILOT' AND f.period='BEFORE' THEN f.reapp_funded_per_app END)
   - (max(CASE WHEN f.cohort='CONTROL' AND f.period='AFTER' THEN f.reapp_funded_per_app END) - max(CASE WHEN f.cohort='CONTROL' AND f.period='BEFORE' THEN f.reapp_funded_per_app END)) did_reapp_funded_per_app
  FROM f),
e AS (SELECT
  max(CASE WHEN cohort='PILOT' AND period='BEFORE' THEN epd_rate END) epd_before, max(CASE WHEN cohort='PILOT' AND period='AFTER' THEN epd_rate END) epd_after,
  max(CASE WHEN cohort='PILOT' AND period='AFTER' THEN epd_rate END) - max(CASE WHEN cohort='PILOT' AND period='BEFORE' THEN epd_rate END)
   - (max(CASE WHEN cohort='CONTROL' AND period='AFTER' THEN epd_rate END) - max(CASE WHEN cohort='CONTROL' AND period='BEFORE' THEN epd_rate END)) did_epd,
  avg(avg_epd_balance) avg_epd_balance FROM r)
SELECT
  round(p.auto_before,4) auto_decision_rate_before, round(p.auto_after,4) auto_decision_rate_after,
  p.median_min_before median_decision_minutes_before, p.median_min_after median_decision_minutes_after,
  round(p.did_pull_through,4) pull_through_lift_did, round(e.epd_before,4) epd_rate_before, round(e.epd_after,4) epd_rate_after, round(e.did_epd,4) epd_change_did,
  round(p.pilot_apps_yr) pilot_apps_per_year,
  -- 1. extra funded loans from faster decisions
  round(p.did_pull_through * p.pilot_approved_yr) extra_funded_loans_yr,
  round(p.did_pull_through * p.pilot_approved_yr * p.pilot_avg_funded * (SELECT v FROM nim)) value_pull_through_nii,
  -- 2. underwriter capacity
  round((p.pilot_apps_yr*p.manual_before*(SELECT v FROM m_leg) - p.pilot_apps_yr*p.manual_after*(SELECT v FROM m_ai))/60) underwriter_hours_saved_yr,
  round((p.pilot_apps_yr*p.manual_before*(SELECT v FROM m_leg) - p.pilot_apps_yr*p.manual_after*(SELECT v FROM m_ai))/60 * (SELECT v FROM uwc)) value_underwriter_capacity,
  -- 3. avoided early-payment-default losses
  round(-e.did_epd * p.pilot_funded_yr * e.avg_epd_balance * (SELECT v FROM lgd)) value_epd_losses_avoided,
  -- 4. declines turned into funded loans
  round(p.did_reapp_funded_per_app * p.pilot_apps_yr) declines_recovered_yr,
  round(p.did_reapp_funded_per_app * p.pilot_apps_yr * p.pilot_avg_funded * (SELECT v FROM nim)) value_declines_recovered_nii,
  (SELECT v FROM ref) / p.pilot_apps_yr AS scale_to_reference_cu
FROM p, e
