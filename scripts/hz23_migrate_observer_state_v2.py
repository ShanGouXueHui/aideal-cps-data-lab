#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

STATE = Path("run/hz23_observer_state.json")
PROBE = Path("reports/hz23_probe_scan_latest.json")


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    if not STATE.exists():
        result = {"ok": False, "error": "observer_state_missing", "state": str(STATE)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 2

    state = json.loads(STATE.read_text(encoding="utf-8"))
    before = dict(state)
    state["version"] = max(2, int(state.get("version") or 1))
    state.setdefault("observation_started_at", state.get("created_at"))
    state.setdefault("successful_probes", 0)
    state.setdefault("failed_probes", 0)
    state.setdefault("first_successful_probe_at", None)
    state.setdefault("last_probe_ok", None)
    state.setdefault("last_probe_reason", None)

    inferred_probe = False
    probe: dict[str, object] = {}
    if PROBE.exists():
        value = json.loads(PROBE.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            probe = value

    probe_ok = bool(
        probe.get("ok") is True
        and not (probe.get("risk") or [])
        and int(probe.get("scanned") or 0) >= 55
    )
    if probe_ok and int(state.get("successful_probes") or 0) == 0:
        state["successful_probes"] = 1
        state["first_successful_probe_at"] = probe.get("ts") or state.get("last_probe_at")
        state["last_probe_at"] = probe.get("ts") or state.get("last_probe_at")
        state["last_probe_ok"] = True
        state["last_probe_reason"] = None
        inferred_probe = True

    atomic_write(STATE, state)
    result = {
        "ok": True,
        "changed": state != before,
        "inferred_existing_successful_probe": inferred_probe,
        "successful_probes": state.get("successful_probes"),
        "failed_probes": state.get("failed_probes"),
        "first_successful_probe_at": state.get("first_successful_probe_at"),
        "observation_started_at": state.get("observation_started_at"),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
