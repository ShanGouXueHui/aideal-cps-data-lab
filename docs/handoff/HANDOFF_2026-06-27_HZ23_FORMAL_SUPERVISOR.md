# Handoff — HZ23 Formal Supervisor / AIdeal CPS Data Lab

Date: 2026-06-27
Repo: `ShanGouXueHui/aideal-cps-data-lab`
Main branch: `main`
Evidence branch: `runtime-evidence`
Primary runtime host: Hangzhou `cpsdata@121.41.111.36`
Runtime path: `/home/cpsdata/projects/aideal-cps-data-lab`

## 1. Conversation and project intent

This handoff continues the AIdeal CPS Data Lab / 智省优选 JD Union data collection project. The current task is to finish HZ23 page 1-67 observation under a production-safe formal supervisor, not to start HZ24, MySQL, publish, or AIdeal CPS sync.

The earlier startup context required:

- Chinese, professional, direct, structured communication.
- No Codex CLI.
- Linux snippets must not use `set -e`.
- User executes only short entrypoint commands.
- Long scripts/docs/log parsing must be committed to GitHub, not printed in chat.
- Runtime evidence and logs should be checked from GitHub whenever possible.
- JD account login/verification is manual; credentials must not be scripted or stored.

## 2. Current runtime state

Latest compact summary observed before this handoff:

```text
SUMMARY_REPORT=reports/hz23_formal_summary_latest.json
PID=465713
ALIVE=true
MODE=paused_for_manual_verification
EXTRA=next_page=43 probe=failed
LAST_COMPLETED_PAGE=42
COMPLETED_COUNT=42
UNFINISHED_FIRST=43
SCANNED_TOTAL=2520
COMPLETE=False
PUBLISH_RC=0
RUNTIME_EVIDENCE_HEAD=4b87c74
```

Interpretation:

- Formal supervisor is alive and is the only controller.
- HZ23 observation round is `hz23_obs_20260624_093503`.
- Pages 1-42 are complete.
- First unfinished page is 43.
- JD verification/risk remains the current blocker.
- Supervisor is paused and will probe during daytime; night behavior is low-frequency heartbeat without JD probing.

## 3. Formal production entrypoints

Allowed production HZ23 formal entrypoints:

```text
scripts/ops/start_hz23_formal_supervisor.sh
scripts/ops/restart_hz23_formal_supervisor.sh
scripts/ops/hz23_formal_supervisor.sh
scripts/ops/hz23_formal_progress_publisher.sh
scripts/ops/hz23_formal_summary.sh
scripts/ops/check_hz23_formal_entrypoints.sh
```

Retired production entrypoints removed from `main`:

```text
scripts/hz23_observation_daemon.sh
scripts/ops/schedule_hz23_observation_daytime.sh
scripts/ops/schedule_hz23_observation_resume_daytime.sh
scripts/ops/run_hz23_smoke_now.sh
scripts/ops/run_hz23_smoke_now_with_deps.sh
```

Archive record:

```text
archive/legacy/README.md
```

Do not restore retired scripts into production paths.

## 4. Current status files and evidence

Use these files first:

```text
runtime-evidence:reports/hz23_formal_summary_latest.json
runtime-evidence:reports/hz23_formal_supervisor_status_latest.json
runtime-evidence:reports/hz23_formal_progress_latest.json
runtime-evidence:reports/hz23_observation_resume_auto_latest.json
runtime-evidence:reports/hz23_round_hz23_obs_20260624_093503_latest.json
```

Compact status command for the user:

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/hz23_formal_summary.sh
```

Entry point guard command:

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main && git reset --hard origin/main && bash scripts/ops/check_hz23_formal_entrypoints.sh
```

Restart formal supervisor only if needed:

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/restart_hz23_formal_supervisor.sh
```

## 5. Current hard gates

Still false / blocked:

```text
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
DUAL_WRITE_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```

Do not start HZ24, Data Lab MySQL initialization, dual-write, publish, or AIdeal CPS sync until HZ23 observation 1-67 completes and candidate quality gates are defined and passed.

## 6. Known technical facts

- HZ21 collector remains controlled fail-closed: `reason=hz21_collector_not_mainlined`.
- `collect_unavailable_pages` is expected during HZ23 observation and means short-link collection is not commercial-ready.
- The old 3304 LKG path is closed: no exact current-disk candidate/hash match was found; do not try to reconstruct it from seen/import files.
- Current HZ23 observation can only prove page scan/catalog observation capability, not final commercial candidate quality.

## 7. Formal supervisor behavior

- Enforces single instance via lock and PID file.
- Cleans legacy daemon/scheduler/smoke/foreground HZ23 jobs before starting.
- Reads resume summary from `runtime-evidence` and computes first unfinished page.
- Performs a lightweight probe on the next unfinished page during daytime.
- If probe succeeds, resumes from first unfinished page.
- If risk/verification is detected, pauses and waits for manual JD verification.
- Publishes status and rolling progress to `runtime-evidence` only.
- Does not bypass verification, crack CAPTCHA, use multiple accounts, or run concurrent browsers.

## 8. User working style

- Do not print long scripts or long logs in chat.
- Upload scripts/docs to GitHub, then give short entrypoint commands.
- User pastes compact summaries only.
- If a log is too long, ask for `RUNTIME_EVIDENCE_HEAD` or compact summary; inspect GitHub files directly.
- Avoid repeated clarification if repo/path/round_id are already known.

## 9. Industry-practice guidance reflected in the design

- Throttling/backoff and low concurrency are preferred over bursty crawls. Scrapy AutoThrottle documents dynamic delay and target concurrency principles.
- Browser automation should use explicit state checks and avoid blind sleeps where possible; Selenium documentation explains wait synchronization and warns that simple sleeps can be flaky.
- Bot detection and verification can bias or block automated sessions; do not treat CAPTCHA/verification as a technical obstacle to bypass. Use pause/manual verification/resume.
- Single active controller, PID/lock, checkpointing, and rolling latest-only evidence prevent duplicate browser control and unbounded logs.

## 10. Next steps

1. Wait for the formal supervisor to probe again, or run compact summary the next day.
2. If `MODE=paused_for_manual_verification` and `UNFINISHED_FIRST=43`, manually verify JD and either wait for hourly probe or restart supervisor to probe immediately.
3. If `MODE=running`, do not start anything else.
4. If `COMPLETE=True` and unfinished pages are empty, move to HZ23 candidate quality gate design.
5. Before candidate generation, decide whether to mainline HZ21 browser collector or keep observation-only scope. Do not claim commercial short-link coverage until HZ21 is mainlined and validated.
