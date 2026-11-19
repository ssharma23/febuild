# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Generate MeridianLink Data Connect extracts (100% synthetic)
# MAGIC
# MAGIC Simulates the daily **MeridianLink Data Connect** export that credit unions receive from the LOS.
# MAGIC Files land in the UC Volume `ml_lend_landing.dataconnect`, where the **Lakeflow** pipeline (Auto Loader) picks them up.
# MAGIC
# MAGIC **Design for a measurable outcome (difference-in-differences):**
# MAGIC * 4 fictional credit unions. **Pilot** (Summit Valley CU, Harbor Point CU) go live on *Lending Intelligence* on **2025-11-01**.
# MAGIC   **Control** (Riverside Community CU, Prairie Federal CU) stay on legacy rules + manual underwriting.
# MAGIC * Before = Nov-2024 → Oct-2025, After = Nov-2025 → Nov-2026.
# MAGIC * Behavioural mechanics: time-to-decision drives abandonment (the "24-hour cliff"); stated-income misstatement drives early-payment default;
# MAGIC   AI document verification catches misstatement; "path to yes" letters drive re-applications.
# MAGIC
# MAGIC Deterministic (seeded). No real people, employers, or accounts. SSNs/emails/phones are fabricated.

# COMMAND ----------

import numpy as np, pandas as pd, os, json, shutil
from datetime import datetime, timedelta

CATALOG = "demo_dnb_catalog"
VOL = f"/Volumes/{CATALOG}/ml_lend_landing/dataconnect"
SEED = 20261118
rng = np.random.default_rng(SEED)

START = pd.Timestamp("2024-11-01")
GO_LIVE = pd.Timestamp("2025-11-01")
END = pd.Timestamp("2026-11-17 23:59:59")   # last full Data Connect day

# clean landing (idempotent rebuild)
for sub in ["institutions","branches","products","denial_reasons","dealers","members","applications","loan_payments","member_notes"]:
    p = f"{VOL}/{sub}"
    if os.path.exists(p): shutil.rmtree(p)
    os.makedirs(p, exist_ok=True)

# COMMAND ----------

# MAGIC %md ## Reference data

# COMMAND ----------

institutions = pd.DataFrame([
  # id, name, short, state, cohort, annual apps target, total assets ($B)
  ("CU-SVCU","Summit Valley Credit Union","SVCU","WA","PILOT",38000,4.2),
  ("CU-HPCU","Harbor Point Credit Union","HPCU","OR","PILOT",26000,2.9),
  ("CU-RCCU","Riverside Community Credit Union","RCCU","ID","CONTROL",22000,2.4),
  ("CU-PFCU","Prairie Federal Credit Union","PFCU","MT","CONTROL",14000,1.6),
], columns=["institution_id","institution_name","institution_short","hq_state","cohort","annual_app_target","total_assets_bn"])
institutions["go_live_date"] = np.where(institutions.cohort=="PILOT", "2025-11-01", None)

cities = {
 "CU-SVCU":[("Spokane","WA"),("Tacoma","WA"),("Yakima","WA"),("Bellingham","WA"),("Olympia","WA"),("Everett","WA"),("Kennewick","WA"),("Wenatchee","WA"),("Vancouver","WA"),("Seattle","WA")],
 "CU-HPCU":[("Portland","OR"),("Eugene","OR"),("Salem","OR"),("Bend","OR"),("Medford","OR"),("Astoria","OR"),("Corvallis","OR"),("Coos Bay","OR")],
 "CU-RCCU":[("Boise","ID"),("Idaho Falls","ID"),("Nampa","ID"),("Pocatello","ID"),("Twin Falls","ID"),("Coeur d'Alene","ID"),("Riverside","ID")],
 "CU-PFCU":[("Billings","MT"),("Missoula","MT"),("Bozeman","MT"),("Great Falls","MT"),("Helena","MT")],
}
br = []
for inst, cl in cities.items():
    for i,(c,s) in enumerate(cl):
        br.append((f"{inst[3:]}-BR{i+1:02d}", inst, f"{c} Branch", c, s))
branches = pd.DataFrame(br, columns=["branch_id","institution_id","branch_name","city","state"])

products = pd.DataFrame([
  ("AUTO","Auto Loan","Secured","Consumer",28000,9000,60,0.0599),
  ("PERSONAL","Personal Loan","Unsecured","Consumer",9500,4000,36,0.1099),
  ("CARD","Credit Card","Revolving","Consumer",6000,3000,0,0.1799),
  ("HELOC","Home Equity Line","Secured","Home",62000,25000,120,0.0749),
], columns=["product_code","product_name","collateral_type","product_family","avg_amount","sd_amount","default_term_months","base_apr"])

denial_reasons = pd.DataFrame([
 (1,"CR-LOW","Credit","Credit score below program minimum","Major"),
 (2,"DTI-HIGH","Capacity","Debt-to-income ratio exceeds program maximum","Major"),
 (3,"INC-UNVER","Income","Stated income could not be verified against documents","Critical"),
 (4,"INC-INSUF","Income","Insufficient income for amount requested","Major"),
 (5,"AMT-HIGH","Capacity","Requested amount too high relative to income","Minor"),
 (6,"DELINQ","Credit","Recent delinquency on credit report","Major"),
 (7,"THIN-FILE","Credit","Insufficient credit history","Minor"),
 (8,"EMP-UNVER","Income","Employment could not be verified","Major"),
 (9,"COLL-LTV","Collateral","Loan-to-value exceeds program maximum","Major"),
 (10,"FRAUD-SUS","Fraud","Identity or document inconsistency requires review","Critical"),
 (11,"BK-RECENT","Credit","Bankruptcy within lookback window","Critical"),
 (12,"OTHER","Other","Other underwriting policy reason","Minor"),
], columns=["denial_reason_id","reason_code","reason_category","reason_description","severity"])

dealers = pd.DataFrame([(f"DLR-{i:03d}", n, inst) for i,(n,inst) in enumerate([
  ("Cascade Auto Group","CU-SVCU"),("Evergreen Motors","CU-SVCU"),("Puget Sound Toyota (fictional)","CU-SVCU"),("Inland Empire Ford (fictional)","CU-SVCU"),
  ("Willamette Honda (fictional)","CU-HPCU"),("Rose City Auto","CU-HPCU"),("High Desert Subaru (fictional)","CU-HPCU"),
  ("Snake River Chevrolet (fictional)","CU-RCCU"),("Treasure Valley Motors","CU-RCCU"),
  ("Big Sky Auto Mall","CU-PFCU"),("Yellowstone Trucks (fictional)","CU-PFCU")],start=1)],
  columns=["dealer_id","dealer_name","institution_id"])

def write_csv(df, entity, name):
    df.to_csv(f"{VOL}/{entity}/{name}.csv", index=False)

write_csv(institutions,"institutions","institutions_full")
write_csv(branches,"branches","branches_full")
write_csv(products,"products","products_full")
write_csv(denial_reasons,"denial_reasons","denial_reasons_full")
write_csv(dealers,"dealers","dealers_full")

# COMMAND ----------

# MAGIC %md ## Members (applicants) — CDC events for SCD2

# COMMAND ----------

FIRST = ["Avery","Jordan","Taylor","Morgan","Casey","Riley","Quinn","Parker","Reese","Rowan","Emerson","Hayden","Skyler","Dakota","Finley","Sawyer","Elliot","Harper","Logan","Cameron",
         "Maya","Liam","Noah","Olivia","Emma","Ava","Sofia","Mateo","Lucas","Isabella","Mia","Ethan","Amara","Kai","Zara","Nina","Omar","Priya","Diego","Leila","Hana","Tomas","Ines","Ravi","Mei","Jonah","Elena","Malik","Grace","Anika"]
LAST  = ["Whitaker","Lindqvist","Okafor","Castellano","Brennan","Nakamura","Delacroix","Halvorsen","Mbeki","Sorensen","Iverson","Kowalczyk","Abernathy","Fairbanks","Vasquez","Takahashi","Oyelaran","Pemberton",
         "Rasmussen","Goldberg","Moreau","Ashford","Calloway","Dunmore","Ellsworth","Farrow","Galloway","Hartwell","Ingram","Jansen","Kendrick","Larkspur","Merriweather","Northcott","Oakley","Prescott",
         "Quintero","Redfield","Stanhope","Thorne","Underwood","Valdez","Wexley","Yardley","Zimmer","Bramwell","Corrigan","Davenport","Easton","Fitzgerald"]
EMPLOYERS = ["Northwind Logistics","Cedar Ridge Health","Pinecrest School District","Blue Heron Manufacturing","Summit Timber Co","Harborline Shipping","Granite Peak Construction","Silverleaf Software",
             "Riverbend Foods","Columbia Gorge Energy","Evergreen County","Lakeside Medical Group","Ironwood Hospitality","Prairie Wind Farms","Copperline Telecom","Meadowbrook Retail","Self-employed"]

app_target = institutions.set_index("institution_id").annual_app_target
n_members = {k:int(v*1.25) for k,v in app_target.items()}   # members per CU
mrows=[]; mid=0
for inst,n in n_members.items():
    cl = cities[inst]
    for _ in range(n):
        mid+=1; mrows.append((inst, mid))
members = pd.DataFrame(mrows, columns=["institution_id","member_seq"])
N = len(members)
members["member_id"] = ["MBR-" + f"{i:07d}" for i in members.member_seq]
members["first_name"] = rng.choice(FIRST, N)
members["last_name"]  = rng.choice(LAST, N)
area = rng.integers(101, 665, N); grp = rng.integers(10, 99, N); ser = rng.integers(1000, 9999, N)
members["ssn"] = [f"{a:03d}-{g:02d}-{s:04d}" for a,g,s in zip(area,grp,ser)]
age = np.clip(rng.normal(41, 13, N), 19, 84)
members["date_of_birth"] = (pd.Timestamp("2026-11-01") - pd.to_timedelta((age*365.25).astype(int), unit="D")).strftime("%Y-%m-%d")
members["email"] = [f"{f.lower()}.{l.lower()}{i%997}@example.com" for f,l,i in zip(members.first_name, members.last_name, members.member_seq)]
members["phone"] = [f"(555) 01{rng.integers(0,10)}{rng.integers(0,10)}-{rng.integers(1000,9999)}" for _ in range(N)]
streets = ["Maple","Cedar","Pine","Oak","Elm","Birch","Aspen","Juniper","Willow","Spruce","Lakeview","Ridge","Hillcrest","River","Canyon"]
members["street_address"] = [f"{rng.integers(100,9999)} {rng.choice(streets)} {rng.choice(['St','Ave','Rd','Ln','Dr','Ct'])}" for _ in range(N)]
cc = [cities[i][rng.integers(0,len(cities[i]))] for i in members.institution_id]
members["city"] = [c for c,_ in cc]; members["state"] = [s for _,s in cc]
members["zip"] = [f"{rng.integers(83000,99400):05d}" for _ in range(N)]
members["member_since"] = (pd.Timestamp("2026-01-01") - pd.to_timedelta(rng.integers(30, 365*20, N), unit="D")).strftime("%Y-%m-%d")
members["employer_name"] = rng.choice(EMPLOYERS, N, p=np.r_[np.full(16, 0.88/16), 0.12])
members["employment_status"] = np.where(members.employer_name=="Self-employed","SELF_EMPLOYED", rng.choice(["FULL_TIME","PART_TIME","RETIRED"],N,p=[.86,.08,.06]))
members["credit_score"] = np.clip(rng.normal(694, 68, N), 520, 850).astype(int)
true_income = np.clip(rng.lognormal(np.log(5600), 0.45, N), 1800, 40000)          # true gross monthly income
members["_true_income"] = true_income.round(0)
misstate = rng.random(N) < 0.065                                                     # 6.5% inflate stated income
members["_misstated"] = misstate
infl = np.where(misstate, rng.uniform(1.25, 1.75, N), rng.uniform(0.97, 1.03, N))
members["stated_monthly_income"] = (true_income*infl).round(-1)
members["monthly_debt_payments"] = (true_income * np.clip(rng.normal(0.24, 0.10, N), 0.02, 0.62)).round(0)

# CDC: initial INSERT event at member_since-ish (clamped to START) + ~6% UPDATE events (address / credit refresh)
base = members.copy()
base["op"]="UPSERT"; base["event_ts"]=(START - pd.Timedelta(days=1)).strftime("%Y-%m-%dT02:00:00")
upd = members.sample(frac=0.06, random_state=1).copy()
upd["street_address"] = [f"{rng.integers(100,9999)} {rng.choice(streets)} {rng.choice(['St','Ave','Rd'])}" for _ in range(len(upd))]
upd["credit_score"] = np.clip(upd.credit_score + rng.integers(-40, 45, len(upd)), 520, 850)
upd["op"]="UPSERT"
upd["event_ts"]=[(START + pd.Timedelta(days=int(d))).strftime("%Y-%m-%dT02:00:00") for d in rng.integers(30, 730, len(upd))]
member_cols = ["member_id","institution_id","first_name","last_name","ssn","date_of_birth","email","phone","street_address","city","state","zip",
               "member_since","employer_name","employment_status","credit_score","stated_monthly_income","monthly_debt_payments","op","event_ts"]
mevents = pd.concat([base, upd])[member_cols]
# DQ defects injected (for expectations): bad SSN format + null member_id
bad = mevents.sample(n=180, random_state=7).copy(); bad["ssn"] = bad.ssn.str.replace("-","",regex=False).str[:7]
nul = mevents.sample(n=40, random_state=8).copy(); nul["member_id"] = None
mevents = pd.concat([mevents, bad, nul])
mevents["_month"] = pd.to_datetime(mevents.event_ts).dt.strftime("%Y-%m")
for m, g in mevents.groupby("_month"):
    g.drop(columns="_month").to_json(f"{VOL}/members/members_cdc_{m}.json", orient="records", lines=True)
print("members", N, "events", len(mevents))

# COMMAND ----------

# MAGIC %md ## Applications — decisioning mechanics

# COMMAND ----------

days = pd.date_range(START.normalize(), END.normalize(), freq="D")
season = 1 + 0.18*np.sin((days.dayofyear.values - 80)/365*2*np.pi)       # spring/summer auto season
weekday = np.where(days.dayofweek.values>=5, 0.55, 1.1)
w = season*weekday; w = w/w.sum()

apps=[]
for inst, target in app_target.items():
    n = int(target * len(days)/365)
    d_idx = rng.choice(len(days), n, p=w)
    mem = members[members.institution_id==inst]
    pick = rng.integers(0, len(mem), n)
    a = pd.DataFrame({"institution_id":inst, "member_id":mem.member_id.values[pick], "_mi":mem.index.values[pick],
                      "submitted_ts": days[d_idx] + pd.to_timedelta(rng.integers(6*3600, 22*3600, n), unit="s")})
    apps.append(a)
apps = pd.concat(apps, ignore_index=True).sort_values("submitted_ts").reset_index(drop=True)
A = len(apps)
mi = apps._mi.values
apps["product_code"] = rng.choice(products.product_code, A, p=[.46,.24,.20,.10])
apps["channel"] = np.where(apps.product_code=="AUTO", rng.choice(["DEALER","ONLINE","MOBILE","BRANCH"],A,p=[.55,.18,.15,.12]),
                                                     rng.choice(["ONLINE","MOBILE","BRANCH"],A,p=[.42,.33,.25]))
dl = dealers.groupby("institution_id").dealer_id.apply(list).to_dict()
apps["dealer_id"] = [rng.choice(dl[i]) if c=="DEALER" else None for i,c in zip(apps.institution_id, apps.channel)]
brs = branches.groupby("institution_id").branch_id.apply(list).to_dict()
apps["branch_id"] = [rng.choice(brs[i]) for i in apps.institution_id]
P = products.set_index("product_code")
amt = np.maximum(500, rng.normal(P.loc[apps.product_code,"avg_amount"].values, P.loc[apps.product_code,"sd_amount"].values))
apps["requested_amount"] = (amt/50).round()*50
apps["term_months"] = np.where(apps.product_code=="AUTO", rng.choice([36,48,60,72],A,p=[.12,.25,.43,.20]),
                     np.where(apps.product_code=="PERSONAL", rng.choice([24,36,48,60],A,p=[.2,.45,.25,.1]),
                     np.where(apps.product_code=="HELOC", 120, 0)))
apps["stated_monthly_income"] = members.stated_monthly_income.values[mi]
credit = members.credit_score.values[mi]
true_inc = members._true_income.values[mi]
misst = members._misstated.values[mi]
debt = members.monthly_debt_payments.values[mi]
pilot = apps.institution_id.isin(["CU-SVCU","CU-HPCU"]).values
after = (apps.submitted_ts >= GO_LIVE).values
live = pilot & after

# payment estimate for DTI
r = P.loc[apps.product_code,"base_apr"].values/12
term = np.where(apps.term_months.values==0, 36, apps.term_months.values)
pmt = apps.requested_amount.values * r/(1-(1+r)**(-term))
dti_stated = (debt + pmt)/apps.stated_monthly_income.values
dti_true   = (debt + pmt)/true_inc

# underlying risk (what a good model sees with verified income)
z = -0.022*(credit-690) + 4.0*(dti_true-0.36) + rng.normal(0, 0.55, A)
risk_true = 1/(1+np.exp(-z))
# what the decision process "sees": legacy uses stated income
z_seen = -0.022*(credit-690) + 4.0*(dti_stated-0.36) + rng.normal(0, 0.55, A)
risk_seen = 1/(1+np.exp(-z_seen))

# ---- auto-decision eligibility
legacy_auto = (credit >= 702) & (dti_stated < 0.40) & (apps.requested_amount.values < 45000)   # legacy rules engine ~1/3
li_auto = ((risk_true < 0.50) | (risk_true > 0.84)) & (apps.product_code.values != "HELOC")         # model-driven auto approve / auto decline
auto = np.where(live, li_auto | legacy_auto, legacy_auto)
# AI income verification catches misstatement in live period (doc check on every app)
ai_caught = live & misst & (rng.random(A) < 0.93)
auto = auto & ~ai_caught           # mismatches always routed to an underwriter
manual_caught = (~auto) & misst & ~live & (rng.random(A) < 0.30)   # humans catch ~30% pre-AI
caught = ai_caught | manual_caught | (live & ~auto & misst & (rng.random(A) < 0.30))

# ---- approval
risk_used = np.where(live, risk_true, risk_seen)
approve_p = np.clip(1.25 - 1.45*risk_used, 0.02, 0.97)
approved = rng.random(A) < approve_p
approved = approved & ~(caught & (rng.random(A) < 0.80))          # most caught misstatements declined
counter = caught & approved                                       # rest approved at a reduced amount
# ---- time to decision (hours)
auto_h = rng.lognormal(np.log(0.07), 0.6, A)                     # ~4 minutes
man_before_h = rng.lognormal(np.log(27.0), 0.75, A)
man_after_h  = rng.lognormal(np.log(7.5), 0.85, A)              # smaller queue → faster humans
ttd_h = np.where(auto, auto_h, np.where(live, man_after_h, man_before_h))
ttd_h = np.where(pilot & ~after, ttd_h*1.0, ttd_h)
apps["decision_ts"] = apps.submitted_ts + pd.to_timedelta((ttd_h*3600).astype(int), unit="s")
pending = apps.decision_ts.values > np.datetime64(END)
apps["decision_source"] = np.where(auto, "AUTO", "MANUAL")
apps["decision_engine"] = np.where(auto & live & ~legacy_auto, "LENDING_INTELLIGENCE", np.where(auto, "LEGACY_RULES", "UNDERWRITER"))
withdrawn = (~auto) & (ttd_h > 48) & (rng.random(A) < 0.18)       # applicant withdraws while waiting
status = np.where(approved, "APPROVED", "DECLINED")
status = np.where(withdrawn, "WITHDRAWN", status)
status = np.where(pending, "PENDING", status)
apps["application_status"] = status

# denial reasons
reason = np.where(caught & (status=="DECLINED"), 3,
          np.where(credit < 620, 1, np.where(dti_true > 0.5, 2, rng.choice([4,5,6,7,8,9,10,11,12], A, p=[.16,.18,.16,.12,.08,.07,.05,.04,.14]))))
apps["denial_reason_id"] = np.where(status=="DECLINED", reason, None)
apr = P.loc[apps.product_code,"base_apr"].values + 0.09*risk_used + rng.normal(0,0.004,A)
apps["apr"] = np.where(status=="APPROVED", np.round(apr,4), None)
appr_amt = np.where(counter, apps.requested_amount.values*rng.uniform(0.55,0.75,A), apps.requested_amount.values)
apps["approved_amount"] = np.where(status=="APPROVED", (appr_amt/50).round()*50, None)

# ---- funding: the 24-hour cliff
base_f = pd.Series(apps.channel).map({"DEALER":0.76,"ONLINE":0.70,"MOBILE":0.71,"BRANCH":0.81}).values
decay = np.where(ttd_h<1, 1.0, np.where(ttd_h<4, 0.96, np.where(ttd_h<24, 0.90, 0.78)))
decay = np.where((apps.channel.values=="DEALER") & (ttd_h>=1), decay*0.92, decay)   # dealers shop the deal to other lenders
funded = (status=="APPROVED") & (rng.random(A) < base_f*decay)
fund_lag = rng.integers(1, 10, A)
apps["funded_ts"] = np.where(funded, apps.decision_ts + pd.to_timedelta(fund_lag, unit="D"), pd.NaT)
funded = funded & (pd.to_datetime(apps.funded_ts) <= END).fillna(False).values
apps.loc[~funded, "funded_ts"] = pd.NaT
apps["funded_flag"] = funded
apps["funded_amount"] = np.where(funded, apps.approved_amount, None)
apps["income_verified_flag"] = np.where(status=="PENDING", None, (caught | live | (~auto)))
apps["underwriter_id"] = np.where(apps.decision_source=="MANUAL", [f"UW-{i[3:7]}-{rng.integers(1,9):02d}" for i in apps.institution_id], None)
apps["model_override_flag"] = np.where(live & ~auto, rng.random(A) < 0.06, False)
apps["_misstated"] = misst; apps["_caught"]=caught; apps["_risk_true"]=risk_true; apps["_live"]=live

# ---- "path to yes" re-applications (declines → future funded loans)
dec = apps[(apps.application_status=="DECLINED") & (apps.decision_ts < END - pd.Timedelta(days=150))]
reapp_p = np.where(dec._live, 0.105, 0.032)
re = dec[rng.random(len(dec)) < reapp_p].copy()
re["prior_application_id_idx"] = re.index
re["submitted_ts"] = re.decision_ts + pd.to_timedelta(rng.integers(30, 120, len(re)), unit="D")
re["decision_source"]="MANUAL"; re["decision_engine"]="UNDERWRITER"
re_ttd = np.where(re._live, rng.lognormal(np.log(6),0.8,len(re)), rng.lognormal(np.log(26),0.75,len(re)))
re["decision_ts"] = re.submitted_ts + pd.to_timedelta((re_ttd*3600).astype(int), unit="s")
ok = rng.random(len(re)) < np.where(re._live, 0.58, 0.45)
re["application_status"] = np.where(ok, "APPROVED", "DECLINED")
re["denial_reason_id"] = np.where(ok, None, 2)
re["approved_amount"] = np.where(ok, (re.requested_amount*0.85/50).round()*50, None)
re["apr"] = np.where(ok, 0.10, None)
f2 = ok & (rng.random(len(re)) < 0.82)
re["funded_ts"] = np.where(f2, re.decision_ts + pd.Timedelta(days=3), pd.NaT)
f2 = f2 & (pd.to_datetime(re.funded_ts) <= END).fillna(False).values
re.loc[~f2,"funded_ts"]=pd.NaT
re["funded_flag"]=f2; re["funded_amount"]=np.where(f2, re.approved_amount, None)
re["_misstated"]=False; re["model_override_flag"]=False
re = re[re.submitted_ts <= END]
apps["prior_application_id_idx"] = None
apps = pd.concat([apps, re], ignore_index=True).sort_values("submitted_ts").reset_index(drop=True)
A = len(apps)
apps["application_id"] = ["APP-" + f"{i:08d}" for i in range(10000001, 10000001+A)]
# map prior idx -> id (prior app ids were assigned after concat; resolve by matching original rows)
idmap = {}
orig = apps[apps.prior_application_id_idx.isna()]
apps["prior_application_id"] = None
apps["is_reapplication"] = apps.prior_application_id_idx.notna()
# link re-apps to the latest prior declined app of the same member
dec_latest = apps[(apps.application_status=="DECLINED") & ~apps.is_reapplication].sort_values("decision_ts").groupby("member_id").application_id.last()
apps.loc[apps.is_reapplication, "prior_application_id"] = apps.loc[apps.is_reapplication, "member_id"].map(dec_latest).values
apps["loan_account_id"] = np.where(apps.funded_flag, ["LN-" + a[4:] for a in apps.application_id], None)
apps["record_updated_ts"] = apps.decision_ts.where(apps.application_status!="PENDING", apps.submitted_ts)
print("applications", A, apps.application_status.value_counts().to_dict())

# COMMAND ----------

# MAGIC %md ## Loan payments (servicing) — early payment default

# COMMAND ----------

L = apps[apps.funded_flag].copy()
risk = L._risk_true.fillna(0.4).values
# EPD = 60+ DPD within first 6 payments. Uncaught misstatement is the big driver.
uncaught = L._misstated.astype(bool).values & ~L._caught.fillna(False).astype(bool).values
epd_p = 0.003 + 0.13*risk**2.2 + np.where(uncaught, 0.14, 0.0)   # bureau/capacity risk + unverified-income risk
epd = rng.random(len(L)) < epd_p
L["_epd"]=epd
first_pay = pd.to_datetime(L.funded_ts).dt.normalize() + pd.Timedelta(days=30)
months_obs = ((END - first_pay).dt.days // 30 + 1).clip(lower=0)
termL = np.where(L.term_months.values==0, 36, L.term_months.values)
k = np.minimum(months_obs.values, termL).astype(int)
idx = np.repeat(np.arange(len(L)), k)
n_in = np.concatenate([np.arange(x) for x in k]) if k.sum() else np.array([])
pay = pd.DataFrame({"loan_account_id":L.loan_account_id.values[idx], "application_id":L.application_id.values[idx],
                    "member_id":L.member_id.values[idx], "institution_id":L.institution_id.values[idx], "installment_number":n_in+1})
pay["due_date"] = first_pay.values[idx] + pd.to_timedelta(30*n_in, unit="D")
amtL = L.funded_amount.astype(float).values[idx]; aprL = L.apr.astype(float).fillna(0.1).values[idx]/12
termI = termL[idx]
sched = amtL*aprL/(1-(1+aprL)**(-termI))
epd_i = epd[idx]; miss_start = 2
missed = epd_i & (n_in >= miss_start) & (n_in <= miss_start+3)
late = (~missed) & (rng.random(len(pay)) < 0.035)
pay["days_past_due"] = np.where(missed, (n_in-miss_start+1)*30, np.where(late, rng.integers(3,25,len(pay)), 0))
pay["payment_status"] = np.where(missed, "MISSED", np.where(late, "LATE", "COMPLETED"))
pay["scheduled_amount"] = sched.round(2)
pay["payment_amount"] = np.where(missed, 0.0, (sched + np.where(late, 25.0, 0)).round(2))
interest = (amtL*(1 - n_in/termI)*aprL).round(2)
pay["interest_amount"] = np.where(missed, 0.0, np.minimum(interest, pay.payment_amount))
pay["late_fee_amount"] = np.where(late, 25.0, 0.0)
pay["principal_amount"] = (pay.payment_amount - pay.interest_amount - pay.late_fee_amount).clip(lower=0).round(2)
pay["payment_date"] = np.where(missed, pd.NaT, pay.due_date + pd.to_timedelta(np.where(late, pay.days_past_due, rng.integers(-3,1,len(pay))), unit="D"))
pay["payment_method"] = rng.choice(["ACH","AUTOPAY","CARD","BRANCH","CHECK"], len(pay), p=[.34,.42,.1,.06,.08])
pay = pay[pay.due_date <= END]
pay["payment_transaction_id"] = ["PMT-" + f"{i:09d}" for i in range(1, len(pay)+1)]
pay["_month"] = pay.due_date.dt.strftime("%Y-%m")
for m, g in pay.groupby("_month"):
    g.drop(columns="_month").to_csv(f"{VOL}/loan_payments/loan_payments_{m}.csv", index=False)
print("payments", len(pay), "loans", len(L), "EPD rate", epd.mean().round(4))

# COMMAND ----------

# MAGIC %md ## Member / loan-officer notes (unstructured → `ai_classify`)

# COMMAND ----------

NOTE_T = {
 "HARDSHIP": ["Member called, reduced hours at {emp}, asked about skipping a payment next month.",
              "Member reports medical bills; requesting payment deferral options on {prod} loan.",
              "Lost second job, worried about making the {prod} payment. Asked for hardship program info."],
 "RATE_SHOPPING": ["Member says dealer quoted a lower APR elsewhere, asked if we can match.",
                   "Applicant comparing our offer with an online lender, wants a decision today or will go elsewhere.",
                   "Asked why our rate is higher than the bank down the street. Considering withdrawing application."],
 "DOCUMENT_ISSUE": ["Uploaded pay stub is blurry, asked member to resend.",
                    "Pay stub employer name does not match application ({emp}). Requested clarification.",
                    "Member can't find last two pay stubs, will upload bank statements instead."],
 "FRAUD_CONCERN": ["Pay stub fonts look inconsistent and YTD totals don't add up. Escalating.",
                   "Phone number on application belongs to a different person per callback. Flagged for review.",
                   "Stated income is much higher than the deposits we see. Possible inflated income."],
 "STATUS_INQUIRY": ["Member asked for status, applied {d} days ago and has not heard back.",
                    "Dealer called asking if the {prod} application is approved yet, customer is waiting on the lot.",
                    "Applicant emailed asking when a decision will be made."],
 "COMPLAINT": ["Member unhappy with how long the decision is taking, said this is the third call.",
               "Complained about the decline letter not explaining what to do next.",
               "Frustrated that the branch asked for the same document twice."],
}
cats = list(NOTE_T)
cat_p_before = np.array([.12,.17,.18,.07,.30,.16]); cat_p_after = np.array([.14,.14,.20,.09,.25,.18])
sample = apps.sample(n=26000, random_state=11)
nrows=[]
for i,(aid, mid_, inst, ts, prod, lv) in enumerate(zip(sample.application_id, sample.member_id, sample.institution_id, sample.submitted_ts, sample.product_code, sample._live.fillna(False))):
    c = rng.choice(cats, p=(cat_p_after if lv else cat_p_before))
    t = rng.choice(NOTE_T[c]).format(emp=rng.choice(EMPLOYERS[:-1]), prod=prod.lower(), d=int(rng.integers(2,6)))
    nrows.append((f"NOTE-{i+1:07d}", aid, mid_, inst, (ts + pd.Timedelta(hours=int(rng.integers(1,72)))).strftime("%Y-%m-%dT%H:%M:%S"),
                  rng.choice(["MEMBER","LOAN_OFFICER","UNDERWRITER"],p=[.35,.4,.25]), t, c))
notes = pd.DataFrame(nrows, columns=["note_id","application_id","member_id","institution_id","created_ts","author_role","note_text","_true_category"])
notes = notes[pd.to_datetime(notes.created_ts) <= END]
notes["_month"]=notes.created_ts.str[:7]
for m,g in notes.groupby("_month"):
    g.drop(columns=["_month","_true_category"]).to_json(f"{VOL}/member_notes/member_notes_{m}.json", orient="records", lines=True)
print("notes", len(notes))

# COMMAND ----------

# MAGIC %md ## Write applications extracts (monthly backfill files) + hidden ground truth for evaluation

# COMMAND ----------

app_cols = ["application_id","institution_id","branch_id","member_id","channel","dealer_id","product_code","requested_amount","term_months",
            "stated_monthly_income","submitted_ts","decision_ts","decision_source","decision_engine","application_status","denial_reason_id",
            "approved_amount","apr","funded_flag","funded_ts","funded_amount","loan_account_id","income_verified_flag","underwriter_id",
            "model_override_flag","is_reapplication","prior_application_id","record_updated_ts"]
out = apps[app_cols].copy()
out.loc[out.application_status=="PENDING", ["decision_ts","decision_source","decision_engine"]] = None
for c in ["submitted_ts","decision_ts","funded_ts","record_updated_ts"]:
    out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d %H:%M:%S")
# DQ defects injected: negative amounts, duplicate rows, unknown product
dq1 = out.sample(n=120, random_state=21).copy(); dq1["requested_amount"] = -dq1.requested_amount
dq2 = out.sample(n=300, random_state=22).copy()                                   # exact duplicates (re-sent extract)
dq3 = out.sample(n=60, random_state=23).copy(); dq3["product_code"] = "UNKNOWN"
out = pd.concat([out, dq1, dq2, dq3])
out["_month"] = out.submitted_ts.str[:7]
for m,g in out.groupby("_month"):
    g.drop(columns="_month").to_csv(f"{VOL}/applications/applications_{m}.csv", index=False)

# hidden truth for model/AI evaluation lives in the ML schema (never in landing)
truth = apps[["application_id","member_id","_misstated","_caught"]].rename(columns={"_misstated":"income_misstated","_caught":"misstatement_caught"})
truth = truth.merge(members[["member_id","_true_income"]].rename(columns={"_true_income":"true_monthly_income"}), on="member_id", how="left")
truth["income_misstated"] = truth.income_misstated.fillna(False).astype(bool)
truth["misstatement_caught"] = truth.misstatement_caught.fillna(False).astype(bool)
spark.createDataFrame(truth).write.mode("overwrite").option("overwriteSchema","true").saveAsTable(f"{CATALOG}.ml_lend_ml.eval_income_truth")
spark.createDataFrame(notes[["note_id","_true_category"]].rename(columns={"_true_category":"human_label"}).sample(n=600, random_state=3)) \
     .write.mode("overwrite").option("overwriteSchema","true").saveAsTable(f"{CATALOG}.ml_lend_ml.eval_note_labels")
# members' true income needed later to render pay-stub PDFs
spark.createDataFrame(members[["member_id","first_name","last_name","employer_name","_true_income"]].rename(columns={"_true_income":"true_monthly_income"})) \
     .write.mode("overwrite").option("overwriteSchema","true").saveAsTable(f"{CATALOG}.ml_lend_ml._paystub_source")
print("done", len(out))
