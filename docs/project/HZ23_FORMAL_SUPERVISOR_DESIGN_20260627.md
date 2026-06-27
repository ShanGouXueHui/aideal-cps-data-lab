# HZ23 Formal Supervisor Design Record

Date: 2026-06-27
Scope: HZ23 JD Union observation/resume controller

## 1. Problem

HZ23 page observation no longer fails primarily because of page parsing. Recent failures are dominated by JD verification/risk pages such as:

```text
risk_after_jump
risk_handler
京东验证
快速验证
安全验证
```

A legacy daemon and multiple one-off scheduler/smoke entrypoints created risk of concurrent browser control. Concurrent page navigation can corrupt JD session state, increase verification probability, and make evidence ambiguous.

## 2. Production principle

There must be exactly one production control path for HZ23 browser activity.

Allowed production logic:

```text
formal supervisor -> lightweight probe -> resume current round -> publish runtime evidence
```

Disallowed production logic:

```text
legacy daemon
one-off daytime scheduler
one-off resume scheduler
smoke-now entrypoint
parallel browser/account rotation
verification bypass/CAPTCHA automation
runtime evidence committed to main
```

## 3. Architecture

```text
operator short command
  -> start/restart formal supervisor
     -> flock + pid guard
     -> force clean old controllers
     -> load latest summary from runtime-evidence
     -> compute first unfinished page
     -> daytime probe
        -> if JD page safe: run hz23_mainline_refresh from checkpoint
        -> if verification/risk: pause for manual verification
     -> rolling latest progress publisher
     -> compact summary publisher
```

## 4. Files

Production entrypoints:

```text
scripts/ops/start_hz23_formal_supervisor.sh
scripts/ops/restart_hz23_formal_supervisor.sh
scripts/ops/hz23_formal_supervisor.sh
scripts/ops/hz23_formal_progress_publisher.sh
scripts/ops/hz23_formal_summary.sh
scripts/ops/check_hz23_formal_entrypoints.sh
```

Runtime evidence files:

```text
reports/hz23_formal_summary_latest.json
reports/hz23_formal_supervisor_status_latest.json
reports/hz23_formal_progress_latest.json
reports/hz23_observation_resume_auto_latest.json
reports/hz23_round_hz23_obs_20260624_093503_latest.json
reports/hz23_round_latest.json
```

Archive-only legacy record:

```text
archive/legacy/README.md
```

## 5. State machine

```text
starting
  -> paused_for_manual_verification
  -> running
  -> complete
  -> blocked
  -> night_wait
```

Meaning:

- `paused_for_manual_verification`: JD probe failed due to verification/risk or unsafe page. Do not run full refresh.
- `running`: current HZ23 resume job is active. Do not start any second job.
- `complete`: pages 1-67 are complete. Move to quality/candidate gates.
- `blocked`: local evidence/summary cannot be loaded or parsed.
- `night_wait`: no JD probe at night.

## 6. Checkpoint and resume

The supervisor never guesses a page number from chat text. It reads:

```text
reports/hz23_round_${ROUND_ID}_latest.json
```

from `runtime-evidence`, derives `completed_pages`, and resumes from the first missing page in `[1, PAGE_END]`.

## 7. Observability

The user-facing compact command is:

```bash
bash scripts/ops/hz23_formal_summary.sh
```

The script publishes full details to runtime-evidence and prints only a short summary.

Rolling progress is latest-only:

```text
reports/hz23_formal_progress_latest.json
```

This avoids unbounded report growth while still allowing GitHub-based inspection.

## 8. Rate limiting and verification handling

- Daytime verification probe interval defaults to 3600 seconds.
- Night heartbeat interval defaults to 10800 seconds.
- Mainline HZ23 page waits already include randomized page sleep and long randomized pauses every 10-15 pages.
- The system never attempts to solve or bypass verification automatically.
- Manual verification is part of the control loop.

## 9. Engineering guardrails

- No duplicate production entrypoints.
- No compatibility branch for old scripts.
- No old path restoration.
- No runtime reports in `main`.
- No multi-account/multi-browser parallelization to evade risk checks.
- No generated long logs in chat.
- Scripts must be thin entrypoints; growing shell logic should be moved into versioned Python application/service modules in later refactor.

## 10. Industry-practice references

The current design follows these general principles:

- Adaptive throttling/backoff and low target concurrency are standard crawler practices. Scrapy AutoThrottle describes dynamic delay, target concurrency, and slowing down when errors occur.
- Browser automation is flaky when blind sleeps replace explicit state checks; Selenium recommends waiting strategies and explains why simple sleeps can fail.
- Modern anti-bot/verification systems fingerprint browser automation and may block sessions; this motivates pause/manual verification/resume rather than bypass logic.
- Web-scraped data can be biased by volatile, personalized, or blocked content; evidence must preserve lineage and collection state.

References:

- https://docs.scrapy.org/en/latest/topics/autothrottle.html
- https://www.selenium.dev/documentation/webdriver/waits/
- https://arxiv.org/abs/2606.14525
- https://arxiv.org/abs/2308.02231

## 11. Future refactor direction

After page 1-67 completes:

1. Move supervisor state machine from shell into typed Python service modules.
2. Keep shell as a thin process launcher only.
3. Add unit tests for first-unfinished-page, risk classification, status summary generation, and entrypoint guard.
4. Decide HZ21 browser collector mainline scope before candidate generation.
5. Define candidate quality gates before HZ24/MySQL/publish.
