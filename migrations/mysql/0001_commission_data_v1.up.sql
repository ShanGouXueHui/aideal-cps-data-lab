-- Migration 0001: commission data V1
-- Apply only after HZ23 observation acceptance and an explicit backup/review gate.

CREATE TABLE IF NOT EXISTS commission_products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  jd_sku_id VARCHAR(64) NOT NULL,
  title VARCHAR(512) NOT NULL,
  description TEXT NULL,
  item_url VARCHAR(500) NULL,
  promotion_url VARCHAR(500) NOT NULL,
  short_url VARCHAR(500) NULL,
  long_url TEXT NULL,
  qr_url TEXT NULL,
  jd_command TEXT NULL,
  image_url VARCHAR(1000) NOT NULL,
  category_name VARCHAR(128) NULL,
  shop_name VARCHAR(255) NULL,
  price DECIMAL(12,2) NOT NULL,
  coupon_price DECIMAL(12,2) NULL,
  commission_rate DECIMAL(8,4) NULL,
  estimated_commission DECIMAL(12,2) NULL,
  sales_volume BIGINT NULL,
  coupon_info VARCHAR(512) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'quarantined',
  is_published TINYINT(1) NOT NULL DEFAULT 0,
  missing_rounds INT UNSIGNED NOT NULL DEFAULT 0,
  source_page_no SMALLINT UNSIGNED NULL,
  source_round_id VARCHAR(64) NULL,
  source_run_id VARCHAR(64) NULL,
  source_payload_hash CHAR(64) NOT NULL,
  catalog_change_count INT UNSIGNED NOT NULL DEFAULT 0,
  link_created_at DATETIME(6) NULL,
  link_expire_at DATETIME(6) NULL,
  refresh_due_at DATETIME(6) NULL,
  first_seen_at DATETIME(6) NOT NULL,
  last_checked_at DATETIME(6) NOT NULL,
  last_seen_at DATETIME(6) NOT NULL,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_commission_products_sku (jd_sku_id),
  KEY ix_commission_products_publish_status (is_published, status),
  KEY ix_commission_products_updated (updated_at, id),
  KEY ix_commission_products_refresh_due (refresh_due_at),
  KEY ix_commission_products_round (source_round_id),
  KEY ix_commission_products_last_seen (last_seen_at),
  CONSTRAINT ck_commission_products_status CHECK (status IN ('active', 'inactive', 'quarantined')),
  CONSTRAINT ck_commission_products_page CHECK (source_page_no IS NULL OR source_page_no BETWEEN 1 AND 67),
  CONSTRAINT ck_commission_products_nonnegative CHECK (
    price >= 0
    AND (coupon_price IS NULL OR coupon_price >= 0)
    AND (commission_rate IS NULL OR commission_rate >= 0)
    AND (estimated_commission IS NULL OR estimated_commission >= 0)
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS commission_refresh_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  round_id VARCHAR(64) NOT NULL,
  run_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  page_start SMALLINT UNSIGNED NULL,
  page_end SMALLINT UNSIGNED NULL,
  completed_pages JSON NULL,
  unfinished_pages JSON NULL,
  scanned_count INT UNSIGNED NOT NULL DEFAULT 0,
  new_count INT UNSIGNED NOT NULL DEFAULT 0,
  changed_count INT UNSIGNED NOT NULL DEFAULT 0,
  unchanged_count INT UNSIGNED NOT NULL DEFAULT 0,
  link_ok_count INT UNSIGNED NOT NULL DEFAULT 0,
  link_fail_count INT UNSIGNED NOT NULL DEFAULT 0,
  risk_signals JSON NULL,
  stop_reason VARCHAR(255) NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  report_path VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_commission_refresh_runs_round (round_id),
  KEY ix_commission_refresh_runs_status_started (status, started_at),
  CONSTRAINT ck_commission_refresh_runs_type CHECK (run_type IN ('probe', 'full', 'backfill', 'retry', 'publish')),
  CONSTRAINT ck_commission_refresh_runs_status CHECK (status IN ('running', 'completed', 'stopped', 'failed'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS commission_product_history (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  jd_sku_id VARCHAR(64) NOT NULL,
  round_id VARCHAR(64) NOT NULL,
  change_type VARCHAR(32) NOT NULL,
  before_payload JSON NULL,
  after_payload JSON NOT NULL,
  before_hash CHAR(64) NULL,
  after_hash CHAR(64) NOT NULL,
  changed_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  KEY ix_commission_product_history_sku_time (jd_sku_id, changed_at),
  KEY ix_commission_product_history_round (round_id),
  CONSTRAINT ck_commission_product_history_type CHECK (change_type IN ('insert', 'update', 'status', 'link'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS commission_publish_versions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  publish_version BIGINT UNSIGNED NOT NULL,
  round_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  row_count INT UNSIGNED NOT NULL,
  data_sha256 CHAR(64) NOT NULL,
  schema_version VARCHAR(64) NOT NULL,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_commission_publish_version (publish_version),
  UNIQUE KEY uq_commission_publish_round (round_id),
  KEY ix_commission_publish_status_version (status, publish_version),
  CONSTRAINT ck_commission_publish_status CHECK (status IN ('candidate', 'published', 'revoked'))
) ENGINE=InnoDB;

DROP VIEW IF EXISTS v_published_commission_products;
CREATE VIEW v_published_commission_products AS
SELECT
  jd_sku_id,
  title,
  description,
  item_url,
  promotion_url,
  short_url,
  image_url,
  category_name,
  shop_name,
  price,
  coupon_price,
  commission_rate,
  estimated_commission,
  sales_volume,
  coupon_info,
  status,
  source_page_no,
  source_round_id,
  source_payload_hash,
  catalog_change_count,
  link_created_at,
  link_expire_at,
  refresh_due_at,
  last_checked_at,
  last_seen_at,
  published_at,
  updated_at
FROM commission_products
WHERE is_published = 1
  AND status = 'active';
