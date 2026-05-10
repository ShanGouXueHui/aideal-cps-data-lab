import json
from pathlib import Path
from datetime import datetime

INPUTS = [
    Path("data/import/hz_jd_union_product_all_promotion_links_latest.jsonl"),
    Path("data/import/hz_jd_union_high_commission_promotion_links_latest.jsonl"),
    Path("data/import/hz_jd_union_guarded_promotion_links_latest.jsonl"),
]
OUT = Path("data/import/hz_jd_union_multi_menu_promotion_links_latest.jsonl")
REPORT = Path("run/hz11_multi_menu_merge_report_latest.json")

def parse_dt(s):
    if not s:
        return datetime.min
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00").replace("+00:00", ""))
    except Exception:
        try:
            return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.min

rows = []
source_counts = {}
for p in INPUTS:
    source_counts[str(p)] = 0
    if not p.exists():
        continue
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            x = json.loads(line)
        except Exception:
            continue
        if x.get("status") == "ok" and x.get("sku") and x.get("short_url"):
            x["_source_file"] = str(p)
            rows.append(x)
            source_counts[str(p)] += 1

by_sku = {}
for x in rows:
    sku = str(x.get("sku")).strip()
    old = by_sku.get(sku)
    if old is None:
        by_sku[sku] = x
        continue
    new_dt = max(parse_dt(x.get("link_created_at")), parse_dt(x.get("ts")))
    old_dt = max(parse_dt(old.get("link_created_at")), parse_dt(old.get("ts")))
    if new_dt >= old_dt:
        by_sku[sku] = x

merged = list(by_sku.values())
merged.sort(key=lambda x: (str(x.get("menu_mode") or ""), str(x.get("sku") or "")))

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    for x in merged:
        y = dict(x)
        y.pop("_source_file", None)
        f.write(json.dumps(y, ensure_ascii=False, sort_keys=True) + "\n")

now = datetime.now()
due_soon = 0
expired = 0
for x in merged:
    due = parse_dt(x.get("refresh_due_at"))
    exp = parse_dt(x.get("link_expire_at"))
    if due != datetime.min and due <= now:
        due_soon += 1
    if exp != datetime.min and exp <= now:
        expired += 1

report = {
    "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
    "inputs": [str(p) for p in INPUTS],
    "source_counts": source_counts,
    "raw_ok_rows": len(rows),
    "dedup_sku": len(merged),
    "target_total": 100000,
    "progress_pct": round(len(merged) / 100000 * 100, 4),
    "refresh_due_or_overdue": due_soon,
    "expired": expired,
    "out": str(OUT),
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
