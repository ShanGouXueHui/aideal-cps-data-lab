# Architecture

## Boundary

This repository is a data lab. It is not a production runtime dependency.

Production repository:
- `aideal-cps`
- FastAPI, WeChat service, H5 pages, admin pages.
- No browser automation dependency should be introduced for portal collection.

Data lab repository:
- `aideal-cps-data-lab`
- Authorized collection, raw capture, cleaning, normalization, and export.
- Secrets, cookies, raw pages, HAR files, screenshots, and account data stay local.

## Data flow

1. Collect authorized portal pages on the Singapore development environment.
2. Store raw files under ignored runtime directories.
3. Normalize product snapshots into `data/import/*.jsonl`.
4. Validate exports with `scripts/validate_export_jsonl.py`.
5. Import validated snapshots with a separate controlled importer.

## Production rule

Do not run browser automation on Hangzhou production.
Do not import this package into `aideal.service`.
