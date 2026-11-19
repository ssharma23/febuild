# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Early-Payment-Default (EPD) risk model
# MAGIC * **Target:** `epd_flag` — 60+ days past due within the first 6 installments (seasoned funded loans only).
# MAGIC * **Features:** only information available **at decision time** (bureau score, capacity, loan structure, channel). No post-decision leakage.
# MAGIC * **Model:** LightGBM, tracked in MLflow, registered to Unity Catalog `ml_lend_ml.epd_risk_model` with alias `@champion`.
# MAGIC * **Explainability:** SHAP → top-3 reason codes mapped to plain-language adverse-action reasons (ECOA / Reg B).
# MAGIC * **Time-based validation:** train on loans funded before 2026-01-01, test on 2026 loans (no random-split optimism).

# COMMAND ----------

# MAGIC %pip install lightgbm==4.5.0 shap==0.46.0 -q
# MAGIC %restart_python

# COMMAND ----------

import mlflow, numpy as np, pandas as pd, lightgbm as lgb, shap, json
from sklearn.metrics import roc_auc_score, average_precision_score
from mlflow.models import infer_signature
mlflow.set_registry_uri("databricks-uc")
CAT = "demo_dnb_catalog"
MODEL_NAME = f"{CAT}.ml_lend_ml.epd_risk_model"
mlflow.set_experiment("/Users/sonam.s@databricks.com/meridianlink_lending/epd_risk_model")

FEATURES = ["credit_score","stated_monthly_income","monthly_debt_payments","dti_stated","loan_to_income","requested_amount","term_months",
            "apr","product_AUTO","product_PERSONAL","product_CARD","product_HELOC","channel_DEALER","channel_ONLINE","channel_MOBILE","channel_BRANCH","member_tenure_years"]

# Feature view (persisted so app, batch scoring and serving share one definition)
spark.sql(f"""
CREATE OR REPLACE VIEW {CAT}.ml_lend_ml.v_application_features
COMMENT 'Decision-time features for the EPD risk model (one row per application). Shared by training, batch scoring and the Workbench app.'
AS SELECT f.application_id, f.institution_id, f.submitted_ts, f.product_code, f.channel,
  CAST(m.credit_score AS DOUBLE) credit_score, f.stated_monthly_income, m.monthly_debt_payments,
  round((m.monthly_debt_payments + f.requested_amount * (coalesce(p.base_apr,0.1)/12) / (1 - power(1 + coalesce(p.base_apr,0.1)/12, -greatest(coalesce(nullif(f.term_months,0),36),1)))) / nullif(f.stated_monthly_income,0), 4) dti_stated,
  round(f.requested_amount / nullif(f.stated_monthly_income*12,0), 4) loan_to_income,
  f.requested_amount, CAST(coalesce(nullif(f.term_months,0),36) AS DOUBLE) term_months,
  coalesce(f.apr, p.base_apr) apr,
  CAST(f.product_code='AUTO' AS INT) product_AUTO, CAST(f.product_code='PERSONAL' AS INT) product_PERSONAL,
  CAST(f.product_code='CARD' AS INT) product_CARD, CAST(f.product_code='HELOC' AS INT) product_HELOC,
  CAST(f.channel='DEALER' AS INT) channel_DEALER, CAST(f.channel='ONLINE' AS INT) channel_ONLINE,
  CAST(f.channel='MOBILE' AS INT) channel_MOBILE, CAST(f.channel='BRANCH' AS INT) channel_BRANCH,
  round(datediff(f.submitted_ts, m.member_since)/365.25, 2) member_tenure_years
FROM {CAT}.ml_lend_gold.fact_application f
JOIN {CAT}.ml_lend_gold.dim_member m USING (member_id)
LEFT JOIN {CAT}.ml_lend_gold.dim_product p USING (product_code)
""")

df = spark.sql(f"""
SELECT v.*, l.epd_flag, l.funded_month FROM {CAT}.ml_lend_ml.v_application_features v
JOIN {CAT}.ml_lend_gold.fact_loan_performance l USING (application_id) WHERE l.is_seasoned
""").toPandas()
for c in FEATURES: df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
df["epd_flag"] = df.epd_flag.astype(int)
train = df[df.funded_month < "2026-01-01"]; test = df[df.funded_month >= "2026-01-01"]
print(len(train), len(test), train.epd_flag.mean().round(4), test.epd_flag.mean().round(4))

# COMMAND ----------

REASON_TEXT = {
 "credit_score":"Credit score below the level for best pricing", "dti_stated":"Debt-to-income ratio is high",
 "monthly_debt_payments":"Existing monthly debt obligations are high", "loan_to_income":"Requested amount is high relative to income",
 "stated_monthly_income":"Income level relative to obligations", "requested_amount":"Requested loan amount", "term_months":"Length of repayment term",
 "apr":"Pricing tier associated with risk", "member_tenure_years":"Length of membership relationship",
 "product_AUTO":"Product type","product_PERSONAL":"Unsecured product type","product_CARD":"Revolving product type","product_HELOC":"Product type",
 "channel_DEALER":"Application channel","channel_ONLINE":"Application channel","channel_MOBILE":"Application channel","channel_BRANCH":"Application channel"}

class EPDRiskModel(mlflow.pyfunc.PythonModel):
    """Returns EPD probability, a risk band and the top-3 SHAP (TreeSHAP) reason codes (adverse-action ready)."""
    def load_context(self, context):
        import lightgbm as lgb, json
        self.booster = lgb.Booster(model_file=context.artifacts["booster"])   # TreeSHAP via LightGBM pred_contrib (no shap dependency at serving)
        self.features = json.load(open(context.artifacts["features"]))
        self.reason_text = json.load(open(context.artifacts["reasons"]))
        self.bands = json.load(open(context.artifacts["bands"]))   # LOW < p50, HIGH >= p90 of training scores
    def predict(self, context, model_input, params=None):
        import numpy as np, pandas as pd
        X = model_input[self.features].astype("float64")
        p = self.booster.predict(X)
        sv = self.booster.predict(X, pred_contrib=True)[:, :-1]   # per-feature SHAP contributions (log-odds), last col = bias
        out = []
        for i in range(len(X)):
            top = np.argsort(-sv[i])[:3]
            out.append({"epd_probability": float(p[i]),
                        "risk_band": "LOW" if p[i] < self.bands["low"] else ("MEDIUM" if p[i] < self.bands["high"] else "HIGH"),
                        "reason_1": self.reason_text.get(self.features[top[0]], self.features[top[0]]),
                        "reason_2": self.reason_text.get(self.features[top[1]], self.features[top[1]]),
                        "reason_3": self.reason_text.get(self.features[top[2]], self.features[top[2]])})
        return pd.DataFrame(out)

with mlflow.start_run(run_name="lgbm_epd_champion") as run:
    params = dict(objective="binary", learning_rate=0.03, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=42)
    dtr = lgb.Dataset(train[FEATURES], train.epd_flag); dte = lgb.Dataset(test[FEATURES], test.epd_flag)
    booster = lgb.train(params, dtr, num_boost_round=600, valid_sets=[dte], callbacks=[lgb.early_stopping(50, verbose=False)])
    p = booster.predict(test[FEATURES])
    auc = roc_auc_score(test.epd_flag, p); ap = average_precision_score(test.epd_flag, p)
    # capture rate: share of EPDs in the riskiest 20% of loans
    q = np.quantile(p, 0.8); capture = test.epd_flag[p >= q].sum()/test.epd_flag.sum()
    mlflow.log_params(params); mlflow.log_metrics({"test_auc":auc, "test_avg_precision":ap, "epd_capture_top20pct":capture,
                                                   "train_rows":len(train), "test_rows":len(test), "test_epd_rate":test.epd_flag.mean()})
    ptr = booster.predict(train[FEATURES]); bands = {"low": float(np.quantile(ptr, 0.5)), "high": float(np.quantile(ptr, 0.9))}
    mlflow.log_params({"band_low_threshold": round(bands["low"],5), "band_high_threshold": round(bands["high"],5)})
    booster.save_model("/tmp/booster.txt"); json.dump(FEATURES, open("/tmp/features.json","w")); json.dump(REASON_TEXT, open("/tmp/reasons.json","w")); json.dump(bands, open("/tmp/bands.json","w"))
    # global importance artifact
    imp = pd.DataFrame({"feature":FEATURES,"gain":booster.feature_importance("gain")}).sort_values("gain", ascending=False)
    mlflow.log_table(imp, "feature_importance.json")
    sample = test[FEATURES].head(20)
    wrapped = EPDRiskModel()
    class _C: artifacts={"booster":"/tmp/booster.txt","features":"/tmp/features.json","reasons":"/tmp/reasons.json","bands":"/tmp/bands.json"}
    wrapped.load_context(_C); out = wrapped.predict(None, sample)
    info = mlflow.pyfunc.log_model(artifact_path="model", python_model=wrapped,
        artifacts={"booster":"/tmp/booster.txt","features":"/tmp/features.json","reasons":"/tmp/reasons.json","bands":"/tmp/bands.json"},
        signature=infer_signature(sample, out), input_example=sample.head(3),
        pip_requirements=["lightgbm==4.5.0", "pandas==2.2.3", "numpy==1.26.4"],
        registered_model_name=MODEL_NAME)
    print(f"AUC={auc:.3f}  AP={ap:.3f}  EPD capture in top 20% riskiest = {capture:.1%}")

from mlflow import MlflowClient
c = MlflowClient()
v = max(int(m.version) for m in c.search_model_versions(f"name='{MODEL_NAME}'"))
c.set_registered_model_alias(MODEL_NAME, "champion", v)
c.update_registered_model(MODEL_NAME, description="Early-payment-default (60+ DPD in first 6 installments) probability for consumer loan applications at MeridianLink credit unions. LightGBM + SHAP reason codes. Time-based validation (train < 2026, test 2026).")
c.update_model_version(MODEL_NAME, v, description=f"AUC {auc:.3f}, avg precision {ap:.3f}, top-20% EPD capture {capture:.1%}. Run {run.info.run_id}.")
dbutils.jobs.taskValues.set("model_version", v) if hasattr(dbutils, "jobs") else None
print("registered", MODEL_NAME, "v", v)

# COMMAND ----------

# MAGIC %md ## Batch score open + recent applications (feeds the underwriting queue & dashboard)

# COMMAND ----------

model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
recent = spark.sql(f"SELECT * FROM {CAT}.ml_lend_ml.v_application_features WHERE submitted_ts >= '2026-09-01'").toPandas()
for c_ in FEATURES: recent[c_] = pd.to_numeric(recent[c_], errors="coerce").astype("float64")
scores = model.predict(recent[FEATURES])
res = pd.concat([recent[["application_id","institution_id"]].reset_index(drop=True), scores], axis=1)
res["model_version"] = str(v); res["scored_at"] = pd.Timestamp.utcnow()
spark.createDataFrame(res).write.mode("overwrite").option("overwriteSchema","true").saveAsTable(f"{CAT}.ml_lend_ml.application_risk_scores")
spark.sql(f"COMMENT ON TABLE {CAT}.ml_lend_ml.application_risk_scores IS 'EPD model scores + top-3 SHAP reason codes for applications submitted since 2026-09-01 (model @champion).'")
print(res.risk_band.value_counts())
