# HZ23 Background Recovery and Status Runbook

Updated: 2026-07-01

## Current operating boundary

HZ23 observation page 1-67 has passed hard quality gate. The current blockers are downstream candidate feed readiness and commercial persistence, not HZ23 page observation.

Do not start HZ24, initialize MySQL, publish to AIdeal CPS, or run downstream sync until candidate feed gate and persistence dry-run pass.

## Recovery model

Formal HZ23 supervisor behavior:

1. Single instance via lock and PID file.
2. It resumes from the first unfinished page based on runtime evidence, not chat text.
3. During daytime window, it runs a lightweight page probe.
4. If manual verification has been completed and the page is safe, it resumes automatically.
5. During night window, it enters `night_wait` and does not touch the browser or page.
6. When all pages are complete, it writes `mode=complete` and exits. `ALIVE=false` after completion is expected.

Observed evidence:

- Page 43 manual verification was followed by successful automatic resume.
- Page 49 resumed in the next daytime window.
- Final status reached `mode=complete`, `completed_count=67`, `unfinished_pages_empty`.

## Query commands

### Compact all-in-one status

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/commercial_runtime_status.sh
```

### Status with bounded log tails

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && STATUS_TAIL=1 bash scripts/ops/commercial_runtime_status.sh
```

### HZ23 formal summary only

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/hz23_formal_summary.sh
```

### HZ23 quality gate only

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && bash scripts/ops/hz23_quality_gate.sh
```

### HZ21 collector readiness only

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && bash scripts/ops/hz21_collector_readiness.sh
```

### Candidate feed gate only

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && bash scripts/ops/hz23_candidate_feed_gate.sh
```

## Expected healthy HZ23 completed status

```text
HZ23_MODE=complete
HZ23_COMPLETE=True
HZ23_COMPLETED_COUNT=67
HZ23_LAST_COMPLETED_PAGE=67
HZ23_QUALITY_PASS=True
HZ21_READY=True
```

Known warning:

```text
HZ23_SCAN_ANOMALIES=[{'page': 63, 'scanned': 59}]
```

This warning means page 63 had 59 cards instead of 60. It does not block the HZ23 observation hard gate.

## Candidate feed status interpretation

If candidate output is empty, do not proceed to CPS integration.

Blocking state:

```text
CANDIDATE_GATE_PASS=False
CANDIDATE_FAILURES=['candidate_empty']
CANDIDATE_ROWS=0
```

This means HZ23 observation is complete, but no commercial candidate feed is ready for CPS consumption.

## Process interpretation

Expected after HZ23 completion:

```text
PROC_COUNT[hz23_formal_supervisor.sh]=0
PROC_COUNT[hz23_mainline_refresh.sh]=0
PROC_COUNT[hz22_prepare_all_product_page.py]=0
PROC_COUNT[hz23_scan_current_page.py]=0
```

If any of these are non-zero after completion, inspect before starting new work.

## Log paths

- `logs/hz23_formal_supervisor.nohup.log`
- `logs/hz23_formal_summary_publish.log`
- `logs/hz23_quality_gate_publish.log`
- `logs/hz21_collector_readiness_publish.log`
- `logs/hz23_candidate_finalize.log`
- `logs/hz23_candidate_feed_gate_publish.log`

Use bounded tails only, for example:

```bash
tail -n 120 logs/hz23_candidate_finalize.log
```
