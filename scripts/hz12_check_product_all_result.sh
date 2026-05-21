#!/usr/bin/env bash
# HZ12 product_all result checker.
# Usage:
#   cd ~/projects/aideal-cps-data-lab || exit 1
#   git fetch origin main && git rebase origin/main
#   bash scripts/hz12_check_product_all_result.sh
#
# This script creates a compact report under reports/ and docs/ops/, commits it,
# and pushes it to GitHub. It does not close Chrome and does not modify secrets.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p reports docs/ops logs run data/import backups

LOG_GLOB="logs/hz12_product_all_full_v3_overnight_*.log"
LATEST_LOG="$(ls -t $LOG_GLOB 2>/dev/null | head -n 1 || true)"
REPORT_JSON="reports/hz12_product_all_full_check_latest.json"
REPORT_MD="docs/ops/DL2_HZ12_PRODUCT_ALL_FULL_CHECK.md"

python3 - <<PY
import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

latest_log = "${LATEST_LOG}"
report_json = Path("${REPORT_JSON}")
report_md = Path("${REPORT_MD}")

files = {
    "latest": "data/import/hz_jd_union_product_all_full_links_latest.jsonl",
    "state": "run/hz12_product_all_full_state.json",
    "runtime_report": "run/hz12_product_all_full_report_latest.json",
    "stop": "run/hz12_product_all_STOP_REQUIRED.json",
}


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
    if not p.exists():
        return rows
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


def tail_events(path, event_names, limit=160):
    p = Path(path)
    out = []
    if not path or not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get("event") in event_names:
            out.append(x)
    return out[-limit:]


def pgrep(pattern):
    try:
        r = subprocess.run(["pgrep", "-af", pattern], text=True, capture_output=True)
        return [x for x in r.stdout.splitlines() if x.strip()]
    except Exception as e:
        return [f"pgrep_error:{e!r}"]

rows = read_jsonl(files["latest"])
ok = [x for x in rows if x.get("status") == "ok" and x.get("short_url")]
skus = [str(x.get("sku") or "").strip() for x in ok if x.get("sku")]
dedup_skus = sorted(set(skus))
non_numeric = [x for x in ok if not str(x.get("sku") or "").isdigit()]

missing = {
    "title": sum(1 for x in ok if not x.get("title")),
    "image_url": sum(1 for x in ok if not x.get("image_url")),
    "item_url": sum(1 for x in ok if not x.get("item_url")),
    "price": sum(1 for x in ok if not x.get("price")),
    "commission_rate": sum(1 for x in ok if not x.get("commission_rate")),
    "estimated_income": sum(1 for x in ok if not x.get("estimated_income")),
    "short_url": sum(1 for x in ok if not x.get("short_url")),
    "long_url": sum(1 for x in ok if not x.get("long_url")),
    "qr_url": sum(1 for x in ok if not x.get("qr_url")),
    "jd_command": sum(1 for x in ok if not x.get("jd_command")),
    "link_created_at": sum(1 for x in ok if not x.get("link_created_at")),
    "link_expire_at": sum(1 for x in ok if not x.get("link_expire_at")),
    "refresh_due_at": sum(1 for x in ok if not x.get("refresh_due_at")),
}

first_ts = None
last_ts = None
for x in ok:
    dt = parse_dt(x.get("link_created_at") or x.get("ts"))
    if dt:
        first_ts = dt if first_ts is None or dt < first_ts else first_ts
        last_ts = dt if last_ts is None or dt > last_ts else last_ts
runtime_hours = None
per_hour = None
per_day = None
if first_ts and last_ts and last_ts > first_ts:
    runtime_hours = max((last_ts - first_ts).total_seconds() / 3600, 1/60)
    per_hour = len(ok) / runtime_hours
    per_day = per_hour * 24

pages = sorted({int(x.get("page_no")) for x in ok if str(x.get("page_no") or "").isdigit()})
page_counts = {}
for x in ok:
    p = str(x.get("page_no") or "")
    page_counts[p] = page_counts.get(p, 0) + 1

price_values = []
commission_values = []
for x in ok:
    try:
        price_values.append(float(str(x.get("price") or "").replace("￥", "").replace(",", "")))
    except Exception:
        pass
    try:
        commission_values.append(float(str(x.get("estimated_income") or "").replace("￥", "").replace(",", "")))
    except Exception:
        pass

suspicious = []
for x in ok:
    title = str(x.get("title") or "")
    if len(title.strip()) < 6:
        suspicious.append({"sku": x.get("sku"), "reason": "short_title", "title": title, "short_url": x.get("short_url")})
    if str(x.get("sku") or "") in title:
        suspicious.append({"sku": x.get("sku"), "reason": "sku_in_title", "title": title[:120], "short_url": x.get("short_url")})

runtime_report = read_json(files["runtime_report"])
state = read_json(files["state"])
stop = read_json(files["stop"])
events = tail_events(latest_log, {"HZ12_PRODUCT_ALL_FULL_START", "TITLE_ENRICHED_CANDIDATES_V3", "PAGE_CANDIDATES", "ITEM_OK", "ITEM_FAIL", "STOP_REQUIRED", "FULL_CYCLE_DONE", "TARGET_TOTAL_REACHED", "SLEEP_REFRESH_NOT_DUE", "EMPTY_PAGE_LIMIT_REACHED"}, 180)

stop_exists = Path(files["stop"]).exists()
worker_processes = pgrep("hz12_product_all_full_collector|chrome.*19228|chrome.*19229")

# Conservative commercial-readiness judgment.
ready_for_dry_run = (
    len(ok) >= 100 and
    len(non_numeric) == 0 and
    not stop_exists and
    missing.get("title", 0) == 0 and
    missing.get("short_url", 0) == 0 and
    missing.get("long_url", 0) == 0 and
    missing.get("image_url", 0) == 0 and
    missing.get("price", 0) == 0 and
    missing.get("commission_rate", 0) == 0 and
    missing.get("estimated_income", 0) == 0
)

report = {
    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "phase": "HZ12 product_all full result check",
    "head": subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True).stdout.strip(),
    "files": files,
    "latest_log": latest_log,
    "processes": worker_processes,
    "stop_exists": stop_exists,
    "stop": stop,
    "counts": {
        "rows": len(rows),
        "ok": len(ok),
        "dedup_sku": len(dedup_skus),
        "non_numeric": len(non_numeric),
        "duplicate_ok_rows": len(ok) - len(dedup_skus),
        "page_count": len(pages),
        "first_page": pages[0] if pages else None,
        "last_page": pages[-1] if pages else None,
    },
    "missing": missing,
    "rates": {
        "title_complete_rate": round((len(ok) - missing["title"]) / len(ok), 4) if ok else None,
        "image_complete_rate": round((len(ok) - missing["image_url"]) / len(ok), 4) if ok else None,
        "price_complete_rate": round((len(ok) - missing["price"]) / len(ok), 4) if ok else None,
        "commission_complete_rate": round((len(ok) - missing["commission_rate"]) / len(ok), 4) if ok else None,
        "link_complete_rate": round((len(ok) - missing["long_url"]) / len(ok), 4) if ok else None,
    },
    "throughput": {
        "first_ts": first_ts.isoformat(timespec="seconds") if first_ts else None,
        "last_ts": last_ts.isoformat(timespec="seconds") if last_ts else None,
        "runtime_hours_est": round(runtime_hours, 3) if runtime_hours else None,
        "estimated_ok_per_hour": round(per_hour, 2) if per_hour else None,
        "estimated_ok_per_day": round(per_day, 2) if per_day else None,
        "estimated_days_to_4000": round(4000 / per_day, 2) if per_day else None,
    },
    "page_counts_sample": {k: page_counts[k] for k in sorted(page_counts, key=lambda v: int(v) if v.isdigit() else 999999)[:30]},
    "value_ranges": {
        "price_min": min(price_values) if price_values else None,
        "price_max": max(price_values) if price_values else None,
        "estimated_income_min": min(commission_values) if commission_values else None,
        "estimated_income_max": max(commission_values) if commission_values else None,
    },
    "suspicious_sample": suspicious[:30],
    "sample_last_20": [
        {
            "page_no": x.get("page_no"),
            "sku": x.get("sku"),
            "short_url": x.get("short_url"),
            "title": (x.get("title") or "")[:120],
            "price": x.get("price"),
            "commission_rate": x.get("commission_rate"),
            "estimated_income": x.get("estimated_income"),
            "refresh_due_at": x.get("refresh_due_at"),
        }
        for x in ok[-20:]
    ],
    "runtime_report": runtime_report,
    "state": state,
    "events_tail": events,
    "commercial_readiness": {
        "ready_for_production_import": False,
        "ready_for_dry_run_import": ready_for_dry_run,
        "reason": "Production import requires full-run completion and dry-run importer validation. This check only assesses collected JSONL quality."
    },
    "next_decision": "If no STOP and quality is good, continue collection until roughly 4000 SKU. If STOP exists, inspect stop reason before restart."
}

report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

md = []
md.append("# HZ12 Product All Full Check")
md.append("")
md.append(f"- Generated at: {report['ts']}")
md.append(f"- STOP exists: {stop_exists}")
md.append(f"- rows={len(rows)}, ok={len(ok)}, dedup_sku={len(dedup_skus)}, non_numeric={len(non_numeric)}")
md.append(f"- pages={len(pages)}, first_page={report['counts']['first_page']}, last_page={report['counts']['last_page']}")
md.append(f"- missing={missing}")
md.append(f"- throughput={report['throughput']}")
md.append(f"- ready_for_dry_run_import={ready_for_dry_run}")
md.append("")
md.append("## Next decision")
md.append("")
md.append(report["next_decision"])
md.append("")
report_md.write_text("\n".join(md), encoding="utf-8")

print(json.dumps({
    "report": str(report_json),
    "rows": len(rows),
    "ok": len(ok),
    "dedup_sku": len(dedup_skus),
    "non_numeric": len(non_numeric),
    "stop_exists": stop_exists,
    "missing": missing,
    "last_page": report['counts']['last_page'],
    "ready_for_dry_run_import": ready_for_dry_run,
}, ensure_ascii=False, indent=2))
PY

# Commit/push report. Avoid failing if there is nothing new.
git add "$REPORT_JSON" "$REPORT_MD"
git commit -m "docs: add HZ12 product all full check report" >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git fetch origin main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git rebase origin/main >/dev/null 2>&1 || true
GIT_TERMINAL_PROMPT=0 git push origin HEAD:main >/dev/null 2>&1 || true

echo "===== SUMMARY ====="
echo "HEAD=$(git rev-parse --short HEAD 2>/dev/null || true)"
echo "REPORT=$REPORT_JSON"
echo "LATEST_LOG=$LATEST_LOG"
git status --short | head -n 60
