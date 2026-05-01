# AIdeal CPS Data Lab

This repository is isolated from the production `aideal-cps` runtime.

Purpose:
- Authorized JD/Jingfen portal data collection during JD Union API quota limitation.
- Normalize product snapshots into JSONL.
- Keep browser automation, cookies, raw HTML, HAR, screenshots, and collector dependencies outside Hangzhou production.

Hard rules:
- Do not run browser automation on Hangzhou production.
- Do not commit cookies, sessions, QR screenshots, raw account pages, HAR, HTML, or secrets.
- Do not modify production DB directly before dry-run validation.
- Production should consume only validated export files or a controlled importer.

Quick check:

```bash
PYTHONPATH=src python3 scripts/make_sample_export.py
PYTHONPATH=src python3 scripts/validate_export_jsonl.py data/import/sample_product_snapshots.jsonl
```
