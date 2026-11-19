# Q&A Bank — likely assessor questions (business + technical)

## Business / framing
1. **Is the $3.6M real?** Synthetic data, but every number is reproducible: `ml_lend_semantic.v_value_bridge` = measured difference-in-differences × documented assumptions (`ml_lend_gold.roi_assumptions`: 3.5% NIM, 55% LGD, $48/h, 45→20 min). First-year NII only (conservative). Sensitivity: halve the EPD effect → still ~$2.8M.
2. **Why a control group?** Seasonality and rate cycles move pull-through. DiD isolates the program effect: pilot +4.4 pts, control −1.1 pts → +5.5 pts.
3. **Biggest lever?** Trust, not speed: avoided early-default losses from AI income verification (~$1.7M of $3.6M per reference CU). Speed drives volume (~$0.85M NII).
4. **Underwriter savings = layoffs?** Capacity released (~15K hours per reference CU) → redeploy to complex files, member outreach, collections. We present it as capacity, not cash.
5. **What's in it for MeridianLink?** Productize "Lending Intelligence" for every credit union on one multi-tenant platform (policy-based isolation, no per-tenant stack) → new revenue line, stickier DecisionLender/Consumer, faster time-to-value.
6. **What's in it for Databricks?** Pipelines + serverless SQL + AI Functions + Model Serving + Lakebase + Apps per tenant — consumption scales with credit unions onboarded.
7. **Next 90 days?** 30: real Data Connect feed for 1 design-partner CU, shadow-mode scoring; 60: compliance review of model + letters, Workbench pilot; 90: go-live + DiD readout, then tenant #2.

## Data engineering
8. **Why files + Auto Loader instead of a connector?** Data Connect *is* file delivery; Auto Loader = Lakeflow Connect's file ingestion — exactly-once, schema evolution, no infra. A SQL Server CDC managed connector is the swap-in if they want direct LOS replication.
9. **How do you handle re-sent / changed records?** AUTO CDC SCD1 on `application_id` sequenced by `record_updated_ts` (300 duplicate rows collapsed); SCD2 for members.
10. **DQ?** Expectations with drop/warn/fail-update + quarantine tables with the failed rule (400 records); metrics in the pipeline event log → dashboard. Anomaly detection/data profiling can be enabled on gold.
11. **Cost of AI in the pipeline?** Streaming table → each document parsed once; notes classified only for a recent window. ~2,300 docs in a few minutes on serverless.

## Governance
12. **How does tenant isolation work?** ABAC row-filter policy on schema `ml_lend_gold`, matches any column tagged `tenant_isolation_key=true`, function checks `tenant_entitlements` for `current_user()`. Flows through metric views, Genie, dashboards (viewer credentials).
13. **Why an entitlement table, not groups?** FEVM account groups weren't available; production would use account groups (`is_account_group_member`) synced from IdP — same policies, swap the function body.
14. **Who classified the PII?** UC Data Classification (auto-tagging enabled for SSN, DOB, email, phone, name, address, location) — it tagged bronze/silver member tables automatically; gold dim tagged with the same system tags.
15. **Lakebase bypasses UC?** The synced queue is a per-tenant slice (Summit Valley only) with SSN reduced to last-4 at source; Postgres roles per app SP. Hardening: Postgres RLS per tenant.

## AI / ML
16. **Model quality?** LightGBM, time-based split (train < 2026, test 2026); see UC model version description for AUC / top-20% capture. EPD is a rare event (~2-3%) — we judge it by capture in the riskiest decile/quintile, not accuracy.
17. **Explainability / fair lending (ECOA, Reg B)?** SHAP top-3 reasons per decision → adverse-action reasons; protected attributes not used as features; letters state principal reason; human review for all mismatches/high risk.
18. **Hallucination risk in letters?** Constrained prompt (exact reason, no numbers, no protected traits), stored with `review_status = PENDING_COMPLIANCE_REVIEW`; batch letters reviewed before sending.
19. **How accurate is ai_classify?** 89% vs human labels (92-note overlap); misses are COMPLAINT↔DOCUMENT_ISSUE — inherently ambiguous; could fine-tune labels/description or use ai_query with few-shot.
20. **Why not just a rules engine?** Legacy rules auto-decided 31%; model + verified income safely auto-decides 58% *and* lowers defaults — rules can't read a pay stub.

## Platform / competitive
21. **Why Databricks vs Snowflake/others?** One governed platform for files → pipelines → AI Functions on documents → ML training/serving → OLTP (Lakebase) → apps → Genie, all under one UC policy model. Fewer copies, one lineage graph.
22. **Latency of the live path?** Parse + extract via serverless SQL (~seconds), model serving (~100 ms warm), Lakebase write (ms).
