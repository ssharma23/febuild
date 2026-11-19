"""Build the 'Speed and Trust' assessment deck on the Databricks Corporate Slide Template 2024 (shared drive).
Keeps the template's Financial Services title, section divider and closing slides; content slides use
'7 Content A - Basic' with custom shapes/tables. Adds speaker notes. Usage: python3 build_deck.py"""
import sys, time, uuid
sys.path.insert(0, "/Users/sonam.s/.vibe/marketplace/plugins/fe-google-tools/skills/google-slides/resources")
import gslides_builder as gb

TEMPLATE = "1MamDvbmyMGBJ4799vsI0C7-CkxA8j7ohya7WWj32zPk"
KEEP_TITLE, KEEP_SECTION, KEEP_CLOSING = "g262a25bb6fc_0_379", "g262a25bb6fc_0_701", "g262a25bb6fc_0_3501"
CONTENT_LAYOUT = "g3a0039abd09_0_81"
E = 914400; FONT = "DM Sans"
def rgb(h): h = h.lstrip("#"); return {"red": int(h[0:2],16)/255, "green": int(h[2:4],16)/255, "blue": int(h[4:6],16)/255}
NAVY, DEEP, BLUE, TEAL, SLATE, GRN = "#004268", "#15295A", "#0061A4", "#007FA4", "#727D82", "#3E8E3A"
DT, WHITE, LG = "#1B3037", "#FFFFFF", "#EEF3F7"
def nid(p="o"): return p + uuid.uuid4().hex[:16]

def api(method, url, data=None):
    if "googleapis.com/drive/v3/files/" in url:
        url += ("&" if "?" in url else "?") + "supportsAllDrives=true"
    return gb.api_call(method, url, data)

copy = api("POST", f"https://www.googleapis.com/drive/v3/files/{TEMPLATE}/copy",
           {"name": "MeridianLink · Speed and Trust · Lending Intelligence (SA assessment)", "parents": ["root"]})
pid = copy["id"]; print("PRES", pid, flush=True)
pres = gb.get_presentation(pid)
gb.batch_update(pid, [{"deleteObject": {"objectId": s["objectId"]}} for s in pres["slides"] if s["objectId"] not in (KEEP_TITLE, KEEP_SECTION, KEEP_CLOSING)])

reqs = []
def text_style(oid, size, color, bold=False, rng=None):
    tr = {"type": "ALL"} if rng is None else {"type": "FIXED_RANGE", "startIndex": rng[0], "endIndex": rng[1]}
    reqs.append({"updateTextStyle": {"objectId": oid, "textRange": tr, "style": {"fontFamily": FONT, "fontSize": {"magnitude": size, "unit": "PT"},
                 "bold": bold, "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}}, "fields": "fontFamily,fontSize,bold,foregroundColor"}})
def box(page, x, y, w, h, fill=None, text="", size=14, color=DT, bold=False, align="START", shape="RECTANGLE", valign="MIDDLE"):
    oid = nid()
    reqs.append({"createShape": {"objectId": oid, "shapeType": shape, "elementProperties": {"pageObjectId": page,
                 "size": {"width": {"magnitude": int(w*E), "unit": "EMU"}, "height": {"magnitude": int(h*E), "unit": "EMU"}},
                 "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x*E), "translateY": int(y*E), "unit": "EMU"}}}})
    props = {"outline": {"propertyState": "NOT_RENDERED"}, "contentAlignment": valign,
             "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}} if fill else {"propertyState": "NOT_RENDERED"}}
    reqs.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": props, "fields": "outline,contentAlignment,shapeBackgroundFill"}})
    if text:
        reqs.append({"insertText": {"objectId": oid, "text": text}})
        text_style(oid, size, color, bold)
        reqs.append({"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"}, "style": {"alignment": align, "spaceBelow": {"magnitude": 4, "unit": "PT"}}, "fields": "alignment,spaceBelow"}})
    return oid
def card(page, x, y, w, h, head, body, fill, color=WHITE, hsize=17, bsize=13, align="START"):
    oid = box(page, x, y, w, h, fill, f"{head}\n{body}", bsize, color, False, align, "ROUND_RECTANGLE", "TOP" if align == "START" else "MIDDLE")
    text_style(oid, hsize, color, True, (0, len(head)))
    return oid
def table(page, data, x, y, w, h, col_w=None, size=12):
    tid = nid("t"); R, C = len(data), len(data[0])
    reqs.append({"createTable": {"objectId": tid, "rows": R, "columns": C, "elementProperties": {"pageObjectId": page,
                 "size": {"width": {"magnitude": int(w*E), "unit": "EMU"}, "height": {"magnitude": int(h*E), "unit": "EMU"}},
                 "transform": {"scaleX": 1, "scaleY": 1, "translateX": int(x*E), "translateY": int(y*E), "unit": "EMU"}}}})
    for r in range(R):
        for c in range(C):
            reqs.append({"insertText": {"objectId": tid, "cellLocation": {"rowIndex": r, "columnIndex": c}, "text": data[r][c]}})
            reqs.append({"updateTextStyle": {"objectId": tid, "cellLocation": {"rowIndex": r, "columnIndex": c}, "textRange": {"type": "ALL"},
                         "style": {"fontFamily": FONT, "fontSize": {"magnitude": size, "unit": "PT"}, "bold": r == 0 or (c == C-1 and r > 0),
                                   "foregroundColor": {"opaqueColor": {"rgbColor": rgb(WHITE if r == 0 else (BLUE if c == C-1 else DT))}}},
                         "fields": "fontFamily,fontSize,bold,foregroundColor"}})
    reqs.append({"updateTableCellProperties": {"objectId": tid, "tableRange": {"location": {"rowIndex": 0, "columnIndex": 0}, "rowSpan": 1, "columnSpan": C},
                 "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(NAVY)}}}}, "fields": "tableCellBackgroundFill"}})
    for r in range(2, R, 2):
        reqs.append({"updateTableCellProperties": {"objectId": tid, "tableRange": {"location": {"rowIndex": r, "columnIndex": 0}, "rowSpan": 1, "columnSpan": C},
                     "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(LG)}}}}, "fields": "tableCellBackgroundFill"}})
    if col_w:
        for c, cw in enumerate(col_w):
            reqs.append({"updateTableColumnProperties": {"objectId": tid, "columnIndices": [c], "tableColumnProperties": {"columnWidth": {"magnitude": int(cw*E), "unit": "EMU"}}, "fields": "columnWidth"}})
    return tid

slides = []
def content_slide(title, subtitle, body=None):
    sid, t_id, s_id, b_id = nid("s"), nid("t"), nid("u"), nid("b")
    gb.batch_update(pid, [{"createSlide": {"objectId": sid, "insertionIndex": 1, "slideLayoutReference": {"layoutId": CONTENT_LAYOUT},
        "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": t_id},
                                  {"layoutPlaceholder": {"type": "BODY", "index": 1}, "objectId": s_id},
                                  {"layoutPlaceholder": {"type": "BODY", "index": 0}, "objectId": b_id}]}}])
    r = [{"insertText": {"objectId": t_id, "text": title}}, {"insertText": {"objectId": s_id, "text": subtitle}}]
    r += [{"insertText": {"objectId": b_id, "text": body}}] if body else [{"deleteObject": {"objectId": b_id}}]
    gb.batch_update(pid, r)
    slides.append(sid); return sid

# 1 · title (template FS title slide)
gb.batch_update(pid, [
  {"deleteText": {"objectId": "g262a25bb6fc_0_382", "textRange": {"type": "ALL"}}},
  {"insertText": {"objectId": "g262a25bb6fc_0_382", "text": "Speed and Trust: Lending Intelligence for MeridianLink’s credit unions"}},
  {"deleteText": {"objectId": "g262a25bb6fc_0_380", "textRange": {"type": "ALL"}}},
  {"insertText": {"objectId": "g262a25bb6fc_0_380", "text": "Sonam Sharma · Solutions Architect\u000bNovember 2026"}}])

# 2 · problem
s = content_slide("The 24-hour cliff and the trust gap", "Every credit union is forced to trade speed against trust")
box(s, 0.82, 2.05, 5.7, 0.4, None, "SPEED · decisions that take too long", 15, BLUE, True)
card(s, 0.82, 2.5, 2.75, 1.9, "73%", "of approved loans fund when decided in under 1 hour", BLUE, hsize=40, bsize=13, align="CENTER")
card(s, 3.77, 2.5, 2.75, 1.9, "57%", "fund when the decision takes more than 24 hours", DEEP, hsize=40, bsize=13, align="CENTER")
box(s, 6.78, 2.05, 5.7, 0.4, None, "TRUST · income no one verified", 15, TEAL, True)
card(s, 6.78, 2.5, 2.75, 1.9, "1 in 15", "applicants overstate income by 25-75%", TEAL, hsize=40, bsize=13, align="CENTER")
card(s, 9.73, 2.5, 2.75, 1.9, "3 in 10", "of those caught by manual review today", NAVY, hsize=40, bsize=13, align="CENTER")
box(s, 0.82, 4.65, 11.66, 1.25, LG, "Legacy process: 31% auto-decided by rules; everyone else waits a median 17 hours. Dealers shop the deal to whoever says yes first.\n"
    "Every missed income misstatement becomes an early-payment-default risk on the book.", 14, DT, False, "START", "ROUND_RECTANGLE")
box(s, 0.82, 6.15, 11.66, 0.35, None, "Synthetic data modeled on the MeridianLink Data Connect schema · 4 fictional credit unions · 208K applications · 24 months", 10, SLATE)

# 3 · thesis
s = content_slide("You don’t have to choose between speed and trust", "MeridianLink’s promise, made operational on one platform")
card(s, 0.82, 2.1, 5.68, 3.6, "Today: speed OR trust",
     "• Legacy rules auto-decide only the obvious 31%\n• Everyone else waits ~17 hours in a queue\n• Pay stubs are checked by hand, when at all\n• Fast decisions carry hidden income risk", LG, DT, 20, 15)
card(s, 6.8, 2.1, 5.68, 3.6, "Lending Intelligence: speed AND trust",
     "• AI reads every pay stub in seconds and reconciles income\n• An explainable risk model auto-decides the safe majority\n• Underwriters only see files that need a human, with evidence\n• Declines get a “path to yes” → future funded loans", NAVY, WHITE, 20, 15)
box(s, 0.82, 5.95, 11.66, 0.5, None, "Built entirely on Databricks: Lakeflow · Unity Catalog · AI Functions · MLflow + Model Serving · Lakebase · Databricks Apps · Genie · AI/BI", 13, TEAL, True, "CENTER")

# 4 · architecture
s = content_slide("One governed platform, end to end", "From the Data Connect file drop to a decision in seconds, with one set of policies")
steps = [("1 · LAND", "Lakeflow Connect file ingestion (Auto Loader) on Data Connect extracts", NAVY),
         ("2 · TRUST", "Declarative pipelines: expectations, quarantine, AUTO CDC (SCD1/SCD2)", DEEP),
         ("3 · PROTECT", "Data Classification → tags → ABAC masks + tenant row filter; RBAC", TEAL),
         ("4 · DECIDE", "AI Functions read pay stubs; EPD model on Model Serving", BLUE),
         ("5 · ACT", "Underwriter Workbench (Databricks App) on Lakebase Postgres", "#0A7BB5"),
         ("6 · EXPLAIN", "Metric views → Genie, AI/BI dashboard, Databricks One", GRN)]
w = (11.66 - 5*0.14)/6
for i, (h, b, c) in enumerate(steps):
    card(s, 0.82 + i*(w+0.14), 2.05, w, 2.15, h, b, c, WHITE, 15, 12, "CENTER")
box(s, 0.82, 4.4, 11.66, 0.55, DT, "UNITY CATALOG · lineage · tags · ABAC / RBAC · one platform, isolated per credit union", 14, WHITE, True, "CENTER", "ROUND_RECTANGLE")
card(s, 0.82, 5.15, 5.73, 1.35, "Batch path (nightly)", "Data Connect files → pipeline → AI + model scores → underwriting queue synced to Lakebase", LG, DT, 14, 12)
card(s, 6.75, 5.15, 5.73, 1.35, "Live path (seconds)", "New application → AI reads pay stub → model scores → routed → decision written to Lakebase → back to Delta", LG, DT, 14, 12)

# 5 · proof
s = content_slide("Proof: pilot vs control credit unions", "Two credit unions went live Nov-2025, two did not; difference-in-differences isolates the effect")
table(s, [["Metric", "Pilot before", "Pilot after", "Control before", "Control after", "Net lift"],
          ["Auto-decision rate", "31.3%", "57.6%", "31.2%", "31.5%", "+26.0 pts"],
          ["Median time to decision", "17.1 h", "8 min", "17.1 h", "17.0 h", "−17 h"],
          ["Decided within 24 hours", "61.2%", "96.4%", "61.2%", "61.6%", "+34.8 pts"],
          ["Pull-through (funded ÷ approved)", "67.1%", "71.5%", "67.9%", "66.8%", "+5.5 pts"],
          ["Early payment default (60+ DPD, first 6)", "2.74%", "1.89%", "2.89%", "3.20%", "−1.2 pts"]],
      0.82, 2.1, 11.66, 3.3, [3.66, 1.6, 1.6, 1.6, 1.6, 1.6], 14)
box(s, 0.82, 5.7, 11.66, 0.7, LG, "Every cell is a governed metric-view query; ask Genie “Did Lending Intelligence improve pull-through?” and it returns this table.", 13, DT, False, "START", "ROUND_RECTANGLE")

# 6 · value
s = content_slide("≈ $3.6M a year for a 40K-application credit union", "Trust pays more than speed, and it’s conservative")
vals = [("Early-default losses avoided (AI income check)", 1.71, TEAL), ("Faster decisions → more funded loans", 0.85, BLUE),
        ("Underwriter capacity released (~15K hours)", 0.72, NAVY), ("Declines turned into funded loans", 0.35, GRN)]
for i, (lab, v, c) in enumerate(vals):
    y = 2.1 + i*0.82
    box(s, 0.82, y, 4.3, 0.6, None, lab, 14, DT, False, "END")
    box(s, 5.3, y, 5.6*v/1.71, 0.6, c)
    box(s, 5.4 + 5.6*v/1.71, y, 1.3, 0.6, None, f"${v:.2f}M", 16, DT, True)
card(s, 0.82, 5.5, 5.73, 1.05, "Assumptions", "First-year interest only (3.5% NIM) · 55% loss given default · 45→20 min per file at $48/h · halve the default effect → still ≈ $2.8M", LG, DT, 13, 11)
card(s, 6.75, 5.5, 5.73, 1.05, "For MeridianLink", "One productized capability for its credit-union base: tenant #2 is an entitlement row, not a new stack", NAVY, WHITE, 13, 12)

# 7 · plan
content_slide("30-60-90 days to production", "Start with one design partner, prove it with the same experiment design",
  "Day 30: real Data Connect feed for one design-partner credit union; model + AI checks in shadow mode\n"
  "Day 60: compliance review of model, reason codes and member letters; Workbench pilot with 3 underwriters\n"
  "Day 90: go-live for auto and personal loans; difference-in-differences readout vs control\n"
  "Then: tenant #2 in days, not months (same pipeline, same policies)\n"
  "Ask: a MeridianLink product + data sponsor and one design-partner credit union")

# appendix
gb.batch_update(pid, [{"deleteText": {"objectId": "g262a25bb6fc_0_703", "textRange": {"type": "ALL"}}},
                      {"insertText": {"objectId": "g262a25bb6fc_0_703", "text": "Appendix"}}])
main_slides = list(slides)
s = content_slide("A1 · Value assumptions", "Every dollar = measured difference-in-differences × a documented assumption")
table(s, [["Lever", "Measured input", "Assumption", "Ref. CU / year"],
          ["Faster decisions → more funded loans", "+5.5 pts pull-through", "3.5% NIM, first year only", "$0.85M"],
          ["Underwriter capacity released", "Manual share 69% → 42%", "45 → 20 min per file, $48/h", "$0.72M"],
          ["Early-default losses avoided", "−1.2 pts EPD", "55% loss given default", "$1.71M"],
          ["Declines turned into funded loans", "+1.2% of applications", "3.5% NIM", "$0.35M"],
          ["Total", "ml_lend_semantic.v_value_bridge", "ml_lend_gold.roi_assumptions", "$3.63M"]],
      0.82, 2.1, 11.66, 3.3, [3.6, 2.9, 3.16, 2.0], 13)
s = content_slide("A2 · Governance model", "RBAC decides which layer you can touch; ABAC decides which rows and columns you see")
card(s, 0.82, 2.1, 5.68, 3.4, "RBAC: layers", "• Platform team owns bronze, silver, ml\n• Business users: gold + metric views only\n• Workbench app service principal: least privilege\n• Genie + dashboards run as the viewer", LG, DT, 19, 15)
card(s, 6.8, 2.1, 5.68, 3.4, "ABAC: rows and columns", "• Data Classification auto-tags PII (class.*)\n• Masks follow the tag: SSN, DOB, contact\n• Row filter on tenant_isolation_key\n• Same policy flows to Genie, BI and apps", NAVY, WHITE, 19, 15)
s = content_slide("A3 · What was built", "Everything lives in the fevm-demo-dnb workspace and a local bundle folder for review")
table(s, [["Capability", "Asset"],
          ["Lakeflow ingest + medallion", "Pipeline ‘MeridianLink Lending · Data Connect Medallion’ (bronze → silver → gold)"],
          ["Data quality", "Expectations (drop / warn / fail) + quarantine tables; DQ page from the event log"],
          ["Classification, ABAC, RBAC", "Auto-tagging; 3 column masks + tenant row filter; schema grants"],
          ["AI Functions", "ai_parse_document · ai_extract · ai_classify · ai_query (member letters)"],
          ["ML", "ml_lend_ml.epd_risk_model@champion (LightGBM + SHAP) on Model Serving"],
          ["Semantic + BI", "3 metric views · Genie space · AI/BI dashboard · Databricks One"],
          ["App", "Lending Intelligence Workbench (Databricks App) on Lakebase Postgres"]],
      0.82, 2.05, 11.66, 4.4, [3.3, 8.36], 12)
appendix = slides[len(main_slides):]

for i in range(0, len(reqs), 60):
    gb.batch_update(pid, reqs[i:i+60]); time.sleep(1.5)

order = [KEEP_TITLE] + main_slides + [KEEP_SECTION] + appendix + [KEEP_CLOSING]
for i, sid in enumerate(order): gb.batch_update(pid, [{"updateSlidesPosition": {"slideObjectIds": [sid], "insertionIndex": i}}])

NOTES = {
 KEEP_TITLE: "Hook with MeridianLink's own words: 'You don't have to choose between speed and trust.' Today every credit union does choose. In the next 20 minutes: a governed platform that removes that trade-off, the proof, and what it's worth.",
 main_slides[0]: "Speed: decide an approved loan in under an hour and 73% fund; take more than 24 hours and only 57% do, because the member or the dealer goes elsewhere. Trust: about 1 in 15 applicants overstate income and manual review catches roughly 3 in 10, which shows up later as early defaults. Synthetic data, modeled on Data Connect.",
 main_slides[1]: "The usual fix makes one worse to improve the other. Lending Intelligence verifies income with AI on every application and uses an explainable model, so we auto-decide more AND decline the risky ones.",
 main_slides[2]: "Six steps, one platform. Land: Lakeflow file ingestion on the Data Connect drop. Trust: declarative pipelines with quality rules and CDC. Protect: classification feeds ABAC; each credit union only sees itself. Decide: AI Functions + the EPD model. Act: the Workbench app on Lakebase. Explain: metric views behind Genie, dashboards and Databricks One. Unity Catalog underneath is why one platform can serve every credit union.",
 main_slides[3]: "Two credit unions went live Nov-2025, two did not. Difference-in-differences removes seasonality and rate effects. Auto-decisions nearly doubled; median decision time went from 17 hours to 8 minutes; pull-through +5.5 points net; early defaults down 1.2 points net.",
 main_slides[4]: "About $3.6M a year for a 40K-application credit union. The biggest lever is trust, not speed: $1.7M of avoided early-default losses. Conservative: first-year interest only; underwriter value is capacity, not layoffs. Halve the default effect and it's still ~$2.8M.",
 main_slides[5]: "Make it real in 90 days with one design partner. Isolation is policy, not infrastructure, so tenant #2 is an entitlement row, not a new stack. The ask: a sponsor and a design partner.",
}
pres = gb.get_presentation(pid); nreq = []
for sl in pres["slides"]:
    note = NOTES.get(sl["objectId"])
    sp = sl.get("slideProperties", {}).get("notesPage", {}).get("notesProperties", {}).get("speakerNotesObjectId")
    if note and sp: nreq.append({"insertText": {"objectId": sp, "text": note}})
if nreq: gb.batch_update(pid, nreq)
open("/Users/sonam.s/meridianlink_lending_story/.deck_id", "w").write(pid)
print("DONE https://docs.google.com/presentation/d/" + pid + "/edit")
