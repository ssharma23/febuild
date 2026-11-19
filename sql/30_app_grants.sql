GRANT USE CATALOG ON CATALOG demo_dnb_catalog TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT USE SCHEMA, SELECT ON SCHEMA demo_dnb_catalog.ml_lend_gold TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT USE SCHEMA, SELECT ON SCHEMA demo_dnb_catalog.ml_lend_ml TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT USE SCHEMA, SELECT ON SCHEMA demo_dnb_catalog.ml_lend_semantic TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT USE SCHEMA ON SCHEMA demo_dnb_catalog.ml_lend_landing TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT READ VOLUME ON VOLUME demo_dnb_catalog.ml_lend_landing.documents TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT USE SCHEMA, EXECUTE ON SCHEMA demo_dnb_catalog.ml_lend_gov TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
GRANT SELECT ON TABLE demo_dnb_catalog.ml_lend_gov.tenant_entitlements TO `85522c3a-a513-4cc7-a183-a8cd4c40a07e`;
MERGE INTO demo_dnb_catalog.ml_lend_gov.tenant_entitlements t
USING (SELECT '85522c3a-a513-4cc7-a183-a8cd4c40a07e' principal, 'Summit Valley CU Underwriter (Workbench app)' persona, 'CU-SVCU' institution_id, 'LAST4' pii_access) s
ON t.principal = s.principal
WHEN MATCHED THEN UPDATE SET persona = s.persona, institution_id = s.institution_id, pii_access = s.pii_access
WHEN NOT MATCHED THEN INSERT *
