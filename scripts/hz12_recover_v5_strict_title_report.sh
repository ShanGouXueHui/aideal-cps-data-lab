#!/usr/bin/env bash
# HZ12 v5 strict-title smoke recovery report.
# Use this when the terminal disconnected before the smoke script generated/pushed reports.
# No `exit` is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p reports docs/ops logs run data/import backups

  LATEST_LOG="$(ls -t logs/hz12t_product_all_v5_strict_title_smoke_*.log 2>/dev/null | head -n 1 || true)"
  if [ -z "$LATEST_LOG" ]; then
    LATEST_LOG="$(ls -t logs/hz12s_product_all_v4_ui_pagination_smoke_*.log 2>/dev/null | head -n 1 || true)"
  fi

  echo "===== HZ12 v5 recovery report ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "LATEST_LOG=$LATEST_LOG"

  echo "===== worker process check ====="
  pgrep -af "hz12_product_all_full_collector|chrome.*19228|chrome.*19229" | head -n 80 || true

  echo "===== merge/current report generation ====="
  python3 - <<PY
import json
from pathlib import Path
from datetime import datetime
import subprocess

log_path = "$LATEST_LOG"

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

def read_json(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        return {"_read_error": repr(e), "_path": str(p)}

def events(path):
    p = Path(path)
    out = []
    if not path or not p.exists():
        return out
    keep = {"STRICT_TITLE_CANDIDATES", "TITLE_ENRICHED_CANDIDATES_V3", "PAGE_CANDIDATES", "ITEM_OK", "ITEM_FAIL", "STOP_REQUIRED", "FULL_CYCLE_DONE", "TARGET_TOTAL_REACHED", "PRODUCT_NEXT_PAGE", "PRODUCT_NEXT_PAGE_FAIL", "PRODUCT_NEXT_UNCHANGED_LIMIT", "SLEEP_REFRESH_NOT_DUE"}
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get("event") in keep:
            out.append(x)
    return out[-260:]

def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        try:
            return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

rows = read_jsonl("data/import/hz_jd_union_product_all_full_links_latest.jsonl")
ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
skus = {str(x.get("sku")) for x in ok if x.get("sku")}
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
ev = events(log_path)
next_events = [x for x in ev if x.get("event") == "PRODUCT_NEXT_PAGE"]
changed_next = [x for x in next_events if (x.get("result") or {}).get("changed")]
fail_events = [x for x in ev if x.get("event") == "ITEM_FAIL"]
stop_events = [x for x in ev if x.get("event") == "STOP_REQUIRED"]
strict_events = [x for x in ev if x.get("event") == "STRICT_TITLE_CANDIDATES"]
first_ts = None
last_ts = None
for x in ok:
    dt = parse_dt(x.get("link_created_at") or x.get("ts"))
    if dt:
        first_ts = dt if first_ts is None or dt < first_ts else first_ts
        last_ts = dt if last_ts is None or dt > last_ts else last_ts
runtime_minutes = None
if first_ts and last_ts and last_ts > first_ts:
    runtime_minutes = (last_ts - first_ts).total_seconds() / 60
throughput_per_hour = len(ok) / runtime_minutes * 60 if runtime_minutes and runtime_minutes > 0 else None
report = {
    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "phase": "HZ12 v5 strict-title smoke recovered report",
    "head": subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True).stdout.strip(),
    "latest_log": log_path,
    "stop_exists": Path("run/hz12_product_all_STOP_REQUIRED.json").exists(),
    "stop": read_json("run/hz12_product_all_STOP_REQUIRED.json"),
    "runtime_report": read_json("run/hz12_product_all_full_report_latest.json"),
    "state": read_json("run/hz12_product_all_full_state.json"),
    "counts": {"rows": len(rows), "ok": len(ok), "dedup_sku": len(skus), "non_numeric": len(non_numeric), "pages": pages, "page_count": len(pages)},
    "missing": missing,
    "pagination": {"next_events": len(next_events), "changed_next_events": len(changed_next)},
    "failures": {"item_fail_events": len(fail_events), "stop_events": len(stop_events)},
    "strict_title": {"strict_events": len(strict_events), "last": strict_events[-1] if strict_events else None},
    "throughput": {"runtime_minutes_est": round(runtime_minutes, 2) if runtime_minutes else None, "estimated_ok_per_hour": round(throughput_per_hour, 2) if throughput_per_hour else None},
    "sample_last_30": [{"page_no": x.get("page_no"), "sku": x.get("sku"), "short_url": x.get("short_url"), "title": (x.get("title") or "")[:100], "price": x.get("price"), "commission_rate": x.get("commission_rate"), "estimated_income": x.get("estimated_income")} for x in ok[-30:]],
    "events_tail": ev,
    "commercial_readiness": {"ready_for_dry_run_import": len(ok) >= 100 and len(non_numeric) == 0 and missing.get("title", 0) == 0 and not Path("run/hz12_product_all_STOP_REQUIRED.json").exists(), "ready_for_production_import": False, "reason": "Production import still requires full data size and importer dry-run validation."},
    "diagnosis_hint": "If ok is low but stop is false, likely strict title gate is skipping many cards or pagination is slow. If title missing > 0, v5 gate was not used or old latest data remained."
}
Path("reports/hz12t_product_all_v5_strict_title_smoke_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
md = []
md.append("# HZ12T Product All V5 Strict Title Smoke Recovered")
md.append("")
md.append(f"- Generated at: {report['ts']}")
md.append(f"- counts: {report['counts']}")
md.append(f"- missing: {missing}")
md.append(f"- stop_exists: {report['stop_exists']}")
md.append(f"- pagination: {report['pagination']}")
md.append(f"- failures: {report['failures']}")
md.append(f"- strict_title: {report['strict_title']}")
md.append(f"- throughput: {report['throughput']}")
md.append("")
Path("docs/ops/DL2_HZ12T_PRODUCT_ALL_V5_STRICT_TITLE_SMOKE.md").write_text("\n".join(md), encoding="utf-8")
print(json.dumps({"report": "reports/hz12t_product_all_v5_strict_title_smoke_latest.json", "counts": report["counts"], "missing": missing, "stop_exists": report["stop_exists"], "pagination": report["pagination"], "failures": report["failures"], "strict_title": report["strict_title"], "throughput": report["throughput"]}, ensure_ascii=False, indent=2))
PY

  echo "===== commit and push recovered report ====="
  git add reports/hz12t_product_all_v5_strict_title_smoke_latest.json docs/ops/DL2_HZ12T_PRODUCT_ALL_V5_STRICT_TITLE_SMOKE.md
  git commit -m "docs: recover HZ12T v5 strict-title report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "REPORT=reports/hz12t_product_all_v5_strict_title_smoke_latest.json"
  echo "LATEST_LOG=$LATEST_LOG"
  pgrep -af "hz12_product_all_full_collector|chrome.*19228|chrome.*19229" | head -n 80 || true
fi
