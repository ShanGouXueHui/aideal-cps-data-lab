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
