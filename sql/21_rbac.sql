-- RBAC (coarse-grained): who can touch which layer. ABAC (fine-grained) then decides which rows/columns.
--   Platform team (schema owner)    : bronze, silver, gold, ml, gov   (no grants needed beyond ownership)
--   Business consumers (account users): semantic layer only (metric views) + gold read for Genie/dashboard joins
--   Workbench app service principal  : granted separately (gold, ml, semantic read; documents volume read)
GRANT USE SCHEMA ON SCHEMA demo_dnb_catalog.ml_lend_semantic TO `account users`;
GRANT SELECT ON SCHEMA demo_dnb_catalog.ml_lend_semantic TO `account users`;
GRANT USE SCHEMA ON SCHEMA demo_dnb_catalog.ml_lend_gold TO `account users`;
GRANT SELECT ON SCHEMA demo_dnb_catalog.ml_lend_gold TO `account users`;
GRANT USE SCHEMA ON SCHEMA demo_dnb_catalog.ml_lend_gov TO `account users`;
GRANT EXECUTE ON SCHEMA demo_dnb_catalog.ml_lend_gov TO `account users`
