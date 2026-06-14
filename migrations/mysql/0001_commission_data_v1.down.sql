-- Rollback migration 0001.
-- Execute only during an explicit rollback window after backup verification.

DROP VIEW IF EXISTS v_published_commission_products;
DROP TABLE IF EXISTS commission_publish_versions;
DROP TABLE IF EXISTS commission_product_history;
DROP TABLE IF EXISTS commission_refresh_runs;
DROP TABLE IF EXISTS commission_products;
