# Evidence · AI Functions (ai_parse_document, ai_extract, ai_classify, ai_query)

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## ai_parse_document + ai_extract: sample extracted pay-stub facts


```sql
SELECT application_id, employer_name, pay_frequency_raw, gross_pay_period, verified_monthly_income, left(doc_text, 90) doc_text_start
FROM demo_dnb_catalog.ml_lend_silver.document_income_extraction ORDER BY application_id LIMIT 8
```

**Result:**

| application_id | employer_name | pay_frequency_raw | gross_pay_period | verified_monthly_income | doc_text_start |
|---|---|---|---|---|---|
| APP-10197056 | Ironwood Hospitality | SEMI-MONTHLY | 2605.0 | 5210.0 | Ironwood Hospitality -- PAY ADVICE EMPLOYEE: Noah Dunmore ID E22059 FREQUENCY: SEMI-MONTHL |
| APP-10197065 | Prairie Wind Farms | Semi-Monthly | 2575.5 | 5151.0 | Prairie Wind Farms Earnings Statement · processed by PayGrid Payroll Services Employee Luc |
| APP-10197070 | Evergreen County | Bi-Weekly | 1719.69 | 3726.0 | Evergreen County Earnings Statement · processed by PayGrid Payroll Services Employee Omar  |
| APP-10197073 | Evergreen County | WEEKLY | 1188.0 | 5148.0 | Evergreen County -- PAY ADVICE EMPLOYEE: Nina Lindqvist ID E60588 FREQUENCY: WEEKLY PERIOD |
| APP-10197084 | Summit Timber Co | Bi-Weekly | 5075.08 | 10996.0 | NORTHSTAR PAYROLL CO. Statement of Earnings for Elena Jansen <table><tr><th>Company</th><t |
| APP-10197099 | Granite Peak Construction | BI-WEEKLY | 2014.62 | 4365.0 | Granite Peak Construction -- PAY ADVICE EMPLOYEE: Omar Davenport ID E81445 FREQUENCY: BI-W |
| APP-10197103 | Cedar Ridge Health | Semi-Monthly | 2656.0 | 5312.0 | NORTHSTAR PAYROLL CO. Statement of Earnings for Hana Corrigan <table><tr><th>Company</th>< |
| APP-10197105 | Granite Peak Construction | Monthly | 3496.0 | 3496.0 | NORTHSTAR PAYROLL CO. Statement of Earnings for Diego Whitaker <table><tr><th>Company</th> |



## Extraction accuracy vs hidden ground truth

Ground truth (`eval_income_truth`) is produced by the synthetic generator and never shown to the pipeline.

```sql
SELECT count(*) documents, round(avg(CASE WHEN abs(d.verified_monthly_income - t.true_monthly_income)/t.true_monthly_income < 0.02 THEN 1.0 ELSE 0 END),4) within_2pct,
 sum(CASE WHEN d.verified_monthly_income IS NULL THEN 1 ELSE 0 END) failed_extractions
FROM demo_dnb_catalog.ml_lend_silver.document_income_extraction d JOIN demo_dnb_catalog.ml_lend_ml.eval_income_truth t USING (application_id)
```

**Result:**

| documents | within_2pct | failed_extractions |
|---|---|---|
| 2374 | 1.0000 | 0 |



## Income-misstatement detection: confusion matrix


```sql
SELECT t.income_misstated, f.ai_income_mismatch_flag, count(*) n
FROM demo_dnb_catalog.ml_lend_silver.document_income_extraction d JOIN demo_dnb_catalog.ml_lend_ml.eval_income_truth t USING (application_id)
JOIN demo_dnb_catalog.ml_lend_gold.fact_application f USING (application_id) GROUP BY ALL ORDER BY 1,2
```

**Result:**

| income_misstated | ai_income_mismatch_flag | n |
|---|---|---|
| false | false | 1892 |
| false | true | 2 |
| true | true | 480 |



## ai_classify accuracy vs human-labelled notes


```sql
SELECT count(*) labelled, round(avg(CASE WHEN n.note_category = l.human_label THEN 1.0 ELSE 0 END),3) accuracy
FROM demo_dnb_catalog.ml_lend_ml.eval_note_labels l JOIN demo_dnb_catalog.ml_lend_silver.member_notes n USING (note_id) WHERE n.note_category IS NOT NULL
```

**Result:**

| labelled | accuracy |
|---|---|
| 92 | 0.891 |



## ai_classify output distribution


```sql
SELECT note_category, count(*) n FROM demo_dnb_catalog.ml_lend_silver.member_notes WHERE note_category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC
```

**Result:**

| note_category | n |
|---|---|
| STATUS_INQUIRY | 1037 |
| DOCUMENT_ISSUE | 1025 |
| RATE_SHOPPING | 557 |
| HARDSHIP | 493 |
| COMPLAINT | 414 |
| FRAUD_CONCERN | 214 |



## ai_query: generated 'path to yes' letters


```sql
SELECT reason_code, count(*) letters FROM demo_dnb_catalog.ml_lend_ml.path_to_yes_letters GROUP BY 1 ORDER BY 2 DESC
```

**Result:**

| reason_code | letters |
|---|---|
| CR-LOW | 267 |
| INC-UNVER | 122 |
| AMT-HIGH | 104 |
| OTHER | 97 |
| INC-INSUF | 87 |
| DELINQ | 86 |
| DTI-HIGH | 84 |
| THIN-FILE | 69 |
| EMP-UNVER | 53 |
| COLL-LTV | 37 |
| BK-RECENT | 21 |
| FRAUD-SUS | 15 |



## Sample letter (INC-UNVER)

```text
Dear Member,

Thank you for applying for a personal loan of $3,500 with Summit Valley Credit Union. We're sorry to let you know we can't approve it at this time. The principal reason is: Stated income could not be verified against documents.

This can often be resolved. These steps may help:

1. Send your most recent pay stubs, covering the last 30 days.
2. Provide your latest W-2 or tax return, if you have one.
3. Share recent bank statements showing your income deposits.

Once these are on file, you're welcome to re-apply. If you have questions or would like help choosing the right documents, please talk with one of our lending specialists. We're glad to help.

Warm regards,

Member Lending Team
Summit Valley Credit Union
```


## Sample letter (INC-UNVER)

```text
Dear Member,

Thank you for applying for your $4,500 CARD loan with Summit Valley Credit Union. We're sorry we couldn't approve it. The principal reason: Stated income could not be verified against documents.

To improve your chances next time, consider these steps:

1. Gather your last 30 days of pay stubs and your most recent W-2 or tax return.
2. Provide bank statements from the last two months showing your income deposits.
3. If you're self-employed, include 1099s or a profit-and-loss statement.

You're welcome to re-apply once these are ready. Or call us to speak with a lending specialist. We're happy to help.

Warm regards,

Member Lending Team, Summit Valley Credit Union
```
