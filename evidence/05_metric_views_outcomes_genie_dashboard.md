# Evidence · Metric views, outcomes (difference-in-differences), Genie, AI/BI dashboard

_Collected 2026-11-19 06:33 UTC from workspace `fevm-demo-dnb` (catalog `demo_dnb_catalog`) by `scripts/collect_evidence.py`. Live results, not screenshots._



## mv_loan_funnel: pilot vs control, before vs after


```sql
SELECT cohort, period, MEASURE(applications) applications, round(MEASURE(approval_rate),4) approval_rate,
 round(MEASURE(pull_through_rate),4) pull_through, round(MEASURE(funded_amount)/1e6,1) funded_mm FROM demo_dnb_catalog.ml_lend_semantic.mv_loan_funnel GROUP BY ALL ORDER BY 1 DESC,2 DESC
```

**Result:**

| cohort | period | applications | approval_rate | pull_through | funded_mm |
|---|---|---|---|---|---|
| PILOT | BEFORE | 65070 | 0.5396 | 0.6714 | 486.1 |
| PILOT | AFTER | 68665 | 0.5269 | 0.7152 | 543.7 |
| CONTROL | BEFORE | 36590 | 0.5423 | 0.6794 | 281.6 |
| CONTROL | AFTER | 37892 | 0.5381 | 0.6683 | 281.6 |



## mv_decision_speed


```sql
SELECT cohort, period, round(MEASURE(auto_decision_rate),4) auto_rate, MEASURE(median_decision_minutes) median_min,
 round(MEASURE(decided_within_24h_rate),4) within_24h FROM demo_dnb_catalog.ml_lend_semantic.mv_decision_speed GROUP BY ALL ORDER BY 1 DESC,2 DESC
```

**Result:**

| cohort | period | auto_rate | median_min | within_24h |
|---|---|---|---|---|
| PILOT | BEFORE | 0.3131 | 1028.6 | 0.6121 |
| PILOT | AFTER | 0.5765 | 8.2 | 0.9637 |
| CONTROL | BEFORE | 0.3117 | 1026.0 | 0.6123 |
| CONTROL | AFTER | 0.3155 | 1017.3 | 0.6157 |



## mv_portfolio_risk


```sql
SELECT cohort, period, MEASURE(seasoned_loans) seasoned, round(MEASURE(epd_rate),4) epd_rate,
 round(MEASURE(est_loss_on_epd),0) est_loss FROM demo_dnb_catalog.ml_lend_semantic.mv_portfolio_risk GROUP BY ALL ORDER BY 1 DESC,2 DESC
```

**Result:**

| cohort | period | seasoned | epd_rate | est_loss |
|---|---|---|---|---|
| PILOT | BEFORE | 23574 | 0.0274 | 5596495.0 |
| PILOT | AFTER | 12604 | 0.0189 | 2670734.0 |
| CONTROL | BEFORE | 13480 | 0.0289 | 3400114.0 |
| CONTROL | AFTER | 6691 | 0.032 | 2305262.0 |



## Value bridge (every $ in the deck)


```sql
SELECT to_json(struct(*)) value_bridge FROM demo_dnb_catalog.ml_lend_semantic.v_value_bridge
```

**Result:**

| value_bridge |
|---|
| {"auto_decision_rate_before":0.3131,"auto_decision_rate_after":0.5762,"median_decision_minutes_before":1028.6,"median_decision_minutes_after":8.2,"pull_through_ |



## ROI assumptions


```sql
SELECT * FROM demo_dnb_catalog.ml_lend_gold.roi_assumptions
```

**Result:**

| assumption_key | assumption_value | assumption_note |
|---|---|---|
| net_interest_margin | 0.035 | Annual net interest margin on funded consumer loans (NCUA peer average ~3.0-3.5%) |
| avg_loan_life_years | 1.000 | Value counted for first year of interest only (conservative) |
| loss_given_default | 0.550 | Share of outstanding balance lost on an early-payment default (consumer unsecured/auto blend) |
| underwriter_loaded_cost_per_hour | 48.000 | Fully loaded underwriter cost per hour (USD) |
| manual_review_minutes_legacy | 45.000 | Manual file review incl. income verification, legacy process |
| manual_review_minutes_ai_assisted | 20.000 | Manual file review when AI has pre-extracted and reconciled income |
| reference_cu_annual_apps | 40000.000 | Annual applications for the reference mid-size credit union used in the deck |



## Genie space `01f1e3d666d91574bd4ffb20588c2ed6`: live transcripts


---
**Q:** Did Lending Intelligence improve pull-through? Compare pilot vs control before and after go-live  
**Status:** COMPLETED

**Generated SQL:**
```sql
SELECT
  `cohort`,
  `period`,
  MEASURE(`applications`) AS `applications`,
  MEASURE(`approved_applications`) AS `approved_applications`,
  MEASURE(`funded_loans`) AS `funded_loans`,
  MEASURE(`pull_through_rate`) AS `pull_through_rate`
FROM `demo_dnb_catalog`.`ml_lend_semantic`.`mv_loan_funnel`
WHERE `cohort` IS NOT NULL
  AND `period` IS NOT NULL
GROUP BY ALL
ORDER BY `cohort` DESC, `period` DESC
```

**Result:**

| cohort | period | applications | approved_applications | funded_loans | pull_through_rate |
|---|---|---|---|---|---|
| PILOT | BEFORE | 65070 | 35111 | 23574 | 0.6714135171313833 |
| PILOT | AFTER | 68665 | 36177 | 25875 | 0.7152334356082594 |
| CONTROL | BEFORE | 36590 | 19841 | 13480 | 0.6794012398568621 |
| CONTROL | AFTER | 37892 | 20388 | 13625 | 0.6682852658426526 |

**Answer:** **Yes.** Pull-through in the **pilot** rose from **67.1%** before go-live to **71.5%** after go-live, while the **control** fell from **67.9%** to **66.8%**.

This means the pilot improved by **4.4 percentage points** versus a **1.1-point decline** in control, for a net difference-in-differences lift of **5.5 percentage points**; funded loans also increased in the pilot from **23,574** to **25,875**, compared with a smaller rise in control from **13,480** to **13,625**.


---
**Q:** Show the 24-hour cliff: pull-through by time to decision  
**Status:** COMPLETED

**Generated SQL:**
```sql
SELECT CASE WHEN `decision_minutes` IS NOT NULL AND `decision_minutes` <= 60 THEN '1 · under 1 hour' WHEN `decision_minutes` IS NOT NULL AND `decision_minutes` <= 240 THEN '2 · 1-4 hours' WHEN `decision_minutes` IS NOT NULL AND `decision_minutes` <= 1440 THEN '3 · 4-24 hours' ELSE '4 · over 24 hours' END AS `decision_time_bucket`, COUNT(*) AS `approved`, AVG(CASE WHEN `is_funded` THEN 1.0 ELSE 0.0 END) AS `pull_through_rate` FROM `demo_dnb_catalog`.`ml_lend_gold`.`fact_application` WHERE `is_approved` = TRUE AND `decision_minutes` IS NOT NULL GROUP BY `decision_time_bucket` ORDER BY `decision_time_bucket`
```

**Result:**

| decision_time_bucket | approved | pull_through_rate |
|---|---|---|
| 1 · under 1 hour | 66092 | 0.73160 |
| 2 · 1-4 hours | 2236 | 0.70930 |
| 3 · 4-24 hours | 22386 | 0.66166 |
| 4 · over 24 hours | 20803 | 0.56737 |

**Answer:** There is a clear **24-hour cliff** in pull-through: approved applications decided in **under 24 hours** convert at **73.2%** (under 1 hour), **70.9%** (1–4 hours), and **66.2%** (4–24 hours), versus **56.7%** when the decision takes **over 24 hours**. Across all **4** time bands, pull-through consistently declines as decision time increases, with the sharpest drop occurring once decisions move past the 24-hour mark.


---
**Q:** What happened to early payment defaults after go-live?  
**Status:** COMPLETED

**Generated SQL:**
```sql
SELECT
  `cohort`,
  `period`,
  MEASURE(`seasoned_loans`) AS `seasoned_loans`,
  MEASURE(`epd_loans`) AS `epd_loans`,
  MEASURE(`epd_rate`) AS `epd_rate`,
  MEASURE(`est_loss_on_epd`) AS `est_loss_on_epd`
FROM `demo_dnb_catalog`.`ml_lend_semantic`.`mv_portfolio_risk`
WHERE `cohort` IS NOT NULL
  AND `period` IS NOT NULL
  AND `is_seasoned` = TRUE
GROUP BY ALL
ORDER BY `cohort` DESC, `period` DESC
```

**Result:**

| cohort | period | seasoned_loans | epd_loans | epd_rate | est_loss_on_epd |
|---|---|---|---|---|---|
| PILOT | BEFORE | 23574 | 645 | 0.027360651565283788 | 5596495.255999997 |
| PILOT | AFTER | 12604 | 238 | 0.018882894319263727 | 2670734.1924999994 |
| CONTROL | BEFORE | 13480 | 390 | 0.028931750741839762 | 3400113.903999997 |
| CONTROL | AFTER | 6691 | 214 | 0.031983261096995966 | 2305262.025 |

**Answer:** After go-live, **early payment defaults improved in the PILOT cohort but worsened in CONTROL**: PILOT fell from **2.7%** before go-live to **1.9%** after, while CONTROL rose from **2.9%** to **3.2%**. That means the post–go-live change favored PILOT by about **1.2 percentage points** versus CONTROL, with estimated loss on early defaults also dropping from **$5,596,495** to **$2,670,734** in PILOT.


---
**Q:** Why did auto loans through dealers fund more after go-live?  
**Status:** COMPLETED

**Generated SQL:**
```sql
WITH `funnel` AS (
  SELECT
    `cohort`,
    `period`,
    MEASURE(`applications`) AS `applications`,
    MEASURE(`approved_applications`) AS `approved_applications`,
    MEASURE(`funded_loans`) AS `funded_loans`,
    MEASURE(`approval_rate`) AS `approval_rate`,
    MEASURE(`pull_through_rate`) AS `pull_through_rate`,
    MEASURE(`funded_amount`) AS `funded_amount`
  FROM `demo_dnb_catalog`.`ml_lend_semantic`.`mv_loan_funnel`
  WHERE `channel` IS NOT NULL
    AND `product` IS NOT NULL
    AND `channel` ILIKE '%dealer%'
    AND `product` ILIKE '%auto%'
    AND `cohort` IS NOT NULL
    AND `period` IS NOT NULL
  GROUP BY ALL
),
`speed` AS (
  SELECT
    `cohort`,
    `period`,
    MEASURE(`decided_applications`) AS `decided_applications`,
    MEASURE(`auto_decision_rate`) AS `auto_decision_rate`,
    MEASURE(`median_decision_minutes`) AS `median_decision_minutes`,
    MEASURE(`decided_within_24h_rate`) AS `decided_within_24h_rate`,
    MEASURE(`manual_reviews`) AS `manual_reviews`
  FROM `demo_dnb_catalog`.`ml_lend_semantic`.`mv_decision_speed`
  WHERE `channel` IS NOT NULL
    AND `product_code` IS NOT NULL
    AND `channel` ILIKE '%dealer%'
    AND `product_code` ILIKE '%auto%'
    AND `cohort` IS NOT NULL
    AND `period` IS NOT NULL
  GROUP BY ALL
)
SELECT
  `funnel`.`cohort`,
  `funnel`.`period`,
  `funnel`.`applications`,
  `funnel`.`approved_applications`,
  `funnel`.`funded_loans`,
  `funnel`.`approval_rate`,
  `funnel`.`pull_through_rate`,
  `funnel`.`funded_amount`,
  `speed`.`decided_applications`,
  `speed`.`auto_decision_rate`,
  `speed`.`median_decision_minutes`,
  `speed`.`decided_within_24h_rate`,
  `speed`.`manual_reviews`
FROM `funnel`
LEFT JOIN `speed`
  ON `funnel`.`cohort` = `speed`.`cohort`
 AND `funnel`.`period` = `speed`.`period`
ORDER BY `funnel`.`cohort` DESC, `funnel`.`period` DESC
```

**Result:**

| cohort | period | applications | approved_applications | funded_loans | approval_rate | pull_through_rate | funded_amount | decided_applications | auto_decision_rate | median_decision_minutes | decided_within_24h_rate | manual_reviews |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PILOT | BEFORE | 16408 | 8550 | 5718 | 0.5210872745002438 | 0.6687719298245614 | 1.5529355E8 | 16408 | 0.29845 | 1075.2 | 0.60184 | 11511 |
| PILOT | AFTER | 17358 | 8797 | 6457 | 0.5067980182048624 | 0.7340002273502331 | 1.7752585E8 | 17351 | 0.61702 | 7.1 | 0.96761 | 6645 |
| CONTROL | BEFORE | 9410 | 4924 | 3352 | 0.5232731137088205 | 0.6807473598700243 | 9.134555E7 | 9410 | 0.29702 | 1061.3 | 0.60659 | 6615 |
| CONTROL | AFTER | 9686 | 5051 | 3339 | 0.5214742927937229 | 0.6610572163927935 | 9.046285E7 | 9664 | 0.30163 | 1040.1 | 0.60575 | 6749 |

**Answer:** Dealer auto loans funded more after go-live in the **PILOT** cohort mainly because approvals converted to funded loans more often and decisions became much faster, while the **CONTROL** cohort did not show the same pattern. In PILOT, funded loans rose from **5,718** to **6,457** and funded amount increased from **$155,293,550** to **$177,525,850**, while pull-through improved from **66.9%** to **73.4%**, auto-decision rate increased from **29.8%** to **61.7%**, and median decision time dropped from **1,075.2 minutes** to **7.1 minutes**; approval rate was slightly lower after go-live (**52.1%** to **50.7%**), so the visible lift appears tied more to faster, more automated conversion after approval than to higher approval rates.


## AI/BI dashboard `01f1e3d70b0c18ed82e52bd9e2d637b6`
Pages: Executive Outcome, Funnel & Speed, Risk & Trust · datasets: 16 · widgets: 25. Definition committed at `dashboards/lending_intelligence_outcomes.lvdash.json`. Each dataset's live result:


### Dataset: Value bridge
| auto_before | auto_after | median_hours_before | median_minutes_after | pull_through_lift_pts | epd_change_pts | value_ref_cu_mm | value_pilot_mm | extra_funded_loans_yr | underwriter_hours_saved_yr | declines_recovered_yr |
|---|---|---|---|---|---|---|---|---|---|---|
| 31.3 | 57.6 | 17.1 | 8.2 | 5.5 | -1.15 | 3.63 | 5.96 | 1900.0 | 24562 | 782.0 |


### Dataset: Value components (reference CU)
| value_lever | annual_value_usd |
|---|---|
| 1 · Faster decisions → more funded loans | 851417.0 |
| 2 · Underwriter capacity released | 718283.0 |
| 3 · Early-default losses avoided (AI income check) | 1711274.0 |
| 4 · Declines turned into funded loans | 350244.0 |


### Dataset: Pilot vs control
| cohort | period | applications | approval_rate_pct | pull_through_pct | funded_mm |
|---|---|---|---|---|---|
| PILOT | BEFORE | 65070 | 54.0 | 67.1 | 486.1 |
| PILOT | AFTER | 68665 | 52.7 | 71.5 | 543.7 |
| CONTROL | BEFORE | 36590 | 54.2 | 67.9 | 281.6 |
| CONTROL | AFTER | 37892 | 53.8 | 66.8 | 281.6 |


### Dataset: Pilot vs control speed
| cohort | period | auto_decision_pct | median_minutes | within_24h_pct |
|---|---|---|---|---|
| PILOT | BEFORE | 31.3 | 1028.6 | 61.2 |
| PILOT | AFTER | 57.6 | 8.2 | 96.4 |
| CONTROL | BEFORE | 31.2 | 1026.0 | 61.2 |
| CONTROL | AFTER | 31.5 | 1017.3 | 61.6 |


### Dataset: Monthly pull-through
| submitted_month | cohort | pull_through_pct |
|---|---|---|
| 2026-10-01T00:00:00.000Z | PILOT | 74.2 |
| 2025-06-01T00:00:00.000Z | PILOT | 66.9 |
| 2025-05-01T00:00:00.000Z | PILOT | 67.7 |
| 2026-03-01T00:00:00.000Z | CONTROL | 68.2 |
| 2026-07-01T00:00:00.000Z | PILOT | 73.6 |
| 2025-04-01T00:00:00.000Z | CONTROL | 65.8 |
| 2025-11-01T00:00:00.000Z | CONTROL | 66.4 |
| 2026-02-01T00:00:00.000Z | PILOT | 71.8 |
| 2024-11-01T00:00:00.000Z | CONTROL | 68.2 |
| 2026-03-01T00:00:00.000Z | PILOT | 72.2 |
| 2025-09-01T00:00:00.000Z | PILOT | 67.4 |
| 2026-06-01T00:00:00.000Z | PILOT | 72.3 |

_48 rows, first 12 shown_


### Dataset: Monthly median decision time
| submitted_month | cohort | median_hours | auto_decision_pct |
|---|---|---|---|
| 2026-10-01T00:00:00.000Z | PILOT | 0.13 | 58.8 |
| 2025-06-01T00:00:00.000Z | PILOT | 17.46 | 30.9 |
| 2025-05-01T00:00:00.000Z | PILOT | 17.56 | 30.9 |
| 2026-03-01T00:00:00.000Z | CONTROL | 15.95 | 32.1 |
| 2026-07-01T00:00:00.000Z | PILOT | 0.15 | 56.0 |
| 2025-04-01T00:00:00.000Z | CONTROL | 17.40 | 31.9 |
| 2025-11-01T00:00:00.000Z | CONTROL | 16.95 | 32.1 |
| 2026-02-01T00:00:00.000Z | PILOT | 0.14 | 57.7 |
| 2024-11-01T00:00:00.000Z | CONTROL | 17.39 | 31.3 |
| 2026-03-01T00:00:00.000Z | PILOT | 0.14 | 56.5 |
| 2025-09-01T00:00:00.000Z | PILOT | 16.69 | 31.6 |
| 2026-06-01T00:00:00.000Z | PILOT | 0.14 | 57.6 |

_50 rows, first 12 shown_


### Dataset: 24-hour cliff
| decision_time | pull_through_pct | approved |
|---|---|---|
| 4 · over 24 hours | 56.7 | 20803 |
| 3 · 4-24 hours | 66.2 | 22386 |
| 2 · 1-4 hours | 70.9 | 2236 |
| 1 · under 1 hour | 73.2 | 66092 |


### Dataset: Decision engine mix (pilot)
| submitted_month | decision_engine | decisions |
|---|---|---|
| 2025-08-01T00:00:00.000Z | LEGACY_RULES | 1874 |
| 2024-12-01T00:00:00.000Z | LEGACY_RULES | 1382 |
| 2026-11-01T00:00:00.000Z | LENDING_INTELLIGENCE | 759 |
| 2024-11-01T00:00:00.000Z | LEGACY_RULES | 1452 |
| 2026-06-01T00:00:00.000Z | UNDERWRITER | 2779 |
| 2026-08-01T00:00:00.000Z | LENDING_INTELLIGENCE | 1733 |
| 2025-11-01T00:00:00.000Z | UNDERWRITER | 1833 |
| 2025-12-01T00:00:00.000Z | LENDING_INTELLIGENCE | 1368 |
| 2025-07-01T00:00:00.000Z | LEGACY_RULES | 2029 |
| 2026-05-01T00:00:00.000Z | UNDERWRITER | 2632 |
| 2026-03-01T00:00:00.000Z | LEGACY_RULES | 1517 |
| 2026-03-01T00:00:00.000Z | UNDERWRITER | 2400 |

_63 rows, first 12 shown_


### Dataset: Channel lift (pilot)
| channel | period | pull_through_pct |
|---|---|---|
| MOBILE | BEFORE | 64.9 |
| BRANCH | BEFORE | 74.8 |
| BRANCH | AFTER | 78.3 |
| ONLINE | AFTER | 67.4 |
| ONLINE | BEFORE | 64.4 |
| DEALER | BEFORE | 66.9 |
| MOBILE | AFTER | 69.6 |
| DEALER | AFTER | 73.4 |


### Dataset: EPD by cohort
| cohort_period | cohort | period | epd_pct | seasoned |
|---|---|---|---|---|
| PILOT · BEFORE | PILOT | BEFORE | 2.74 | 23574 |
| PILOT · AFTER | PILOT | AFTER | 1.89 | 12604 |
| CONTROL · BEFORE | CONTROL | BEFORE | 2.89 | 13480 |
| CONTROL · AFTER | CONTROL | AFTER | 3.2 | 6691 |


### Dataset: AI income verification
| week | documents_verified | mismatches |
|---|---|---|
| 2026-11-02T00:00:00.000Z | 348 | 70 |
| 2026-09-28T00:00:00.000Z | 67 | 20 |
| 2026-11-09T00:00:00.000Z | 341 | 66 |
| 2026-10-19T00:00:00.000Z | 366 | 81 |
| 2026-10-26T00:00:00.000Z | 334 | 69 |
| 2026-10-12T00:00:00.000Z | 386 | 79 |
| 2026-10-05T00:00:00.000Z | 412 | 85 |
| 2026-11-16T00:00:00.000Z | 120 | 12 |


### Dataset: Model risk bands
| risk_band | applications | avg_epd_pct |
|---|---|---|
| LOW | 6356 | 1.48 |
| HIGH | 5006 | 6.57 |
| MEDIUM | 9088 | 3.45 |


### Dataset: AI note categories
| note_category | notes |
|---|---|
| COMPLAINT | 414 |
| HARDSHIP | 493 |
| STATUS_INQUIRY | 1037 |
| DOCUMENT_ISSUE | 1025 |
| RATE_SHOPPING | 557 |
| FRAUD_CONCERN | 214 |


### Dataset: Expectations
| expectation | passed_records | failed_records | pass_rate_pct |
|---|---|---|---|
| valid_ssn_format | 132540 | 180 | 99.864 |
| credit_score_range | 132720 | 0 | 100.0 |
| application_id_present | 208697 | 0 | 100.0 |
| positive_requested_amt | 208577 | 120 | 99.943 |
| decision_after_submit | 208697 | 0 | 100.0 |
| valid_dpd | 1762780 | 0 | 100.0 |
| member_present | 208697 | 0 | 100.0 |
| valid_status | 1762780 | 0 | 100.0 |
| member_id_present | 132680 | 40 | 99.97 |
| known_product | 208637 | 60 | 99.971 |
| amounts_balance | 1762780 | 0 | 100.0 |


### Dataset: Quarantine
| entity | failed_rule | records |
|---|---|---|
| applications | positive_requested_amt | 120 |
| applications | known_product | 60 |
| members | valid_ssn_format | 180 |
| members | member_id_present | 40 |


### Dataset: Governed columns
| tbl | column_name | tag_name | tag_value |
|---|---|---|---|
| ml_lend_gold.dim_member | first_name | class.name |  |
| ml_lend_silver.members_quarantine | zip | class.location |  |
| ml_lend_gold.outcome_monthly | institution_id | tenant_isolation_key | true |
| ml_lend_gold.dim_member | phone | class.phone_number |  |
| ml_lend_silver.members | last_name | class.name |  |
| ml_lend_silver.members_quarantine | street_address | class.street_address |  |
| ml_lend_silver.members_quarantine | street_address | class.location |  |
| ml_lend_silver.members | street_address | class.location |  |
| ml_lend_silver.members | street_address | class.street_address |  |
| ml_lend_bronze.members_cdc_raw | first_name | class.name |  |
| ml_lend_bronze.members_cdc_raw | phone | class.phone_number |  |
| ml_lend_silver.members | phone | class.phone_number |  |

_48 rows, first 12 shown_
