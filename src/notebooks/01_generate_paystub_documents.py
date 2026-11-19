# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate synthetic pay-stub PDFs (member-submitted documents)
# MAGIC Renders ~1,500 pay stubs for recent pilot-CU applications (last ~45 days) in 3 different payroll-provider layouts,
# MAGIC so `ai_parse_document` + `ai_extract` have realistic variety. Gross pay reflects the member's **true** income; members who
# MAGIC inflated their stated income on the application therefore show a mismatch — exactly what underwriters need to catch.
# MAGIC Also writes 3 **live-demo** documents to `documents/demo/` (not auto-ingested) used by the Workbench app.

# COMMAND ----------

# MAGIC %pip install reportlab==4.2.5 -q

# COMMAND ----------

import os, shutil, numpy as np, pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

CATALOG="demo_dnb_catalog"
DOC_VOL=f"/Volumes/{CATALOG}/ml_lend_landing/documents"
OUT=f"{DOC_VOL}/paystubs"; DEMO=f"{DOC_VOL}/demo"
for p in [OUT, DEMO]:
    os.makedirs(p, exist_ok=True)
existing = set(os.listdir(OUT))
rng=np.random.default_rng(7)

apps = spark.sql(f"""
  SELECT a.application_id, a.member_id, a.institution_id, a.product_code, CAST(a.submitted_ts AS TIMESTAMP) submitted_ts, a.application_status,
         CAST(a.stated_monthly_income AS DOUBLE) stated, s.first_name, s.last_name, s.employer_name, s.true_monthly_income
  FROM (SELECT DISTINCT application_id, member_id, institution_id, product_code, submitted_ts, stated_monthly_income, application_status
        FROM read_files('/Volumes/{CATALOG}/ml_lend_landing/dataconnect/applications/', format=>'csv', header=>true)) a
  JOIN {CATALOG}.ml_lend_ml._paystub_source s USING (member_id)
  WHERE a.institution_id IN ('CU-SVCU','CU-HPCU') AND CAST(a.submitted_ts AS TIMESTAMP) >= '2026-10-03'
""").toPandas()
# keep every misstated case in the window + sample the rest to ~1,500
apps["ratio"] = apps.stated / apps.true_monthly_income
pending_ids = set(apps[apps.application_status=="PENDING"].application_id)
apps = apps.sort_values("application_status").drop_duplicates("application_id")   # one row per application
pend = apps[apps.application_id.isin(pending_ids)]                                # open underwriting queue: always has a document
mis = apps[(apps.ratio > 1.2) & ~apps.application_id.isin(pending_ids)]
rest = apps[(apps.ratio <= 1.2) & ~apps.application_id.isin(pending_ids)].sample(n=max(0, 1500-len(mis)-len(pend)), random_state=3)
docs = pd.concat([pend, mis, rest]).drop_duplicates("application_id")
print(len(apps), "candidates;", len(docs), "documents;", len(mis), "with income mismatch")

FREQ = [("Bi-Weekly",26/12),("Semi-Monthly",2.0),("Weekly",52/12),("Monthly",1.0)]
PROVIDERS = ["PayGrid Payroll Services","Northstar Payroll Co.","ClearPay HR"]

def money(x): return f"${x:,.2f}"

def render(path, name, employer, gross_monthly, period_end, style, freq_idx, emp_id):
    fname, ppm = FREQ[freq_idx]
    gross = round(gross_monthly/ppm, 2)
    periods_ytd = max(1, int(period_end.dayofyear/365*ppm*12))
    ytd = round(gross*periods_ytd, 2)
    fed = round(gross*0.11,2); state=round(gross*0.04,2); fica=round(gross*0.0765,2); k401=round(gross*0.05,2); med=round(gross*0.03,2)
    net = round(gross-fed-state-fica-k401-med,2)
    c = canvas.Canvas(path, pagesize=letter); W,H = letter
    prov = PROVIDERS[style]
    if style==0:
        c.setFillColor(colors.HexColor("#1F3A5F")); c.rect(0,H-80,W,80,fill=1,stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold",18); c.drawString(40,H-45,employer)
        c.setFont("Helvetica",9); c.drawString(40,H-62,f"Earnings Statement  ·  processed by {prov}")
        c.setFillColor(colors.black); y=H-120
        c.setFont("Helvetica-Bold",10); c.drawString(40,y,"Employee"); c.drawString(320,y,"Pay Details")
        c.setFont("Helvetica",10)
        c.drawString(40,y-15,name); c.drawString(40,y-30,f"Employee ID: {emp_id}")
        c.drawString(320,y-15,f"Pay Frequency: {fname}"); c.drawString(320,y-30,f"Pay Period End: {period_end:%m/%d/%Y}")
        c.drawString(320,y-45,f"Pay Date: {(period_end+pd.Timedelta(days=5)):%m/%d/%Y}")
        y-=90; c.setFont("Helvetica-Bold",10); c.drawString(40,y,"Earnings"); c.drawString(250,y,"Current"); c.drawString(380,y,"Year to Date")
        c.setFont("Helvetica",10); c.drawString(40,y-16,"Regular Gross Pay"); c.drawString(250,y-16,money(gross)); c.drawString(380,y-16,money(ytd))
        y-=50; c.setFont("Helvetica-Bold",10); c.drawString(40,y,"Deductions")
        c.setFont("Helvetica",10)
        for i,(k,v) in enumerate([("Federal Income Tax",fed),("State Income Tax",state),("Social Security & Medicare",fica),("401(k)",k401),("Medical",med)]):
            c.drawString(40,y-16*(i+1),k); c.drawString(250,y-16*(i+1),money(v))
        y-=110; c.setFont("Helvetica-Bold",12); c.drawString(40,y,f"Gross Pay This Period: {money(gross)}"); c.drawString(320,y,f"Net Pay: {money(net)}")
        c.setFont("Helvetica",10); c.drawString(40,y-18,f"Year-to-Date Gross: {money(ytd)}")
    elif style==1:
        c.setFont("Times-Bold",16); c.drawCentredString(W/2,H-50,prov.upper())
        c.setFont("Times-Roman",11); c.drawCentredString(W/2,H-66,f"Statement of Earnings for {name}")
        c.line(40,H-80,W-40,H-80)
        rows=[("Company",employer),("Employee Number",emp_id),("Pay Schedule",fname),("Period Ending",f"{period_end:%B %d, %Y}"),
              ("Gross Earnings (this period)",money(gross)),("Gross Earnings (YTD)",money(ytd)),("Total Taxes",money(fed+state+fica)),
              ("Total Deductions",money(k401+med)),("Net Pay",money(net))]
        y=H-110
        for k,v in rows:
            c.setFont("Times-Bold",11); c.drawString(60,y,k); c.setFont("Times-Roman",11); c.drawString(300,y,v); y-=20
        c.setFont("Times-Italic",8); c.drawString(60,60,"This statement is for informational purposes. Synthetic document generated for a Databricks demo.")
    else:
        c.setFont("Courier-Bold",12); c.drawString(40,H-50,f"{employer} -- PAY ADVICE")
        c.setFont("Courier",10)
        lines=[f"EMPLOYEE: {name}   ID {emp_id}", f"FREQUENCY: {fname.upper()}", f"PERIOD END: {period_end:%Y-%m-%d}",
               "-"*60, f"GROSS PAY CURRENT ........ {money(gross):>14}", f"GROSS PAY YTD ............ {money(ytd):>14}",
               f"FED TAX .................. {money(fed):>14}", f"STATE TAX ................ {money(state):>14}", f"FICA ..................... {money(fica):>14}",
               f"401K ..................... {money(k401):>14}", f"MEDICAL .................. {money(med):>14}", "-"*60,
               f"NET PAY .................. {money(net):>14}", "", f"Payroll processed by {prov}"]
        y=H-80
        for l in lines: c.drawString(40,y,l); y-=15
    c.save()
    return gross, fname

meta=[]
for r in docs.itertuples():
    if f"{r.application_id}_paystub.pdf" in existing: continue
    style=int(rng.integers(0,3)); fi=int(rng.choice(4,p=[.55,.25,.1,.1]))
    pe = (pd.Timestamp(r.submitted_ts).normalize() - pd.Timedelta(days=int(rng.integers(3,14))))
    g,f = render(f"{OUT}/{r.application_id}_paystub.pdf", f"{r.first_name} {r.last_name}", r.employer_name if r.employer_name!="Self-employed" else "Granite Peak Construction",
                 r.true_monthly_income, pe, style, fi, f"E{int(rng.integers(10000,99999))}")
    meta.append((r.application_id, style, f, g))
print("rendered", len(meta))

# --- live-demo documents (used by the Workbench "New application" flow)
demo = [("APP-LIVE0001","Jordan Whitaker","Northwind Logistics",4200.0,0,0),   # stated 7,500 -> big mismatch
        ("APP-LIVE0002","Maya Okafor","Cedar Ridge Health",6850.0,1,1),        # stated 6,900 -> verified
        ("APP-LIVE0003","Diego Castellano","Silverleaf Software",9100.0,2,0)]  # stated 9,000 -> verified
for aid,n,e,inc,st,fi in demo:
    render(f"{DEMO}/{aid}_paystub.pdf", n, e, inc, pd.Timestamp("2026-11-07"), st, fi, "E40112")
print(os.listdir(DEMO))
