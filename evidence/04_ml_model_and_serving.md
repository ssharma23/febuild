# Evidence · EPD model (MLflow / UC) + Model Serving

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## UC registered model versions

```text
v4: AUC 0.691, avg precision 0.053, top-20% EPD capture 39.1%. Run 7e65e106d62846648f8a7f6b6b79527f.
v3: AUC 0.691, avg precision 0.053, top-20% EPD capture 39.1%. Run 15bf30219a704c1ab421cacd44b21717.
v2: AUC 0.691, avg precision 0.053, top-20% EPD capture 39.1%. Run 75ac7e971b1f4f98b16d2958aaf5eeb4.
v1: AUC 0.612, avg precision 0.026, top-20% EPD capture 44.6%. Run f7d096b69c0c460181de8b3463ee6647.
```


## Aliases

```json
null
```


## Batch scores: risk band distribution vs realized EPD (seasoned loans)


```sql
SELECT s.risk_band, count(*) applications, round(avg(s.epd_probability),4) avg_predicted
FROM demo_dnb_catalog.ml_lend_ml.application_risk_scores s GROUP BY 1 ORDER BY 3
```

**Result:**

| risk_band | applications | avg_predicted |
|---|---|---|
| LOW | 6356 | 0.0148 |
| MEDIUM | 9088 | 0.0345 |
| HIGH | 5006 | 0.0657 |



## Sample scored applications with SHAP reason codes


```sql
SELECT application_id, round(epd_probability,4) p, risk_band, reason_1, reason_2, reason_3, model_version FROM demo_dnb_catalog.ml_lend_ml.application_risk_scores ORDER BY epd_probability DESC LIMIT 5
```

**Result:**

| application_id | p | risk_band | reason_1 | reason_2 | reason_3 | model_version |
|---|---|---|---|---|---|---|
| APP-10194011 | 0.1574 | HIGH | Credit score below the level for best pricing | Income level relative to obligations | Debt-to-income ratio is high | 4 |
| APP-10197766 | 0.1389 | HIGH | Credit score below the level for best pricing | Income level relative to obligations | Debt-to-income ratio is high | 4 |
| APP-10202828 | 0.1388 | HIGH | Credit score below the level for best pricing | Income level relative to obligations | Debt-to-income ratio is high | 4 |
| APP-10206358 | 0.1319 | HIGH | Credit score below the level for best pricing | Income level relative to obligations | Debt-to-income ratio is high | 4 |
| APP-10187963 | 0.131 | HIGH | Credit score below the level for best pricing | Pricing tier associated with risk | Debt-to-income ratio is high | 4 |



## Serving endpoint state

```json
{
 "name": "ml-lend-epd-risk",
 "state": {
  "config_update": "NOT_UPDATING",
  "ready": "READY"
 },
 "served_entities": [
  {
   "entity_name": "demo_dnb_catalog.ml_lend_ml.epd_risk_model",
   "entity_version": "4",
   "workload_size": "Small",
   "scale_to_zero_enabled": true
  }
 ]
}
```


## Live endpoint request (Jordan Whitaker, live-demo applicant)

```json
{
 "dataframe_records": [
  {
   "credit_score": 702.0,
   "stated_monthly_income": 7500.0,
   "monthly_debt_payments": 900.0,
   "dti_stated": 0.2027,
   "loan_to_income": 0.3556,
   "requested_amount": 32000.0,
   "term_months": 60.0,
   "apr": 0.0599,
   "product_AUTO": 1.0,
   "product_PERSONAL": 0.0,
   "product_CARD": 0.0,
   "product_HELOC": 0.0,
   "channel_DEALER": 1.0,
   "channel_ONLINE": 0.0,
   "channel_MOBILE": 0.0,
   "channel_BRANCH": 0.0,
   "member_tenure_years": 6.0
  }
 ]
}
```


## Live endpoint response

```json
{
 "predictions": [
  {
   "epd_probability": 0.029802793956876003,
   "reason_1": "Debt-to-income ratio is high",
   "reason_2": "Credit score below the level for best pricing",
   "reason_3": "Requested loan amount",
   "risk_band": "MEDIUM"
  }
 ]
}
```
