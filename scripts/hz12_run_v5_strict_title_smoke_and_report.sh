#!/usr/bin/env bash
# HZ12 v5 strict-title product_all smoke runner.
# No `exit` is used because the user's shell environment may logout on exit.
# Run on collector server 121.41.111.36 as user cpsdata:
#   cd ~/projects/aideal-cps-data-lab && git fetch origin main && git rebase origin/main && bash scripts/hz12_run_v5_strict_title_smoke_and_report.sh

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"

if ! cd "$PROJECT_DIR"; then
  echo "===== SUMMARY ====="
  echo "ERROR=PROJECT_DIR_NOT_FOUND"
  echo "PROJECT_DIR=$PROJECT_DIR"
  echo "WHOAMI=$(whoami)"
  echo "HINT=请在杭州采集机 121.41.111.36 的 cpsdata 用户下执行；不要在生产机 deploy 用户下执行。"
else
  TS="$(date +%Y%m%d_%H%M%S)"
  mkdir -p backups logs reports docs/ops run data/import

  echo "===== HZ12 v5 strict-title smoke start ====="
  echo "PWD=$(pwd)"
  echo "USER=$(whoami)"
  echo "HEAD_BEFORE=$(git rev-parse --short HEAD 2>/dev/null || true)"

  echo "===== stop old HZ12 worker only, keep Chrome ====="
  pkill -f "python.*run/hz12_product_all_full_collector" 2>/dev/null || true
  sleep 2

  echo "===== backup and reset HZ12 smoke state ====="
  for f in \
    run/hz12_product_all_STOP_REQUIRED.json \
    run/hz12_product_all_full_state.json \
    data/import/hz_jd_union_product_all_full_links_latest.jsonl
  do
    if [ -e "$f" ]; then
      mv -v "$f" "backups/$(basename "$f").before_hz12t_v5_smoke_${TS}" || true
    fi
  done

  echo "===== static check ====="
  .venv-browser/bin/python -m py_compile \
    run/hz12_product_all_full_collector.py \
    run/hz12_product_all_full_collector_v3.py \
    run/hz12_product_all_full_collector_v4.py \
    run/hz12_product_all_full_collector_v5.py
  STATIC_RC=$?

  if [ "$STATIC_RC" != "0" ]; then
    SMOKE_RC=SKIPPED
    echo "STATIC_CHECK_FAILED"
  else
    echo "===== run v5 strict-title smoke target 80 ====="
    SMOKE_LOG="logs/hz12t_product_all_v5_strict_title_smoke_${TS}.log"
    (
      set -a
      . config/hz12_product_all_full.env
      set +a
      export HZ12_RUN_ONCE=true
      export HZ12_PAGE_MAX=20
      export HZ12_TARGET_TOTAL=80
      export HZ12_ITEMS_PER_PAGE_LIMIT=20
      export HZ12_ITEM_SLEEP_MIN=5
      export HZ12_ITEM_SLEEP_MAX=10
      export HZ12_PAGE_SLEEP_MIN=3
      export HZ12_PAGE_SLEEP_MAX=6
      timeout 3600 .venv-browser/bin/python run/hz12_product_all_full_collector_v5.py
    ) > "$SMOKE_LOG" 2>&1
    SMOKE_RC=$?
  fi

  if [ -z "${SMOKE_LOG:-}" ]; then
    SMOKE_LOG=""
  fi

  echo "===== generate report ====="
  python3 - <<PY
import json
from pathlib import Path
from datetime import datetime

log_path = "$SMOKE_LOG"

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
        return {"_read_error": repr(e)}

def events(path):
    p = Path(path)
    out = []
    if not path or not p.exists():
        return out
    keep = {"STRICT_TITLE_CANDIDATES", "TITLE_ENRICHED_CANDIDATES_V3", "PAGE_CANDIDATES", "ITEM_OK", "ITEM_FAIL", "STOP_REQUIRED", "FULL_CYCLE_DONE", "TARGET_TOTAL_REACHED", "PRODUCT_NEXT_PAGE", "PRODUCT_NEXT_PAGE_FAIL", "PRODUCT_NEXT_UNCHANGED_LIMIT"}
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
report = {
    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "phase": "HZ12T v5 strict-title product_all smoke",
    "return_codes": {"static": "$STATIC_RC", "smoke": "$SMOKE_RC", "timeout_124_can_be_expected": True},
    "stop_exists": Path("run/hz12_product_all_STOP_REQUIRED.json").exists(),
    "stop": read_json("run/hz12_product_all_STOP_REQUIRED.json"),
    "runtime_report": read_json("run/hz12_product_all_full_report_latest.json"),
    "counts": {"rows": len(rows), "ok": len(ok), "dedup_sku": len(skus), "non_numeric": len(non_numeric), "pages": pages, "page_count": len(pages)},
    "missing": missing,
    "pagination": {"next_events": len(next_events), "changed_next_events": len(changed_next)},
    "failures": {"item_fail_events": len(fail_events), "stop_events": len(stop_events)},
    "strict_title": {"strict_events": len(strict_events), "last": strict_events[-1] if strict_events else None},
    "sample_last_20": [{"page_no": x.get("page_no"), "sku": x.get("sku"), "short_url": x.get("short_url"), "title": (x.get("title") or "")[:100], "price": x.get("price"), "commission_rate": x.get("commission_rate"), "estimated_income": x.get("estimated_income")} for x in ok[-20:]],
    "events_tail": ev,
    "log": log_path,
    "decision": "If ok reaches 80, title missing is 0, no STOP, and pagination changed at least once, start full v5 collection."
}
Path("reports/hz12t_product_all_v5_strict_title_smoke_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
md = []
md.append("# HZ12T Product All V5 Strict Title Smoke")
md.append("")
md.append(f"- Generated at: {report['ts']}")
md.append(f"- counts: {report['counts']}")
md.append(f"- missing: {missing}")
md.append(f"- stop_exists: {report['stop_exists']}")
md.append(f"- pagination: {report['pagination']}")
md.append(f"- failures: {report['failures']}")
md.append(f"- strict_title: {report['strict_title']}")
md.append("")
Path("docs/ops/DL2_HZ12T_PRODUCT_ALL_V5_STRICT_TITLE_SMOKE.md").write_text("\n".join(md), encoding="utf-8")
print(json.dumps({"report": "reports/hz12t_product_all_v5_strict_title_smoke_latest.json", "counts": report["counts"], "missing": missing, "stop_exists": report["stop_exists"], "pagination": report["pagination"], "failures": report["failures"], "strict_title": report["strict_title"]}, ensure_ascii=False, indent=2))
PY

  echo "===== commit and push report ====="
  git add reports/hz12t_product_all_v5_strict_title_smoke_latest.json docs/ops/DL2_HZ12T_PRODUCT_ALL_V5_STRICT_TITLE_SMOKE.md
  git commit -m "docs: add HZ12T v5 strict-title smoke report" >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

  echo "===== SUMMARY ====="
  echo "STATIC_RC=$STATIC_RC"
  echo "SMOKE_RC=$SMOKE_RC"
  echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "SMOKE_LOG=$SMOKE_LOG"
  echo "REPORT=reports/hz12t_product_all_v5_strict_title_smoke_latest.json"
  git status --short | head -n 60
fi
