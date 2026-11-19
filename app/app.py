"""Lending Intelligence Workbench — Summit Valley Credit Union (MeridianLink demo, synthetic data).

Data paths
  * Underwriting queue  : Lakebase (synced from Delta ml_lend_ml.underwriting_queue) + live applications (Lakebase)
  * Decisions / audit   : Lakebase lending.workbench.*  (replicated back to Delta ml_lend_ops via Lakebase CDF)
  * Document AI         : ai_parse_document + ai_extract on the SQL warehouse (Unity Catalog governed)
  * Risk model          : Model Serving endpoint ml-lend-epd-risk (UC model epd_risk_model@champion)
  * Outcomes            : Unity Catalog metric views (ml_lend_semantic) — ABAC tenant isolation applies to this app's identity
"""
import base64, html, json, os, time
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

# ---------------------------------------------------------------- config
CAT = os.getenv("CATALOG", "demo_dnb_catalog")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "6ea47fe72fea6233")
ENDPOINT = os.getenv("SERVING_ENDPOINT", "ml-lend-epd-risk")
TENANT = os.getenv("TENANT", "CU-SVCU")
PG_PROJECT = os.getenv("PG_PROJECT", "meridianlink-lending")
PG_BRANCH = os.getenv("PG_BRANCH", "production")
PG_DB = os.getenv("PG_DB", "lending")
PG_EP = f"projects/{PG_PROJECT}/branches/{PG_BRANCH}/endpoints/primary"
QUEUE_TABLE = os.getenv("QUEUE_TABLE", "ml_lend_ml.underwriting_queue_synced")
LLM = os.getenv("LLM_ENDPOINT", "databricks-claude-haiku-5-5")
DEMO_DOCS = {  # allowlist: only these paths can ever be inlined into SQL
    "APP-LIVE0001 · Jordan Whitaker · Northwind Logistics": "/Volumes/demo_dnb_catalog/ml_lend_landing/documents/demo/APP-LIVE0001_paystub.pdf",
    "APP-LIVE0002 · Maya Okafor · Cedar Ridge Health": "/Volumes/demo_dnb_catalog/ml_lend_landing/documents/demo/APP-LIVE0002_paystub.pdf",
    "APP-LIVE0003 · Diego Castellano · Silverleaf Software": "/Volumes/demo_dnb_catalog/ml_lend_landing/documents/demo/APP-LIVE0003_paystub.pdf",
}
DEMO_DEFAULTS = {
    "APP-LIVE0001": dict(name="Jordan Whitaker", employer="Northwind Logistics", product="AUTO", amount=32000, term=60, income=7500, credit=702, debt=900),
    "APP-LIVE0002": dict(name="Maya Okafor", employer="Cedar Ridge Health", product="PERSONAL", amount=12000, term=36, income=6900, credit=731, debt=650),
    "APP-LIVE0003": dict(name="Diego Castellano", employer="Silverleaf Software", product="AUTO", amount=41000, term=72, income=9000, credit=768, debt=1400),
}
BASE_APR = {"AUTO": 0.0599, "PERSONAL": 0.1099, "CARD": 0.1799, "HELOC": 0.0749}
FEATURES = ["credit_score", "stated_monthly_income", "monthly_debt_payments", "dti_stated", "loan_to_income", "requested_amount", "term_months",
            "apr", "product_AUTO", "product_PERSONAL", "product_CARD", "product_HELOC", "channel_DEALER", "channel_ONLINE", "channel_MOBILE",
            "channel_BRANCH", "member_tenure_years"]

NAVY, DEEP, BLUE, TEAL, CYAN, GREEN, SLATE = "#004268", "#15295A", "#0061A4", "#007FA4", "#00B9F2", "#6EC068", "#727D82"
INK, BORDER, BG, RED, AMBER = "#222222", "#E2E8F0", "#F6F8FA", "#C62828", "#E8710A"
BAND_COLOR = {"LOW": GREEN, "MEDIUM": AMBER, "HIGH": RED}
ROUTE_COLOR = {"INCOME_MISMATCH": RED, "HIGH_RISK": AMBER, "PRODUCT_POLICY": TEAL, "STANDARD_REVIEW": BLUE, "AUTO_APPROVE": GREEN}

st.set_page_config(page_title="Lending Intelligence Workbench · Summit Valley CU", page_icon="🏦", layout="wide",
                   initial_sidebar_state="collapsed")
cfg = Config()


# ---------------------------------------------------------------- connections
@st.cache_resource
def ws():
    return WorkspaceClient()


@st.cache_resource
def sql_conn():
    return sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
                       credentials_provider=lambda: cfg.authenticate)


def q(query, params=None):
    try:
        cur = sql_conn().cursor()
    except Exception:
        sql_conn.clear(); cur = sql_conn().cursor()
    with cur:
        cur.execute(query, params or {})
        df = cur.fetchall_arrow().to_pandas()
    for c in df.columns:
        if isinstance(df[c].dtype, pd.DatetimeTZDtype):
            df[c] = df[c].dt.tz_convert("UTC").dt.tz_localize(None)
    return df


@st.cache_resource(ttl=2700)
def pg_params():
    w = ws()
    eps = w.api_client.do("GET", f"/api/2.0/postgres/projects/{PG_PROJECT}/branches/{PG_BRANCH}/endpoints")
    host = (eps.get("endpoints") or eps)[0]["status"]["hosts"]["host"]
    token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": PG_EP})["token"]
    user = cfg.client_id or w.current_user.me().user_name
    return dict(host=host, dbname=PG_DB, user=user, password=token, sslmode="require")


def pg(query, params=None, fetch=True):
    try:
        conn = psycopg.connect(**pg_params(), autocommit=True)
    except Exception:
        pg_params.clear(); conn = psycopg.connect(**pg_params(), autocommit=True)
    with conn, conn.cursor() as cur:
        cur.execute(query, params or ())
        if fetch and cur.description:
            cols = [d.name for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)
    return None


def b64(path):
    try:
        return base64.b64encode(open(os.path.join(os.path.dirname(__file__), path), "rb").read()).decode()
    except Exception:
        return ""


LOGO = b64("ml_logo_color.svg")
ME = os.getenv("DATABRICKS_APP_NAME", "workbench")


def current_underwriter():
    try:
        return st.context.headers.get("X-Forwarded-Email") or st.context.headers.get("X-Forwarded-Preferred-Username") or "underwriter@summitvalley.example"
    except Exception:
        return "underwriter@summitvalley.example"


# ---------------------------------------------------------------- style
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
  html, body, [class*="css"], .stApp, button, input, textarea, select {{ font-family: 'Roboto', sans-serif !important; }}
  .stApp {{ background:{BG}; color:{INK}; }}
  header[data-testid="stHeader"] {{ background:transparent; height:0; }}
  #MainMenu, footer, [data-testid="stToolbar"] {{ visibility:hidden; }}
  .block-container, [data-testid="stMainBlockContainer"] {{ max-width:100% !important; padding:0.6rem 1.5rem 1rem 1.5rem !important; }}
  .ml-top {{ background:#fff; border-bottom:1px solid {BORDER}; margin:-0.6rem -1.5rem 0 -1.5rem; padding:10px 1.5rem;
            display:flex; align-items:center; justify-content:space-between; }}
  .ml-top img {{ height:32px; }} .ml-top .r {{ color:{SLATE}; font-size:12.5px; text-align:right; line-height:1.35; }}
  .ml-band {{ background:linear-gradient(90deg,{NAVY} 0%,{DEEP} 100%); margin:0 -1.5rem 16px -1.5rem; padding:16px 1.5rem; color:#fff;
             display:flex; justify-content:space-between; align-items:center; }}
  .ml-band .t {{ font-size:22px; font-weight:500; }} .ml-band .s {{ font-size:13px; color:#B9D3E6; margin-top:2px; }}
  .pill {{ display:inline-block; border-radius:16px; padding:3px 11px; font-size:12px; font-weight:700; color:#fff; }}
  .kpi {{ background:#fff; border:1px solid {BORDER}; border-top:4px solid {BLUE}; border-radius:10px; padding:12px 14px; min-height:108px; }}
  .kpi .l {{ color:{SLATE}; font-size:11px; text-transform:uppercase; letter-spacing:.6px; font-weight:500; }}
  .kpi .v {{ color:{NAVY}; font-size:28px; font-weight:700; line-height:1.25; }} .kpi .d {{ color:{SLATE}; font-size:12px; }}
  .card {{ background:#fff; border:1px solid {BORDER}; border-radius:10px; padding:14px 16px; margin-bottom:10px; }}
  .card h4 {{ color:{NAVY}; margin:0 0 8px 0; font-size:15px; font-weight:700; }}
  .muted {{ color:{SLATE}; font-size:12.5px; }}
  .alert {{ border-left:5px solid {RED}; background:#FDECEC; padding:10px 14px; border-radius:6px; color:#7a1414; font-weight:500; }}
  .ok {{ border-left:5px solid {GREEN}; background:#EEF8EC; padding:10px 14px; border-radius:6px; color:#1f5b1a; font-weight:500; }}
  .step {{ display:flex; justify-content:space-between; padding:7px 10px; border-bottom:1px solid {BORDER}; font-size:14px; }}
  .step b {{ color:{NAVY}; }}
  .letter {{ background:#fff; border:1px solid {BORDER}; border-left:5px solid {TEAL}; border-radius:8px; padding:14px 18px; white-space:pre-wrap; font-size:14px; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:6px; }}
  .stTabs [data-baseweb="tab"] {{ background:#fff; border:1px solid {BORDER}; border-radius:8px 8px 0 0; padding:8px 18px; color:{NAVY}; }}
  .stTabs [aria-selected="true"] {{ background:{NAVY} !important; color:#fff !important; }}
  .stButton>button, .stFormSubmitButton>button {{ background:{BLUE}; color:#fff; border:0; border-radius:6px; font-weight:500; }}
  .stButton>button:hover, .stFormSubmitButton>button:hover {{ background:{NAVY}; color:#fff; }}
  .ml-foot {{ color:{SLATE}; font-size:11px; text-align:center; margin-top:28px; }}
</style>""", unsafe_allow_html=True)


def kpi(col, label, value, sub="", color=BLUE):
    col.markdown(f"<div class='kpi' style='border-top-color:{color}'><div class='l'>{label}</div><div class='v'>{value}</div>"
                 f"<div class='d'>{sub}</div></div>", unsafe_allow_html=True)


def pill(text, color):
    return f"<span class='pill' style='background:{color}'>{html.escape(str(text))}</span>"


def money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "—"


def style_fig(fig, h=300):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="#fff", plot_bgcolor="#fff",
                      font=dict(family="Roboto, sans-serif", color=INK, size=12),
                      title=dict(text=fig.layout.title.text or "", font=dict(color=NAVY, size=15)),
                      legend=dict(orientation="h", y=-0.22))
    fig.update_xaxes(gridcolor="#EEF2F6"); fig.update_yaxes(gridcolor="#EEF2F6")
    return fig


# ---------------------------------------------------------------- header
now = datetime.now(timezone.utc).strftime("%b %d, %Y · %H:%M UTC")
st.markdown(f"""<div class='ml-top'><img src='data:image/svg+xml;base64,{LOGO}'/>
  <div class='r'><b style='color:{NAVY}'>Summit Valley Credit Union</b> · Consumer Lending<br/>{html.escape(current_underwriter())} · {now}</div></div>
  <div class='ml-band'><div><div class='t'>Lending Intelligence Workbench</div>
  <div class='s'>Speed and trust — AI verifies the documents, the model scores the risk, your underwriters make the call.</div></div>
  <div>{pill('Powered by Databricks · Lakebase · Unity Catalog', TEAL)}</div></div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data access
QUEUE_COLS = """application_id, member_name, product_code, channel, requested_amount, term_months, stated_monthly_income,
                ai_verified_monthly_income, ai_income_variance_pct, epd_probability, risk_band, reason_1, reason_2, reason_3,
                routing_reason, submitted_at, source"""


def load_queue():
    live = f"""SELECT application_id, member_name, product_code, channel, requested_amount::float, term_months, stated_monthly_income::float,
                 ai_verified_monthly_income::float, ai_income_variance_pct::float, epd_probability::float, risk_band, reason_1, reason_2, reason_3,
                 routing_reason, submitted_at, 'LIVE' AS source
               FROM workbench.live_applications WHERE institution_id = %s AND routing <> 'AUTO_APPROVE'"""
    synced = f"""SELECT application_id, member_name, product_code, channel, requested_amount::float, term_months, stated_monthly_income::float,
                 ai_verified_monthly_income::float, ai_income_variance_pct::float, epd_probability::float, risk_band, reason_1, reason_2, reason_3,
                 routing_reason, submitted_ts AS submitted_at, 'DATA CONNECT' AS source
               FROM {QUEUE_TABLE} WHERE institution_id = %s"""
    df = pg(f"""SELECT * FROM ({live} UNION ALL {synced}) u
               WHERE application_id NOT IN (SELECT application_id FROM workbench.underwriting_decisions)
               ORDER BY CASE routing_reason WHEN 'INCOME_MISMATCH' THEN 0 WHEN 'HIGH_RISK' THEN 1 ELSE 2 END, submitted_at DESC""",
            (TENANT, TENANT))
    return df


def app_detail(app_id):
    d = pg(f"SELECT *, 'DATA CONNECT' AS source FROM {QUEUE_TABLE} WHERE application_id = %s AND institution_id = %s", (app_id, TENANT))
    if d is not None and len(d):
        return d.iloc[0].to_dict()
    d = pg("SELECT *, 'LIVE' AS source FROM workbench.live_applications WHERE application_id = %s AND institution_id = %s", (app_id, TENANT))
    return d.iloc[0].to_dict() if d is not None and len(d) else None


def score(features: dict):
    r = ws().api_client.do("POST", f"/serving-endpoints/{ENDPOINT}/invocations", body={"dataframe_records": [features]})
    p = r.get("predictions")
    return p[0] if isinstance(p, list) else {k: v[0] for k, v in p.items()}


def build_features(product, channel, amount, term, income, credit, debt, tenure):
    apr = BASE_APR[product]; r = apr / 12; n = max(term or 36, 1)
    pmt = amount * r / (1 - (1 + r) ** (-n))
    f = {"credit_score": float(credit), "stated_monthly_income": float(income), "monthly_debt_payments": float(debt),
         "dti_stated": round((debt + pmt) / income, 4), "loan_to_income": round(amount / (income * 12), 4),
         "requested_amount": float(amount), "term_months": float(n), "apr": apr, "member_tenure_years": float(tenure)}
    for p in BASE_APR: f[f"product_{p}"] = float(product == p)
    for c in ["DEALER", "ONLINE", "MOBILE", "BRANCH"]: f[f"channel_{c}"] = float(channel == c)
    return {k: f[k] for k in FEATURES}


def path_to_yes_letter(name, product, amount, reasons, stated, verified):
    prompt = (
        "You are a member-services writer at Summit Valley Credit Union. Write a short, warm, plain-language letter (under 170 words) "
        f"to {name} explaining that their {product.lower()} loan application for ${amount:,.0f} was not approved at this time. "
        f"Principal reasons (state them plainly, as required for an adverse action notice): {reasons}. "
        + (f"Their stated monthly income was ${stated:,.0f} but their pay stub supports ${verified:,.0f}. " if verified else "")
        + "Then give a concrete 'path to yes': 2-3 specific actions (e.g. a smaller amount, a co-applicant, updated documents, paying down debt) "
        "and invite them to reapply or call a loan officer. Do not promise approval, do not mention scores or AI. "
        "Close with: 'You have the right to a statement of specific reasons and to a free copy of your credit report under the Equal Credit Opportunity Act and FCRA.' "
        "Sign as 'Summit Valley Credit Union Lending Team'.")
    return q(f"SELECT ai_query('{LLM}', :p) AS letter", {"p": prompt}).iloc[0]["letter"]


def record_decision(rec, decision, approved_amount, conditions, rationale, letter=None):
    band = rec.get("risk_band")
    followed = (decision.startswith("APPROVE") and band != "HIGH") or (decision == "DECLINE" and band == "HIGH")
    mismatch = bool(rec.get("ai_income_variance_pct") is not None and float(rec.get("ai_income_variance_pct") or 0) > 0.20)
    pg("""INSERT INTO workbench.underwriting_decisions (application_id, institution_id, decision, approved_amount, conditions, underwriter,
            model_epd_probability, model_risk_band, followed_model, ai_income_mismatch, rationale, member_letter)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
       (rec["application_id"], TENANT, decision, approved_amount, conditions, current_underwriter(),
        float(rec.get("epd_probability") or 0), band, followed, mismatch, rationale, letter), fetch=False)
    pg("INSERT INTO workbench.audit_log (actor, action, application_id, detail) VALUES (%s,%s,%s,%s)",
       (current_underwriter(), f"DECISION_{decision}", rec["application_id"],
        json.dumps({"risk_band": band, "epd_probability": float(rec.get("epd_probability") or 0), "followed_model": followed})), fetch=False)


# ---------------------------------------------------------------- tabs
t_queue, t_review, t_new, t_out = st.tabs(["📥  Underwriting Queue", "🔎  Application Review", "⚡  New Application (live)", "📈  Outcomes"])

# ---- 1. queue
with t_queue:
    try:
        if st.button("↻ Refresh queue", key="refresh_queue"):
            st.rerun()
        qdf = load_queue()
    except Exception as e:
        qdf = pd.DataFrame(); st.error(f"Could not read the queue from Lakebase: {e}")
    if len(qdf):
        mism = int((qdf.routing_reason == "INCOME_MISMATCH").sum()); high = int((qdf.risk_band == "HIGH").sum())
        c1, c2, c3, c4 = st.columns(4)
        kpi(c1, "Open files for underwriters", len(qdf), "everything else was auto-decided", NAVY)
        kpi(c2, "AI income mismatches", mism, "stated income > 120% of pay stub", RED)
        kpi(c3, "High EPD risk", high, "model risk band HIGH", AMBER)
        kpi(c4, "Requested $ in queue", money(qdf.requested_amount.sum()), "awaiting a decision", TEAL)
        st.write("")
        f1, f2 = st.columns(2)
        rr = f1.multiselect("Routing reason", sorted(qdf.routing_reason.dropna().unique()), placeholder="All")
        rb = f2.multiselect("Risk band", ["HIGH", "MEDIUM", "LOW"], placeholder="All")
        mask = pd.Series(True, index=qdf.index)
        if rr: mask &= qdf.routing_reason.isin(rr)
        if rb: mask &= qdf.risk_band.isin(rb)
        view = qdf[mask].copy()
        for c in ["ai_income_variance_pct", "epd_probability", "requested_amount", "stated_monthly_income", "ai_verified_monthly_income"]:
            view[c] = pd.to_numeric(view[c], errors="coerce")
        view["variance"] = view.ai_income_variance_pct.map(lambda v: "" if pd.isna(v) else f"{v*100:+.0f}%")
        view["EPD %"] = (view.epd_probability * 100).round(2)
        st.dataframe(view[["source", "application_id", "member_name", "product_code", "channel", "requested_amount", "stated_monthly_income",
                           "ai_verified_monthly_income", "variance", "EPD %", "risk_band", "routing_reason", "submitted_at"]],
                     hide_index=True, use_container_width=True,
                     column_config={"requested_amount": st.column_config.NumberColumn("Requested", format="$%d"),
                                    "stated_monthly_income": st.column_config.NumberColumn("Stated income/mo", format="$%d"),
                                    "ai_verified_monthly_income": st.column_config.NumberColumn("AI-verified income/mo", format="$%d")})
        st.markdown("<div class='muted'>Queue served from <b>Lakebase</b> (Postgres): synced from the governed Delta table "
                    "<code>ml_lend_ml.underwriting_queue</code> plus live applications. Decisions are written back to Lakebase and replicated to Delta "
                    "(<code>ml_lend_ops</code>) by Lakebase change data feed.</div>", unsafe_allow_html=True)
    elif not len(qdf):
        st.info("No open files — every application has been decided.")

# ---- 2. review
with t_review:
    try:
        qdf2 = load_queue()
    except Exception as e:
        qdf2 = pd.DataFrame(); st.error(str(e))
    if len(qdf2):
        labels = {f"{r.application_id} · {r.member_name} · {r.product_code} {money(r.requested_amount)} · {r.routing_reason}": r.application_id
                  for r in qdf2.itertuples()}
        pick = st.selectbox("Select a file", list(labels))
        rec = app_detail(labels[pick])
        if rec:
            left, right = st.columns([1.15, 1])
            with left:
                st.markdown(f"<div class='card'><h4>{html.escape(str(rec.get('member_name')))} · {rec['application_id']}</h4>"
                            f"<div class='muted'>{rec.get('product_code')} · {rec.get('channel')} · {money(rec.get('requested_amount'))} over "
                            f"{rec.get('term_months')} months · source: {rec.get('source')}</div>"
                            + (f"<div class='muted'>SSN {rec.get('ssn_last4')} · credit score {rec.get('credit_score')}</div>" if rec.get('ssn_last4') else
                               f"<div class='muted'>credit score {rec.get('credit_score')}</div>") + "</div>", unsafe_allow_html=True)
                stated = float(rec.get("stated_monthly_income") or 0); ver = rec.get("ai_verified_monthly_income")
                ver = float(ver) if ver is not None and not pd.isna(ver) else None
                st.markdown("<div class='card'><h4>Income verification · AI document check</h4>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                kpi(c1, "Stated on application", money(stated), "per month", SLATE)
                kpi(c2, "Verified from pay stub", money(ver) if ver else "—", f"{rec.get('ai_pay_frequency') or ''} · {rec.get('ai_employer_name') or ''}", TEAL)
                var = (stated - ver) / ver if ver else None
                kpi(c3, "Variance", f"{var:+.0%}" if var is not None else "—", "threshold +20%", RED if var and var > 0.2 else GREEN)
                if var is not None and var > 0.2:
                    st.markdown(f"<div class='alert'>⚠ Stated income is {var:.0%} higher than the pay stub supports. "
                                f"Capacity should be re-assessed on {money(ver)}/month.</div>", unsafe_allow_html=True)
                elif ver:
                    st.markdown("<div class='ok'>✓ Stated income is consistent with the pay stub.</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                if rec.get("latest_note"):
                    st.markdown(f"<div class='card'><h4>Latest note {pill(rec.get('latest_note_category') or 'unclassified', BLUE)}</h4>"
                                f"<div>{html.escape(str(rec.get('latest_note')))}</div><div class='muted'>Category assigned by ai_classify in the pipeline</div></div>",
                                unsafe_allow_html=True)
            with right:
                p = float(rec.get("epd_probability") or 0); band = rec.get("risk_band") or "—"
                fig = go.Figure(go.Indicator(mode="gauge+number", value=p * 100, number={"suffix": "%", "valueformat": ".2f"},
                                             title={"text": "Early-payment-default probability"},
                                             gauge={"axis": {"range": [0, 15]}, "bar": {"color": BAND_COLOR.get(band, BLUE)},
                                                    "steps": [{"range": [0, 2.1], "color": "#EEF8EC"}, {"range": [2.1, 5.1], "color": "#FFF4E5"},
                                                              {"range": [5.1, 15], "color": "#FDECEC"}]}))
                st.plotly_chart(style_fig(fig, 230), use_container_width=True)
                st.markdown(f"<div class='card'><h4>Model view {pill(band, BAND_COLOR.get(band, BLUE))}</h4>"
                            f"<div class='muted'>Top reasons (SHAP) · adverse-action ready</div>"
                            f"<ol><li>{html.escape(str(rec.get('reason_1')))}</li><li>{html.escape(str(rec.get('reason_2')))}</li>"
                            f"<li>{html.escape(str(rec.get('reason_3')))}</li></ol>"
                            f"<div class='muted'>Routed to you because: <b>{rec.get('routing_reason')}</b></div></div>", unsafe_allow_html=True)
                with st.form(f"decide_{rec['application_id']}"):
                    decision = st.radio("Decision", ["APPROVE", "APPROVE_WITH_CONDITIONS", "REQUEST_DOCUMENTS", "DECLINE"], horizontal=True)
                    amt = st.number_input("Approved amount", value=float(rec.get("requested_amount") or 0), step=500.0)
                    cond = st.text_input("Conditions", value="")
                    why = st.text_area("Rationale (kept for audit)", value="")
                    go_ = st.form_submit_button("Record decision")
                if go_:
                    letter = None
                    with st.spinner("Recording decision in Lakebase…"):
                        if decision == "DECLINE":
                            reasons = "; ".join(str(rec.get(k)) for k in ["reason_1", "reason_2", "reason_3"] if rec.get(k))
                            if var is not None and var > 0.2:
                                reasons = "Income could not be verified at the stated level; " + reasons
                            letter = path_to_yes_letter(str(rec.get("member_name")), str(rec.get("product_code")),
                                                        float(rec.get("requested_amount") or 0), reasons, stated, ver)
                        record_decision(rec, decision, amt if decision.startswith("APPROVE") else None, cond, why, letter)
                    st.success(f"{decision.replace('_', ' ').title()} recorded for {rec['application_id']} by {current_underwriter()}.")
                    if letter:
                        st.markdown("**Member letter — 'path to yes' (generated with ai_query, stored with the decision)**")
                        st.markdown(f"<div class='letter'>{html.escape(letter)}</div>", unsafe_allow_html=True)
    else:
        st.info("Queue is empty.")

# ---- 3. live new application
with t_new:
    st.markdown("<div class='muted'>A member applies through the dealer / online channel. The same governed AI functions and model used in the "
                "nightly pipeline run here in real time.</div>", unsafe_allow_html=True)
    doc_label = st.selectbox("Pay-stub document uploaded by the member", list(DEMO_DOCS))
    app_key = doc_label.split(" · ")[0]; dflt = DEMO_DEFAULTS[app_key]
    with st.form("new_app"):
        c1, c2, c3, c4 = st.columns(4)
        name = c1.text_input("Member", dflt["name"]); employer = c2.text_input("Employer (stated)", dflt["employer"])
        product = c3.selectbox("Product", list(BASE_APR), index=list(BASE_APR).index(dflt["product"]))
        channel = c4.selectbox("Channel", ["DEALER", "ONLINE", "MOBILE", "BRANCH"])
        c5, c6, c7, c8, c9 = st.columns(5)
        amount = c5.number_input("Requested amount", value=float(dflt["amount"]), step=500.0)
        term = c6.number_input("Term (months)", value=int(dflt["term"]), step=12)
        income = c7.number_input("Stated monthly income", value=float(dflt["income"]), step=100.0)
        credit = c8.number_input("Credit score", value=int(dflt["credit"]), step=1)
        debt = c9.number_input("Monthly debt payments", value=float(dflt["debt"]), step=50.0)
        submitted = st.form_submit_button("Submit application")
    if submitted:
        path = DEMO_DOCS[doc_label]
        assert path in DEMO_DOCS.values() and "'" not in path
        steps = []; t0 = time.time()
        with st.status("Processing application…", expanded=True) as status:
            t = time.time()
            st.write("1 · Parsing pay-stub PDF with `ai_parse_document`…")
            txt = q(f"""SELECT concat_ws('\\n', transform(try_cast(ai_parse_document(content):document:elements AS ARRAY<VARIANT>),
                              e -> try_cast(e:content AS STRING))) AS doc_text
                        FROM read_files('{path}', format => 'binaryFile')""").iloc[0]["doc_text"]
            steps.append(("Parse document (ai_parse_document)", time.time() - t)); t = time.time()
            st.write("2 · Extracting employer, pay frequency and gross pay with `ai_extract`…")
            ex = q("""SELECT ai_extract(:txt, array('employer_name','employee_name','pay_frequency','pay_period_end_date','gross_pay_this_period','year_to_date_gross')) AS f""",
                   {"txt": txt}).iloc[0]["f"]
            ex = json.loads(ex) if isinstance(ex, str) else dict(ex)
            freq = (ex.get("pay_frequency") or "").lower()
            ppm = 26 / 12 if "bi" in freq and "week" in freq else 2.0 if "semi" in freq else 52 / 12 if "week" in freq else 1.0
            gross = float(str(ex.get("gross_pay_this_period") or "0").replace("$", "").replace(",", ""))
            verified = round(gross * ppm, 0); variance = (income - verified) / verified if verified else None
            steps.append(("Extract income (ai_extract)", time.time() - t)); t = time.time()
            st.write("3 · Scoring early-payment-default risk on Model Serving…")
            s = score(build_features(product, channel, amount, term, income, credit, debt, 6.0))
            steps.append(("Score risk (Model Serving · epd_risk_model@champion)", time.time() - t)); t = time.time()
            st.write("4 · Applying credit policy and routing…")
            if variance is not None and variance > 0.20:
                routing, reason = "UNDERWRITER", "INCOME_MISMATCH"
            elif s["risk_band"] == "HIGH":
                routing, reason = "UNDERWRITER", "HIGH_RISK"
            else:
                routing, reason = "AUTO_APPROVE", "AUTO_APPROVE"
            total_ms = int((time.time() - t0) * 1000)
            live_id = f"{app_key}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
            pg("""INSERT INTO workbench.live_applications (application_id, institution_id, member_name, product_code, channel, requested_amount,
                    term_months, stated_monthly_income, credit_score, monthly_debt_payments, doc_path, ai_verified_monthly_income, ai_employer_name,
                    ai_pay_frequency, ai_income_variance_pct, epd_probability, risk_band, reason_1, reason_2, reason_3, routing, routing_reason, processing_ms)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
               (live_id, TENANT, name, product, channel, amount, int(term), income, int(credit), debt, path, verified, ex.get("employer_name"),
                ex.get("pay_frequency"), round(variance, 3) if variance is not None else None, float(s["epd_probability"]), s["risk_band"],
                s["reason_1"], s["reason_2"], s["reason_3"], routing, reason, total_ms), fetch=False)
            steps.append(("Route + write to Lakebase", time.time() - t))
            status.update(label=f"Decision routed in {total_ms/1000:.1f} seconds", state="complete")
        st.session_state["live_result"] = dict(steps=steps, total_ms=total_ms, routing=routing, reason=reason, s=dict(s), income=income,
                                               verified=verified, ex=dict(ex), variance=variance, live_id=live_id)
        st.rerun()   # re-render so the Underwriting Queue tab immediately shows the new file
    if "live_result" in st.session_state:
        R = st.session_state["live_result"]
        steps, total_ms, routing, reason, s = R["steps"], R["total_ms"], R["routing"], R["reason"], R["s"]
        income, verified, ex, variance, live_id = R["income"], R["verified"], R["ex"], R["variance"], R["live_id"]
        a, b = st.columns([1, 1.2])
        with a:
            st.markdown("<div class='card'><h4>Timeline</h4>" + "".join(f"<div class='step'><span>{n}</span><b>{d:.1f}s</b></div>" for n, d in steps)
                        + f"<div class='step'><span><b>Total</b></span><b>{total_ms/1000:.1f}s</b></div>"
                        + "<div class='muted' style='margin-top:6px'>Legacy median time to decision for a manual file: ~17 hours.</div></div>",
                        unsafe_allow_html=True)
        with b:
            st.markdown(f"<div class='card'><h4>Result {pill(routing.replace('_', ' '), GREEN if routing == 'AUTO_APPROVE' else RED)} "
                        f"{pill(s['risk_band'], BAND_COLOR.get(s['risk_band'], BLUE))}</h4>"
                        f"<div>Stated income <b>{money(income)}</b>/mo · pay stub supports <b>{money(verified)}</b>/mo "
                        f"({ex.get('pay_frequency')}, {ex.get('employer_name')}) · variance <b>{(variance or 0):+.0%}</b></div>"
                        f"<div>EPD probability <b>{float(s['epd_probability']):.2%}</b> — {s['reason_1']}; {s['reason_2']}; {s['reason_3']}</div></div>",
                        unsafe_allow_html=True)
            if routing == "AUTO_APPROVE":
                st.markdown("<div class='ok'>✓ Auto-approved in seconds — the member hears 'yes' while still at the dealership.</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='alert'>Routed to an underwriter ({reason.replace('_', ' ').lower()}). It is now at the top of the queue "
                            f"as <b>{live_id}</b>.</div>", unsafe_allow_html=True)

# ---- 4. outcomes
with t_out:
    st.markdown("<div class='muted'>Read from Unity Catalog metric views. This app runs as the Summit Valley identity, so ABAC tenant isolation "
                "limits every number to Summit Valley's own members.</div>", unsafe_allow_html=True)
    try:
        fun = q(f"""SELECT credit_union, period, MEASURE(applications) apps, MEASURE(pull_through_rate) pull_through,
                       MEASURE(funded_amount) funded, MEASURE(withdrawal_rate) withdrawn
                    FROM {CAT}.ml_lend_semantic.mv_loan_funnel GROUP BY ALL""")
        spd = q(f"""SELECT credit_union, period, MEASURE(auto_decision_rate) auto_rate, MEASURE(median_decision_minutes) med_min,
                       MEASURE(decided_within_24h_rate) within24
                    FROM {CAT}.ml_lend_semantic.mv_decision_speed GROUP BY ALL""")
        rsk = q(f"""SELECT credit_union, period, MEASURE(epd_rate) epd FROM {CAT}.ml_lend_semantic.mv_portfolio_risk WHERE is_seasoned GROUP BY ALL""")
        m = fun.merge(spd, on=["credit_union", "period"]).merge(rsk, on=["credit_union", "period"], how="left")
        cus = sorted(m.credit_union.unique())
        cu = st.selectbox("Credit union", cus, index=cus.index("Summit Valley Credit Union") if "Summit Valley Credit Union" in cus else 0)
        mm = m[m.credit_union == cu].set_index("period")
        if {"BEFORE", "AFTER"} <= set(mm.index):
            B, A = mm.loc["BEFORE"], mm.loc["AFTER"]
            c = st.columns(5)
            kpi(c[0], "Auto-decision rate", f"{A.auto_rate:.0%}", f"before {B.auto_rate:.0%}", GREEN)
            kpi(c[1], "Median time to decision", f"{A.med_min:,.0f} min", f"before {B.med_min/60:,.1f} h", BLUE)
            kpi(c[2], "Pull-through", f"{A.pull_through:.1%}", f"before {B.pull_through:.1%} ({(A.pull_through-B.pull_through)*100:+.1f} pts)", TEAL)
            kpi(c[3], "Early payment default", f"{A.epd:.2%}" if pd.notna(A.epd) else "—",
                f"before {B.epd:.2%}" if pd.notna(B.epd) else "", AMBER)
            kpi(c[4], "Funded volume (12 mo)", money(A.funded), f"before {money(B.funded)}", NAVY)
        st.dataframe(m.sort_values(["credit_union", "period"], ascending=[True, False]), hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"Outcome metrics unavailable: {e}")
    try:
        dd = pg("""SELECT decision, count(*) n, sum(CASE WHEN followed_model THEN 1 ELSE 0 END) followed_model,
                          sum(CASE WHEN member_letter IS NOT NULL THEN 1 ELSE 0 END) letters
                   FROM workbench.underwriting_decisions WHERE institution_id = %s AND decided_at::date = current_date GROUP BY 1""", (TENANT,))
        st.markdown("<div class='card'><h4>Decisions made today in the Workbench (Lakebase)</h4></div>", unsafe_allow_html=True)
        st.dataframe(dd, hide_index=True, use_container_width=True) if dd is not None and len(dd) else st.caption("No decisions yet today.")
    except Exception as e:
        st.caption(f"Lakebase decisions unavailable: {e}")

st.markdown("<div class='ml-foot'>Synthetic data for demonstration only · MeridianLink × Databricks · Lending Intelligence</div>", unsafe_allow_html=True)
