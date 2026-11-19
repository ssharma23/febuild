-- PII tags on the gold member dimension (same system tags Data Classification applies; scan also runs on bronze/silver/gold)
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN ssn SET TAGS ('class.us_ssn');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN date_of_birth SET TAGS ('class.date_of_birth');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN email SET TAGS ('class.email_address');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN phone SET TAGS ('class.phone_number');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN street_address SET TAGS ('class.street_address');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN first_name SET TAGS ('class.name');
ALTER MATERIALIZED VIEW demo_dnb_catalog.ml_lend_gold.dim_member ALTER COLUMN last_name SET TAGS ('class.name')
