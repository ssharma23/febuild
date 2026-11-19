CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_landing COMMENT 'MeridianLink Data Connect landing zone: raw daily extract files and application documents (synthetic)';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_bronze COMMENT 'Bronze: raw Data Connect extracts ingested by Lakeflow (Auto Loader), append-only, schema-on-read';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_silver COMMENT 'Silver: validated, deduplicated, conformed lending entities with DQ expectations and AI-enriched documents';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_gold COMMENT 'Gold: consumer lending star schema and outcome KPIs for MeridianLink credit-union customers';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_ml COMMENT 'ML: feature tables, early-payment-default model, scores and reason codes';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_gov COMMENT 'Governance: ABAC/row-filter functions, entitlement mappings, DQ results';
CREATE SCHEMA IF NOT EXISTS demo_dnb_catalog.ml_lend_semantic COMMENT 'Semantic layer: metric views powering Genie, AI/BI dashboards and the Consumer Lending ontology';
CREATE VOLUME IF NOT EXISTS demo_dnb_catalog.ml_lend_landing.dataconnect COMMENT 'Daily MeridianLink Data Connect extract drops (CSV/JSON) per entity';
CREATE VOLUME IF NOT EXISTS demo_dnb_catalog.ml_lend_landing.documents COMMENT 'Member-submitted application documents (pay stubs, PDFs)'
