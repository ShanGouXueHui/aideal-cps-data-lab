# AIdeal CPS Product Feed Contract V1

Status: authoritative producer contract

Producer repository: `ShanGouXueHui/aideal-cps-data-lab`

Consumer repository: `ShanGouXueHui/aideal-cps`

## 1. Fixed topology and ownership

### Producer

- Server: Hangzhou data-lab server
- SSH endpoint: `cpsdata@121.41.111.36`
- Repository: `/home/cpsdata/projects/aideal-cps-data-lab`
- Responsibility: JD page authorization, collection, cleaning, promotion-link generation, refresh, quality gates, immutable feed publication
- Must never expose browser profiles, cookies, `.secrets/`, raw HTML/HAR, Playwright runtime, or JD account material to the consumer

### Consumer

- Server: Hangzhou AIdeal CPS production server
- SSH endpoint: `deploy@8.136.28.6`
- Repository: `/home/deploy/projects/aideal-cps`
- MySQL database name: `aideal_cps`
- Database connectivity remains local to the consumer server through `DATABASE_URL`; database credentials must never be stored in GitHub
- Responsibility: pull a published snapshot, validate it, import it transactionally into the consumer database, and serve it through the existing product and promotion APIs

## 2. Transport decision

V1 uses **pull-based rsync over SSH** from the AIdeal CPS server to the data-lab server.

Do not use a long-lived SSH tunnel and do not query the data-lab database remotely.

Reasons:

1. The feed refreshes every 3-5 days and does not require online remote queries.
2. AIdeal CPS must continue serving its local database if data-lab is temporarily unavailable.
3. Pull-based immutable files give checksum validation, replay, rollback, and auditability.
4. The data-lab browser/account boundary remains isolated from production.

Security requirements:

- Use a dedicated SSH key owned by `deploy`.
- The data-lab server must allow that key only from `8.136.28.6/32`.
- Restrict the key to read-only rsync of the export directory, preferably with `rrsync -ro`.
- Disable port forwarding, agent forwarding, X11 forwarding, and PTY for the feed key.
- Pin the data-lab SSH host key in `/home/deploy/.ssh/known_hosts`.
- Do not store the private key or passwords in either repository.

Producer export directory:

```text
/home/cpsdata/projects/aideal-cps-data-lab/data/export/
```

Consumer landing directory:

```text
/home/deploy/projects/aideal-cps/var/data/data-lab/
├── incoming/
├── current/
├── archive/
└── rejected/
```

## 3. Publication files

### Observation-only files

```text
aideal_cps_products_commercial_candidate_latest.jsonl
aideal_cps_products_commercial_candidate_manifest.json
```

The candidate manifest always has:

```json
"commercial_enabled": false
```

AIdeal CPS may download and dry-run candidate files, but must not expose them to end users.

### Promoted commercial files

After the 48-72 hour observation gate passes, data-lab publishes:

```text
aideal_cps_products_commercial_latest.jsonl
aideal_cps_products_commercial_manifest.json
```

AIdeal CPS imports only when all gates are true:

```text
schema_version = aideal-cps-product-feed-manifest/v1
feed_schema_version = aideal-cps-product-feed/v1
commercial_enabled = true
observation_ready = true
round_complete = true
duplicate_sku_count = 0
row_count > 0
```

## 4. Atomic transfer protocol

The consumer must use this order:

1. Pull the manifest to a temporary filename.
2. Validate schema versions and commercial gates.
3. Pull the JSONL file named by `data_file` to a temporary filename.
4. Calculate SHA-256 and compare it with `data_sha256`.
5. Count non-empty JSONL rows and compare with `row_count`.
6. Validate every row against `aideal-cps-product-feed-v1.schema.json`.
7. Atomically rename the two temporary files into `current/`.
8. Start a database import run.
9. Move accepted source files to `archive/<round_id>/`; move invalid files to `rejected/<timestamp>/`.

The consumer must never import a partially transferred file.

## 5. Manifest fields

| Field | Type | Required | Meaning |
|---|---:|---:|---|
| `schema_version` | string | yes | `aideal-cps-product-feed-manifest/v1` |
| `feed_schema_version` | string | yes | `aideal-cps-product-feed/v1` |
| `feed_status` | string | yes | `candidate` or `commercial` |
| `generated_at` | ISO-8601 string | yes | producer publication time |
| `round_id` | string | yes | HZ23 completed refresh round |
| `data_file` | string | yes | JSONL basename in the same export directory |
| `data_sha256` | 64-char string | yes | SHA-256 of exact JSONL bytes |
| `row_count` | integer | yes | non-empty JSONL row count |
| `trusted_dedup_sku_count` | integer | yes | deduplicated trusted link records before feed eligibility filters |
| `catalog_index_sku_count` | integer | yes | HZ23 catalog index size |
| `round_seen_sku_count` | integer | yes | unique SKUs seen in the completed 1-67 round |
| `eligible_sku_count` | integer | yes | records written to JSONL; must equal `row_count` |
| `rejected` | object | yes | counts rejected by reason |
| `duplicate_sku_count` | integer | yes | must be zero |
| `round_complete` | boolean | yes | all target pages completed |
| `round_total_ok` | integer/null | yes | new promotion links created in the round |
| `round_total_fail` | integer/null | yes | new-link attempts that failed in the round |
| `observation_ready` | boolean | yes | producer quality gate result |
| `commercial_enabled` | boolean | yes | explicit consumer enable switch |

## 6. Product feed row fields

The machine-readable schema is `docs/contracts/aideal-cps-product-feed-v1.schema.json`.

### Required business fields

| Feed field | Type | Consumer mapping |
|---|---|---|
| `schema_version` | string | validate only |
| `source` | string | `products.source` |
| `sku` | digit string | `products.jd_sku_id`; unique upsert key |
| `title` | string | `products.title` |
| `item_url` | URL string | `products.item_url` |
| `promotion_url` | URL string | `products.promotion_url`; also copy to legacy `products.product_url` during compatibility period |
| `image_url` | URL string | `products.image_url` |
| `price` | decimal string/number | `products.price`, parse through `Decimal` |
| `status` | string | `products.status` |
| `source_round_id` | string | `products.source_round_id` |
| `source_updated_at` | ISO-8601 string | `products.source_updated_at` |
| `source_payload_hash` | SHA-256 string | `products.source_payload_hash` |

### Optional fields

| Feed field | Consumer mapping |
|---|---|
| `description` | `products.description` |
| `short_url` | alias of `promotion_url`; retained for source compatibility |
| `long_url` | optional audit field |
| `qr_url` | optional audit field |
| `jd_command` | optional audit field |
| `category_name` | `products.category_name` |
| `shop_name` | `products.shop_name` |
| `coupon_price` | `products.coupon_price` |
| `commission_rate` | `products.commission_rate`; remove trailing `%` before parsing |
| `estimated_commission` | `products.estimated_commission` |
| `sales_volume` | `products.sales_volume` |
| `coupon_info` | `products.coupon_info` |
| `link_created_at` | `products.promotion_link_created_at` |
| `link_expire_at` | `products.promotion_link_expire_at` |
| `refresh_due_at` | `products.promotion_refresh_due_at` |
| `last_checked_at` | `products.last_checked_at` |
| `last_seen_at` | `products.last_seen_at` |
| `source_run_id` | audit only |
| `source_page_no` | audit only |
| `catalog_change_count` | `products.catalog_change_count` |

Null optional fields must not overwrite a non-null consumer field unless the import policy explicitly allows clearing that field.

## 7. Consumer database contract

Existing table: `products`

Existing unique key: `jd_sku_id`

Existing columns remain the public application model. Add the following columns through Alembic; never alter production schema manually:

```sql
ALTER TABLE products
  ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'manual',
  ADD COLUMN item_url VARCHAR(500) NULL,
  ADD COLUMN promotion_url VARCHAR(500) NULL,
  ADD COLUMN promotion_link_created_at DATETIME NULL,
  ADD COLUMN promotion_link_expire_at DATETIME NULL,
  ADD COLUMN promotion_refresh_due_at DATETIME NULL,
  ADD COLUMN source_round_id VARCHAR(64) NULL,
  ADD COLUMN source_updated_at DATETIME NULL,
  ADD COLUMN last_checked_at DATETIME NULL,
  ADD COLUMN last_seen_at DATETIME NULL,
  ADD COLUMN source_payload_hash CHAR(64) NULL,
  ADD COLUMN catalog_change_count INT NOT NULL DEFAULT 0,
  ADD COLUMN last_import_run_id BIGINT NULL;
```

The SQL above is a contract illustration. The AIdeal CPS project must implement the equivalent Alembic migration using SQLAlchemy types and indexes.

Compatibility rule:

- `products.item_url` is the canonical JD detail page.
- `products.promotion_url` is the commission-tracked link.
- Existing `promotion_service.py` currently reads `products.product_url`; until that service is migrated, the importer must set `product_url = promotion_url`.

### New table: `product_import_runs`

| Column | Type | Constraints |
|---|---|---|
| `id` | BIGINT | primary key |
| `source` | VARCHAR(32) | not null, default `jd_union_datalab` |
| `schema_version` | VARCHAR(64) | not null |
| `round_id` | VARCHAR(64) | not null, unique with `source` |
| `manifest_sha256` | CHAR(64) | not null |
| `data_sha256` | CHAR(64) | not null |
| `status` | VARCHAR(32) | `received`, `validated`, `imported`, `rejected` |
| `row_count` | INT | not null |
| `inserted_count` | INT | default 0 |
| `updated_count` | INT | default 0 |
| `unchanged_count` | INT | default 0 |
| `deactivated_count` | INT | default 0 |
| `rejected_count` | INT | default 0 |
| `error_message` | TEXT | nullable |
| `started_at` | DATETIME | not null |
| `finished_at` | DATETIME | nullable |
| `created_at` | DATETIME | server default now |

### New table: `product_feed_staging`

| Column | Type | Constraints |
|---|---|---|
| `id` | BIGINT | primary key |
| `import_run_id` | BIGINT | indexed, foreign key to `product_import_runs.id` |
| `line_no` | INT | not null |
| `jd_sku_id` | VARCHAR(64) | not null |
| `payload` | JSON/TEXT | not null |
| `payload_hash` | CHAR(64) | not null |
| `validation_status` | VARCHAR(32) | `valid` or `rejected` |
| `validation_error` | TEXT | nullable |
| `created_at` | DATETIME | server default now |

Unique constraint: `(import_run_id, jd_sku_id)`.

## 8. Transactional import algorithm

1. Reject an already imported `(source, round_id)` unless explicitly running idempotent verification.
2. Create `product_import_runs(status='received')`.
3. Load and validate all feed rows into `product_feed_staging`.
4. Abort before touching `products` if any required-row validation or manifest count/hash validation fails.
5. In one database transaction, upsert by `products.jd_sku_id`:
   - insert missing SKU;
   - update changed fields only when `source_payload_hash` differs;
   - update `last_checked_at` and `last_seen_at` even when payload is unchanged;
   - never overwrite AI-generated fields (`ai_reason`, `ai_tags`) with null feed values;
   - set `product_url = promotion_url` during the compatibility period.
6. Set `product_import_runs.status='imported'` with counters.
7. On failure, rollback the product transaction and set the import run to `rejected` with `error_message`.

AIdeal CPS must serve only local MySQL data. It must never make a user request wait for data-lab SSH or network access.

## 9. Scheduling

Producer:

- Browser operations only during server-local 09:30-21:30.
- Full refresh every random 3-5 days.
- New-link item waits random 3-7 seconds.
- Page waits random 90-210 seconds.

Consumer:

- Run a lightweight pull/manifest check every 30 minutes during 09:30-22:00.
- If `round_id` is unchanged, do nothing.
- Import only a newly promoted commercial round.
- Candidate files may be validated with a `--dry-run` command but not imported into active products.

## 10. Source of truth and change control

This file is the authoritative producer contract.

The consumer mirror is:

```text
ShanGouXueHui/aideal-cps
docs/integration/DATA_LAB_PRODUCT_FEED_V1.md
```

Any V1 field or semantic change must update both repositories in the same change window. Breaking changes require a new schema version and new filenames; do not silently change V1 semantics.
