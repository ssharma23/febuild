# MeridianLink · "Speed AND Trust": storyline (v3, final numbers from the build)
SA assessment · audience: SA business + technical leadership · slot 15–20 min (≈5 min deck, ≈11 min demo, Q&A)

## One-line story
MeridianLink tells lenders *"you don't have to choose between speed and trust."* Today every credit union does choose.
We built the governed platform that removes the trade-off, proved it with a pilot-vs-control experiment, and priced it at **≈ $3.6M a year per 40K-application credit union**. And because tenant isolation is a *policy*, MeridianLink can ship it to every credit union it serves.

## Characters
- **Priya**, VP Lending, Summit Valley Credit Union (fictional MeridianLink customer): losing members and dealer deals to faster lenders.
- **Marcus**, senior underwriter: 140 files in the queue, checks pay stubs by hand.
- **MeridianLink data platform team**: wants to productize "Lending Intelligence" for all credit unions without a stack per tenant.

## The tension (slide 2), all from the data
| Speed | Trust |
|---|---|
| 73% of approved loans fund when decided in under 1 h; **57%** when it takes more than 24 h | **1 in 15** applicants overstate income by 25–75% |
| Legacy rules auto-decide 31%; everyone else waits a median **17 h** | Manual review catches only **3 in 10** of them, and they show up later as early defaults |

## The resolution: six steps on one platform (demo flow)
| Step | Business line | Proof in the build |
|---|---|---|
| 1 · Land | "Data Connect files arrive; nobody writes ingestion code." | Lakeflow file ingestion (Auto Loader) → bronze streaming tables |
| 2 · Trust | "Bad records never reach an underwriter." | Declarative pipeline; expectations drop / warn / fail; 400 quarantined; AUTO CDC SCD1/SCD2 |
| 3 · Protect | "Summit Valley can't see Harbor Point; analysts never see SSNs." | Data Classification auto-tags → ABAC masks + tenant row filter (proven live); RBAC on layers |
| 4 · Decide | "AI reads the pay stub so Marcus doesn't have to." | `ai_parse_document` + `ai_extract`: 100% within 2% of truth; 479/479 misstatements flagged, 2 false positives. EPD model (LightGBM + SHAP) on Model Serving |
| 5 · Act | "The queue only holds files that need a human." | Workbench app on Lakebase: live new application → routed in seconds → decision + "path to yes" letter written back |
| 6 · Explain | "Priya asks why, in English." | 3 metric views → Genie, AI/BI dashboard, Databricks One; Ontology domain spec ready |

## The proof (slide 5): difference-in-differences, pilot vs control
| Metric | Pilot before → after | Control before → after | Net lift |
|---|---|---|---|
| Auto-decision rate | 31.3% → 57.6% | 31.2% → 31.5% | **+26 pts** |
| Median time to decision | 17.1 h → 8 min | 17.1 h → 17.0 h | **−17 h** |
| Pull-through | 67.1% → 71.5% | 67.9% → 66.8% | **+5.5 pts** |
| Early payment default | 2.74% → 1.89% | 2.89% → 3.20% | **−1.2 pts** |

## The value (slide 6), reference credit union of 40K applications/yr
Avoided early-default losses **$1.71M** · more funded loans **$0.85M** · underwriter capacity **$0.72M** (~15K h) · recovered declines **$0.35M** → **≈ $3.63M**.
**Twist:** trust pays more than speed. Conservative: first-year NII only; capacity is not presented as layoffs; halve the default effect → still ≈ $2.8M.
Source of truth: `ml_lend_semantic.v_value_bridge` × `ml_lend_gold.roi_assumptions`.

## The ask (slide 7)
30-60-90 with one design-partner credit union, the same experiment design. Tenant #2 = an entitlement row, not a new stack.

## Honesty guardrails (say these out loud)
- 100% synthetic data modeled on the Data Connect schema; no customer data was used.
- Dollar values = measured lifts × documented assumptions.
- Persona isolation uses an entitlement table because FEVM has no account groups; production uses IdP-synced groups with the same policies.
- Ontology domain not created only because of the FEVM tag-policy quota; content and metric views exist.
