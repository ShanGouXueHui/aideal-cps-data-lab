# Commission MySQL Preparation Status — 2026-06-14

## Current gate

```text
HZ23 full observation round: not yet verified in GitHub
Data Lab production MySQL: not initialized
Data Lab DB write: disabled
Data Lab dual-write: disabled
Data Lab publish: disabled
AIdeal CPS sync: disabled
```

No production database, HZ23 service, JD browser session, or consumer traffic was changed by this preparation work.

## Implemented in Data Lab

- Disabled-by-default database settings.
- Versioned MySQL V1 upgrade and rollback SQL.
- Commission product domain model using Decimal values.
- Stable business payload hash excluding observation timestamps and lineage.
- Repository protocol and transactional MySQL repository core.
- Complete commission field persistence and history writes only for business changes.
- Candidate JSONL validation, SKU deduplication, checksum and dry-run planning.
- Gated JSONL-to-MySQL backfill command; execution requires an explicit flag and write feature flag.
- Database URL and server option-file connection modes.
- Offline DDL and migration-pair validators.
- Offline unit tests and one-command preparation check suite.
- Centralized HZ23 strong-risk policy and simulation-based risk-policy validation.

## Implemented in AIdeal CPS

- Data Lab connection and tunnel configuration with `DATA_LAB_SYNC_ENABLED=false` by default.
- Strict read-row contract validation for SKU, Decimal fields, promotion URL, status and payload hash.
- Local-only, noninteractive SSH tunnel command builder.
- Read-only production schema/Alembic preflight script.
- Offline tests for contract validation, tunnel safety and disabled default.

## Intentionally not executed

- No MySQL database or account creation.
- No migration upgrade/downgrade against production.
- No JSONL backfill execution.
- No HZ23 dual-write.
- No publish-version activation.
- No SSH tunnel establishment.
- No AIdeal CPS product-table mutation.

## Remaining gates

1. Run Data Lab offline preparation checks and publish the summary report.
2. Run AIdeal CPS production schema preflight and confirm the actual Alembic revision chain.
3. Verify at least two HZ23 daily probes and one complete 1-67 round.
4. Require `scanned_total >= 3900`, no unfinished pages, no stop reason and zero duplicate SKU.
5. Validate candidate checksum, row count and schema.
6. Only after observation acceptance: initialize MySQL, run backfill, verify consistency, then enable dual-write in stages.
