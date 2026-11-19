CREATE OR REPLACE TABLE demo_dnb_catalog.ml_lend_ml.path_to_yes_letters
COMMENT 'AI-drafted "path to yes" adverse-action follow-up letters for recent declines at pilot credit unions (ai_query, Claude Haiku 5.5). Each letter states the principal reason, concrete next steps and an invitation to re-apply; reviewed by compliance before sending.'
AS
WITH d AS (
  SELECT f.application_id, f.institution_id, i.institution_name, f.product_code, f.requested_amount, f.credit_band,
         r.reason_code, r.reason_description, f.decision_ts
  FROM demo_dnb_catalog.ml_lend_gold.fact_application f
  JOIN demo_dnb_catalog.ml_lend_gold.dim_institution i USING (institution_id)
  JOIN demo_dnb_catalog.ml_lend_gold.dim_denial_reason r ON f.denial_reason_id = r.denial_reason_id
  WHERE f.is_declined AND f.cohort = 'PILOT' AND f.decision_ts >= '2026-11-03')
SELECT *, ai_query('databricks-claude-haiku-5-5',
  concat('You write short, warm, plain-language letters for a US credit union member whose loan application was declined. ',
         'Rules: state the principal reason exactly as given; do not mention credit score numbers, protected characteristics or AI; ',
         'give 2-3 specific, practical steps that could lead to approval; invite the member to re-apply or talk to a lending specialist; ',
         'under 140 words; sign as "Member Lending Team, ', institution_name, '". No subject line, no placeholders.\n\n',
         'Product: ', product_code, ' loan; amount requested: $', format_number(requested_amount, 0), '; principal reason: ', reason_description, '.')) AS letter_text,
  'databricks-claude-haiku-5-5' AS model, current_timestamp() AS generated_at, 'PENDING_COMPLIANCE_REVIEW' AS review_status
FROM d;
ALTER TABLE demo_dnb_catalog.ml_lend_ml.path_to_yes_letters ALTER COLUMN institution_id SET TAGS ('tenant_isolation_key' = 'true')
