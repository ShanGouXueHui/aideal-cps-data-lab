#!/usr/bin/env bash
# Offline diagnostic only. No JD live traffic, no MySQL connection, no service restart.
# No set -e is used.

cd "${HOME}/projects/aideal-cps-data-lab" || exit 1
mkdir -p logs reports

LOG="logs/commission_data_unittest_diagnostic.log"
REPORT="reports/commission_data_unittest_diagnostic_latest.json"

PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py' -v \
  > "$LOG" 2>&1
TEST_RC=$?

python3 - "$LOG" "$REPORT" "$TEST_RC" <<'PY'
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

log_path = Path(sys.argv[1])
report_path = Path(sys.argv[2])
test_rc = int(sys.argv[3])
text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
lines = text.splitlines()
failed_tests = []
for line in lines:
    match = re.match(r"^(test\S+ \([^)]*\)) \.\.\. (FAIL|ERROR)$", line.strip())
    if match:
        failed_tests.append({"test": match.group(1), "result": match.group(2)})

sections = []
index = 0
while index < len(lines):
    line = lines[index]
    if line.startswith("FAIL: ") or line.startswith("ERROR: "):
        current = [line]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            if next_line.startswith("FAIL: ") or next_line.startswith("ERROR: "):
                break
            if next_line.startswith("Ran "):
                break
            current.append(next_line)
            index += 1
        sections.append("\n".join(current).strip())
        continue
    index += 1

summary_lines = [line for line in lines[-40:] if line.strip()]
payload = {
    "schema_version": "aideal-commission-test-diagnostic/v1",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "test_rc": test_rc,
    "failed_test_count": len(failed_tests),
    "failed_tests": failed_tests,
    "failure_sections": sections[:10],
    "summary_tail": summary_lines,
    "ok": test_rc == 0,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
tmp = report_path.with_suffix(report_path.suffix + ".tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
tmp.replace(report_path)
PY
PARSE_RC=$?

git add "$REPORT"
if git diff --cached --quiet; then
  COMMIT_STATUS="no_change"
else
  git commit -m "reports: publish commission test diagnostics"
  COMMIT_RC=$?
  if [ "$COMMIT_RC" != "0" ]; then
    echo "===== SUMMARY ====="
    echo "STATUS=FAIL"
    echo "STEP=commit"
    echo "TEST_RC=$TEST_RC"
    echo "PARSE_RC=$PARSE_RC"
    echo "COMMIT_RC=$COMMIT_RC"
    exit 1
  fi
  COMMIT_STATUS="committed"
fi

GIT_TERMINAL_PROMPT=0 git fetch origin main
FETCH_RC=$?
if [ "$FETCH_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git rebase origin/main
  REBASE_RC=$?
else
  REBASE_RC=99
fi
if [ "$FETCH_RC" = "0" ] && [ "$REBASE_RC" = "0" ]; then
  GIT_TERMINAL_PROMPT=0 git push origin HEAD:main
  PUSH_RC=$?
else
  PUSH_RC=99
fi

FAILED_COUNT="$(python3 - "$REPORT" <<'PY'
import json,sys
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(x.get('failed_test_count') or 0)
PY
)"
LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"
REMOTE_HEAD="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
STATUS=PASS
if [ "$PARSE_RC" != "0" ] || [ "$FETCH_RC" != "0" ] || [ "$REBASE_RC" != "0" ] || [ "$PUSH_RC" != "0" ] || [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  STATUS=FAIL
fi

echo "===== SUMMARY ====="
echo "STATUS=$STATUS"
echo "TEST_RC=$TEST_RC"
echo "PARSE_RC=$PARSE_RC"
echo "FAILED_TEST_COUNT=$FAILED_COUNT"
echo "COMMIT_STATUS=$COMMIT_STATUS"
echo "FETCH_RC=$FETCH_RC"
echo "REBASE_RC=$REBASE_RC"
echo "PUSH_RC=$PUSH_RC"
echo "LOCAL_HEAD=$LOCAL_HEAD"
echo "REMOTE_HEAD=$REMOTE_HEAD"

[ "$STATUS" = PASS ]
