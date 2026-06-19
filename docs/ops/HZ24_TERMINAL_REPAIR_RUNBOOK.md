# HZ24 Terminal Repair Runbook

## Scope

This procedure repairs terminal-state classification only. It does not start JD collection.

## Required sequence

1. Run the offline quality gate.
2. Run terminal repair in dry-run mode.
3. Review the generated counts and failures.
4. Execute the terminal repair explicitly.
5. Verify the resume gate reports queue 221, linked 72, unavailable 5, pending 144.
6. Publish only JSON reports and export manifests through the repository allowlisted publisher.
7. Keep HZ24 collection paused until `resume_allowed` is true.

## Prohibited artifacts

Do not publish row-level import files, browser profiles, cookies, tokens, private keys, environment files, or database credentials.

## Runtime entrypoints

- Offline repair: `python scripts/hz24_repair_terminal_state.py`
- Explicit execution: `python scripts/hz24_repair_terminal_state.py --execute`
- Resume validation: `python scripts/hz24_validate_resume_gate.py`
- Sanitized report publication: `bash scripts/hz24_publish_terminal_repair_evidence.sh`

The collection loop is a separate action and must not be invoked by the repair procedure.
