# Submission answers

## What is the business challenge you are solving?

MeridianLink tells the credit unions and banks it serves "you don't have to choose between speed and trust." In practice, credit unions on legacy decisioning still choose every day.

**Speed:** a legacy rules engine auto-decides only about 31% of consumer loan applications. Everyone else waits a median of 17 hours for an underwriter. Members and auto dealers don't wait. When a decision comes back within an hour, 73% of approved loans fund; past 24 hours, only 57% do, because the member or the dealer has gone to whoever said yes first.

**Trust:** about 1 in 15 applicants overstate their income. Underwriters checking pay stubs by hand catch roughly 3 in 10 of them. The rest are booked, and they show up months later as early payment defaults. Automating faster with today's rules makes that worse, and slowing down to check more loses the deal.

For MeridianLink there's a third problem. Every credit union wants this capability, but building a separate data stack per customer doesn't scale. They need one governed platform where each credit union sees only its own members.

**Goal:** decide most loans in minutes, catch income misstatement before booking, and deliver it as a multi-tenant product. Then prove the impact with a controlled comparison, not anecdotes.

## How does your Databricks solution address this challenge?

"Lending Intelligence" runs end to end on one Databricks platform, organized as six steps:

1. **Land.** MeridianLink Data Connect extracts (applications, members, payments, notes) and member pay-stub PDFs land in a Unity Catalog volume. Lakeflow file ingestion (Auto Loader) picks them up incrementally, with no custom ingestion code.
2. **Trust.** A Lakeflow Spark Declarative Pipeline builds a bronze → silver → gold medallion. Data-quality expectations drop or fail bad records, and 400 records land in quarantine tables with the rule they broke. AUTO CDC collapses re-sent records (SCD1) and keeps member history (SCD2).
3. **Protect.** Unity Catalog Data Classification auto-tags PII. ABAC policies attached to those tags mask SSN, date of birth and contact details. A row-filter policy isolates each credit union's data, and it flows through to metric views, Genie, dashboards and the app. RBAC limits business users to the gold and semantic layers.
4. **Decide.** AI Functions run inside the pipeline. `ai_parse_document` and `ai_extract` read every pay stub and reconcile verified against stated income: on 1,500 test documents, extraction was within 2% of true income every time, and all 479 misstatements were flagged with 2 false positives. `ai_classify` tags member notes (89% agreement with human labels), and `ai_query` drafts a compliant "path to yes" letter for every decline. An early-payment-default model (LightGBM with SHAP reason codes, tracked in MLflow, registered in Unity Catalog, served on Model Serving) scores every application. Its reason codes double as adverse-action reasons.
5. **Act.** A Databricks App on Lakebase Postgres, the Lending Intelligence Workbench, gives underwriters a queue of only the files that need a human, with the AI evidence alongside. A new application is parsed, scored and routed in about 30 seconds. Decisions and letters are written to Lakebase and synced back to Delta.
6. **Explain.** Three Unity Catalog metric views (loan funnel, decision speed, portfolio risk) power an AI/BI dashboard, a Genie space and Databricks One for business users. They also form the Consumer Lending ontology.

**Measured outcome.** Two credit unions went live and two stayed on the legacy process as a control; all figures below compare the two (difference-in-differences):

| Metric | Before | After | Net effect vs control |
|---|---|---|---|
| Auto-decision rate | 31% | 58% | — |
| Median time to decision | 17 hours | 8 minutes | — |
| Pull-through (approved loans that fund) | — | — | +5.5 points |
| Early payment default rate | — | — | −1.2 points |

**Value.** About **$3.6M a year for a 40,000-application credit union**:

| Lever | Annual value |
|---|---|
| Avoided early-default losses | $1.71M |
| Extra funded loans | $0.85M |
| Underwriter capacity | $0.72M |
| Declines turned into funded loans | $0.35M |

Every dollar traces to a governed SQL view of measured lift multiplied by a documented assumption. Because tenant isolation is a policy rather than separate infrastructure, onboarding the next credit union means adding an entitlement row, not standing up a new stack.

## What AI tools did you use, and what was your workflow? What decisions and trade-offs did you have to make for your build?

**AI tools**

| Tool | What I used it for |
|---|---|
| Claude Code, with Databricks, Google Workspace and Chrome DevTools integrations | Coding partner: framing the story, generating the synthetic data, writing pipeline/ML/app code, deploying through the Databricks CLI and APIs, building the deck. A second Claude Code agent worked in parallel on the model, serving, Lakebase and app while I built governance, Genie and the dashboard. |
| Databricks AI Functions | `ai_parse_document`, `ai_extract`, `ai_classify`, and `ai_query` with Claude Haiku 5.5, inside the pipeline and the app |
| Databricks Genie and metric views | Natural-language analytics on certified metrics |
| MLflow + Model Serving | Training, registering and serving the risk model |

**Workflow**

1. **Story first.** I anchored on MeridianLink's own promise ("speed and trust") and defined the outcome metrics and the pilot-vs-control experiment before writing any code.
2. **Data designed for proof.** Synthetic data mirroring the Data Connect schema. No customer data was used. The data has realistic mechanics: the 24-hour funding cliff, income misstatement that drives early defaults, and a control group.
3. **Build in layers, validate each one** against hidden ground truth: AI extraction accuracy, note-classification accuracy, model AUC on a time-based split, and a live test of masking and row isolation by switching personas.
4. **Semantic layer, then consumption.** Metric views first, then Genie (tested on the demo questions), the dashboard, the app and the deck. Every number in the deck is reproducible from SQL.

**Decisions and trade-offs**

| Decision | Trade-off |
|---|---|
| **File-based ingestion** (Data Connect → Auto Loader) instead of standing up a source database | Mirrors how MeridianLink actually delivers data and needs no extra infrastructure. A managed SQL Server CDC connector is the drop-in alternative. |
| **Synthetic data with a built-in control group** | The numbers aren't real customer results. In return they're safe to show and causally defensible, and the deck labels them as synthetic. |
| **Tuned for realism over a flashier story** | My first data version produced an implausible pull-through lift (+12 points) and a weak model (AUC 0.61), so I retuned the generator. The model now has AUC 0.69, which is realistic for bureau and DTI features alone. I chose an honest model and framed AI income verification as the missing signal rather than inflating accuracy. |
| **ABAC on classification tags, plus an entitlement table for tenant isolation** | The sandbox had no account groups and was at its tag-policy limit. Policies attach to Data Classification's system tags, so new PII is protected automatically. Personas map through an entitlement table, and production would swap in IdP-synced groups with the same policies. |
| **LightGBM + SHAP instead of a black-box or rules model** | Slightly more engineering, but every decline has explainable principal reasons for ECOA/Reg B adverse-action notices. I used LightGBM's built-in SHAP so the serving environment stays lean. |
| **AI Functions inside a streaming pipeline** | Each document is parsed once, which keeps cost predictable. Note classification is limited to a recent window to bound token spend. The live app path runs the same functions synchronously: about 30 seconds per application, versus a 17-hour baseline. |
| **Lakebase for the Workbench** instead of writing to Delta from the app | Low-latency OLTP for underwriter actions, with the queue synced from Delta. For the return path, Lakebase's change-data-feed (Beta) is configured, and I added an explicit sync job as the reliable route back to Unity Catalog. |
| **Conservative value model** | First-year interest only, underwriter time counted as capacity rather than headcount cuts, assumptions published in a table, and a sensitivity check: halving the default effect still gives about $2.8M. |
| **Genie Ontology domain** | The domain object couldn't be created because the sandbox was at its tag-policy limit. The three metric views and both pages are built and documented, ready to create in the UI. |

## What are the business outcomes and impact?

Compared with a control group (difference-in-differences: two pilot credit unions vs two on the legacy process):
- **Speed:** auto-decisions rose from 31% to 58%, and median time to decision fell from 17 hours to 8 minutes.
- **Growth:** pull-through rose 5.5 points, about 1,900 more funded loans a year.
- **Risk:** early payment defaults fell 1.2 points. AI caught 100% of inflated incomes on the test documents; manual review catches about 30%.
- **Productivity:** manual reviews fell from 69% to 42% of applications, freeing about 15K underwriter hours a year.
- **Value:** about **$3.6M a year per 40K-application credit union**: $1.71M avoided early-default losses, $0.85M extra funded loans, $0.72M underwriter capacity and $0.35M from declines turned into funded loans, using conservative, published assumptions.
- **Strategic:** MeridianLink can productize this for every credit union it serves. Tenant isolation is a policy, so a new credit union is an entitlement row, not a new stack.

*Synthetic data; every figure is reproducible in SQL and Genie.*
