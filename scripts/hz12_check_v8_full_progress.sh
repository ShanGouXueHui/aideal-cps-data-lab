#!/usr/bin/env bash
# HZ12 v8 full collection progress checker.
# No `exit` is used because the user's shell environment may logout on exit.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz12_check_v8_full_progress.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p reports docs/ops logs run data/import backups

  LATEST_LOG="$(ls -t logs/hz12aa_product_all_v8_reposition_full_4000_*.log 2>/dev/null | head -n 1 || true)"
  if [ -z "$LATEST_LOG" ]; then
    LATEST_LOG="$(ls -t logs/hz12z_product_all_v7_full_4000_*.log 2>/dev/null | head -n 1 || true)"
  fi
  REPORT_JSON="reports/hz12aa_product_all_v8_full_progress_latest.json"
  REPORT_MD="docs/ops/DL2_HZ12AA_PRODUCT_ALL_V8_FULL_PROGRESS.md"

  echo "===== HZ12 v8 full progress check ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "LATEST_LOG=$LATEST_LOG"

  python3 - <<PY
import json
import subprocess
from pathlib import Path
from datetime import datetime

latest_log = "$LATEST_LOG"
report_json = Path("$REPORT_JSON")
report_md = Path("$REPORT_MD")
latest_path = Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
state_path = Path("run/hz12_product_all_full_state.json")
runtime_report_path = Path("run/hz12_product_all_full_report_latest.json")
stop_path = Path("run/hz12_product_all_STOP_REQUIRED.json")

def read_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        return {"_read_error": repr(e), "_path": str(p)}

def read_jsonl(path):
    p = Path(path)
    rows = []
    if p.exists():
        target = p.resolve() if p.is_symlink() else p
        for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

def parse_dt(s):
    if not s:
        return None
    for fmt in (None, "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.fromisoformat(str(s)) if fmt is None else datetime.strptime(str(s), fmt)
        except Exception:
            pass
    return None

def events(path, limit=260):
    p = Path(path)
    out = []
    if not path or not p.exists():
        return out
    keep = {"PAGE_CANDIDATES", "ITEM_OK", "ITEM_FAIL", "STOP_REQUIRED", "TARGET_TOTAL_REACHED", "PRODUCT_NEXT_TEXT", "PRODUCT_NEXT_TEXT_FAIL", "PRODUCT_NEXT_TEXT_UNCHANGED_LIMIT", "PRODUCT_NEXT_REPOSITION", "FULL_CYCLE_DONE", "SLEEP_REFRESH_NOT_DUE", "STRICT_TITLE_CANDIDATES"}
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get("event") in keep:
            out.append(x)
    return out[-limit:]

def pgrep(pattern):
    try:
        r = subprocess.run(["pgrep", "-af", pattern], text=True, capture_output=True)
        return [x for x in r.stdout.splitlines() if x.strip()]
    except Exception as e:
        return [f"pgrep_error:{e!r}"]

rows = read_jsonl(latest_path)
ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
skus = [str(x.get("sku") or "").strip() for x in ok if x.get("sku")]
dedup = sorted(set(skus))
non_numeric = [x for x in ok if not str(x.get("sku") or "").isdigit()]
missing = {
    "title": sum(1 for x in ok if not x.get("title")),
    "image_url": sum(1 for x in ok if not x.get("image_url")),
    "item_url": sum(1 for x in ok if not x.get("item_url")),
    "price": sum(1 for x in ok if not x.get("price")),
    "commission_rate": sum(1 for x in ok if not x.get("commission_rate")),
    "estimated_income": sum(1 for x in ok if not x.get("estimated_income")),
    "long_url": sum(1 for x in ok if not x.get("long_url")),
    "qr_url": sum(1 for x in ok if not x.get("qr_url")),
    "jd_command": sum(1 for x in ok if not x.get("jd_command")),
    "refresh_due_at": sum(1 for x in ok if not x.get("refresh_due_at")),
}
pages = sorted({int(x.get("page_no")) for x in ok if str(x.get("page_no") or "").isdigit()})
first_ts = None
last_ts = None
for x in ok:
    dt = parse_dt(x.get("link_created_at") or x.get("ts"))
    if dt:
        first_ts = dt if first_ts is None or dt < first_ts else first_ts
        last_ts = dt if last_ts is None or dt > last_ts else last_ts
runtime_hours = None
per_hour = None
eta_hours_to_4000 = None
if first_ts and last_ts and last_ts > first_ts:
    runtime_hours = max((last_ts - first_ts).total_seconds() / 3600, 1/60)
    per_hour = len(ok) / runtime_hours
    if per_hour > 0:
        eta_hours_to_4000 = max(0, (4000 - len(dedup)) / per_hour)

ev = events(latest_log)
next_text_events = [x for x in ev if x.get("event") == "PRODUCT_NEXT_TEXT"]
next_reposition_events = [x for x in ev if x.get("event") == "PRODUCT_NEXT_REPOSITION"]
next_events = next_text_events + next_reposition_events
changed_next = [x for x in next_events if (x.get("result") or {}).get("changed")]
fail_events = [x for x in ev if x.get("event") == "ITEM_FAIL"]
stop_events = [x for x in ev if x.get("event") == "STOP_REQUIRED"]
processes = pgrep("hz12_product_all_full_collector|chrome.*19228|chrome.*19229")
report = {
    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "phase": "HZ12AA v8 full 4000 progress check",
    "latest_log": latest_log,
    "processes": processes,
    "stop_exists": stop_path.exists(),
    "stop": read_json(stop_path),
    "counts": {"rows": len(rows), "ok": len(ok), "dedup_sku": len(dedup), "non_numeric": len(non_numeric), "duplicate_ok_rows": len(ok) - len(dedup), "page_count": len(pages), "first_page": pages[0] if pages else None, "last_page": pages[-1] if pages else None, "target_total": 4000, "progress_pct": round(len(dedup) / 4000 * 100, 2)},
    "missing": missing,
    "pagination": {"next_text_events_tail": len(next_text_events), "next_reposition_events_tail": len(next_reposition_events), "changed_next_events_tail": len(changed_next), "last_next": next_events[-1] if next_events else None},
    "failures": {"item_fail_events_tail": len(fail_events), "stop_events_tail": len(stop_events), "last_fail": fail_events[-1] if fail_events else None},
    "throughput": {"first_ts": first_ts.isoformat(timespec="seconds") if first_ts else None, "last_ts": last_ts.isoformat(timespec="seconds") if last_ts else None, "runtime_hours_est": round(runtime_hours, 3) if runtime_hours else None, "estimated_ok_per_hour": round(per_hour, 2) if per_hour else None, "eta_hours_to_4000": round(eta_hours_to_4000, 2) if eta_hours_to_4000 is not None else None},
    "runtime_report": read_json(runtime_report_path),
    "state": read_json(state_path),
    "events_tail": ev,
    "sample_last_20": [{"page_no": x.get("page_no"), "sku": x.get("sku"), "short_url": x.get("short_url"), "title": (x.get("title") or "")[:100], "price": x.get("price"), "commission_rate": x.get("commission_rate"), "estimated_income": x.get("estimated_income")} for x in ok[-20:]],
    "decision": "If v8 process is alive, stop=false, missing=0, and dedup_sku grows beyond the v7 plateau, continue. If still stuck, switch to category/query expansion."
}
report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
md = []
md.append("# HZ12AA Product All V8 Full Progress")
md.append("")
md.append(f"- Generated at: {report['ts']}")
md.append(f"- counts: {report['counts']}")
md.append(f"- missing: {missing}")
md.append(f"- stop_exists: {report['stop_exists']}")
md.append(f"- pagination: {report['pagination']}")
md.append(f"- failures: {report['failures']}")
md.append(f"- throughput: {report['throughput']}")
md.append("")
report_md.write_text("\n".join(md), encoding="utf-8")
print(json.dumps({"report": str(report_json), "counts": report["counts"], "missing": missing, "stop_exists": report["stop_exists"], "pagination": report["pagination"], "failures": report["failures"], "throughput": report["throughput"], "process_alive": any('hz12_product_all_full_collector' in p for p in processes)}, ensure_ascii=False, indent=2))
PY

  git add "$REPORT_JSON" "$REPORT_MD"
  git commit -m "docs: add HZ12AA v8 full progress report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "REPORT=$REPORT_JSON"
  echo "LATEST_LOG=$LATEST_LOG"
  git status --short | head -n 60
fi
