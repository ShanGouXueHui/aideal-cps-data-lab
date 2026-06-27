# Legacy runtime scripts archive

This directory stores references to retired runtime scripts that must not be present as production entrypoints.

## HZ23 legacy observation daemon

- Original production path: `scripts/hz23_observation_daemon.sh`
- Legacy source commit: `b1a16aa6236c2eb26c4f8fbbf5cc9e0b05d31086`
- Legacy blob SHA: `7dd5640807a6d359694868156a388cc87495e0df`
- Replacement: `scripts/ops/hz23_formal_supervisor.sh`
- Launcher: `scripts/ops/start_hz23_formal_supervisor.sh`
- Retirement reason: the old daemon could run browser probe/full cycles on its own and commit/push runtime reports into `main`. Runtime evidence must be JSON-only and published to `runtime-evidence`.

To inspect the old code for forensics only:

```bash
git show b1a16aa6236c2eb26c4f8fbbf5cc9e0b05d31086:scripts/hz23_observation_daemon.sh
```

Do not restore the old script to `scripts/`. Formal production control must go through the formal supervisor only.

## HZ23 retired one-off controllers

The following scripts were removed from production paths after formal supervisor takeover because they can create a second browser controller if invoked manually or by stale process state.

- `scripts/ops/schedule_hz23_observation_daytime.sh`
  - Retired blob SHA: `195731a1b0969307ed00d057fba142e9a5fbc365`
- `scripts/ops/schedule_hz23_observation_resume_daytime.sh`
  - Retired blob SHA: `91c4b99b3382c7ebdbf519d134985bb1877e136a`
- `scripts/ops/run_hz23_smoke_now.sh`
  - Retired blob SHA: `9015d344f43255faebdbee0028ead12f81265d06`
- `scripts/ops/run_hz23_smoke_now_with_deps.sh`
  - Retired blob SHA: `98bc7ef48b219be07b4cd69e4b1a8ed88fe92f98`

Formal production entrypoints are limited to:

- `scripts/ops/start_hz23_formal_supervisor.sh`
- `scripts/ops/restart_hz23_formal_supervisor.sh`
- `scripts/ops/hz23_formal_supervisor.sh`
- `scripts/ops/hz23_formal_progress_publisher.sh`

For manual forensic inspection, use `git show <commit>:<path>` only. Do not restore retired one-off controllers into `scripts/ops/`.
