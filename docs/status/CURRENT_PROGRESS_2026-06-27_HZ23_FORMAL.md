# Current Progress — HZ23 Formal Observation

Date: 2026-06-27

## Runtime summary

```text
ROUND_ID=hz23_obs_20260624_093503
PID=465713
ALIVE=true
MODE=paused_for_manual_verification
EXTRA=next_page=43 probe=failed
LAST_COMPLETED_PAGE=42
COMPLETED_COUNT=42
UNFINISHED_FIRST=43
SCANNED_TOTAL=2520
COMPLETE=False
LATEST_RUNTIME_EVIDENCE_HEAD=4b87c74
```

## Meaning

- Formal supervisor is alive.
- Retired HZ23 legacy entrypoints are absent.
- No second browser controller is expected.
- HZ23 observation is paused at page 43 due to JD verification/risk probe failure.
- Pages 1-42 are completed.
- Pages 43-67 remain unfinished.
- The system is waiting for manual JD verification and/or the next daytime hourly probe.

## User command for compact status

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/hz23_formal_summary.sh
```

## User command for entrypoint guard

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main && git reset --hard origin/main && bash scripts/ops/check_hz23_formal_entrypoints.sh
```

Expected guard output:

```text
CHECK_RC=0
```

## Next decision tree

### If summary shows `MODE=paused_for_manual_verification`

- Do not start a second job.
- If user has manually verified JD, either wait for the hourly probe or restart the formal supervisor to trigger immediate probe:

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/restart_hz23_formal_supervisor.sh
```

### If summary shows `MODE=running`

- Do nothing except monitor compact summary or GitHub runtime evidence.
- Do not restart unless it is clearly wedged and the evidence shows no progress.

### If summary shows `COMPLETE=True`

- Confirm `unfinished_pages=[]` in runtime-evidence summary.
- Then move to HZ23 candidate quality gate design.
- Do not start HZ24/MySQL/publish yet.

## Still blocked

```text
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
DUAL_WRITE_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```

## Important caveat

HZ21 collector is still controlled fail-closed. HZ23 observation completion is not equivalent to commercial short-link data readiness.
