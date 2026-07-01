#!/usr/bin/env bash
# Audit legacy source JSON stream format without printing the full source file.
# Does not start collectors, browser jobs, MySQL jobs, or downstream sync.
# No set -e is used.

PROJECT_DIR="${HOME}/projects/aideal-cps-data-lab"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs reports run data/import data/export

REPORT="reports/source_stream_format_audit_latest.json"
SOURCE_A="data/import/hz_jd_union_all_product_full_links_latest.jsonl"
SOURCE_B="data/import/hz_jd_union_product_all_full_links_latest.jsonl"

python3 - "$REPORT" "$SOURCE_A" "$SOURCE_B" <<'PY'
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from json import JSONDecoder
from pathlib import Path

report=Path(sys.argv[1])
sources=[Path(sys.argv[2]), Path(sys.argv[3])]

def safe_window(text, pos, width=160):
    start=max(0,pos-width)
    end=min(len(text),pos+width)
    return text[start:end].encode('unicode_escape').decode('ascii', errors='replace')

def audit(path: Path):
    out={'path':str(path),'exists':path.exists()}
    if not path.exists():
        return out
    raw=path.read_bytes()
    text=raw.decode('utf-8', errors='replace')
    out.update({
        'bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(),
        'nonblank_lines':sum(1 for line in text.splitlines() if line.strip()),
        'char_counts':{
            'open_brace':text.count('{'),
            'close_brace':text.count('}'),
            'object_join_brace_brace':text.count('}{'),
            'object_join_comma_brace':text.count('},{'),
            'newline_brace':text.count('\n{'),
            'nul':text.count('\x00'),
        },
        'prefix':text[:500].encode('unicode_escape').decode('ascii', errors='replace'),
    })
    decoder=JSONDecoder()
    positions=[]
    index=0
    parsed=0
    stops=[]
    length=len(text)
    while index < length and parsed < 20:
        while index < length and (text[index].isspace() or text[index] == ','):
            index += 1
        if index >= length:
            break
        try:
            value,end=decoder.raw_decode(text,index)
            parsed += 1
            positions.append({'index':parsed,'start':index,'end':end,'keys':sorted(value.keys())[:20] if isinstance(value,dict) else [],'sku':value.get('sku') if isinstance(value,dict) else None,'status':value.get('status') if isinstance(value,dict) else None})
            index=end
        except Exception as exc:
            next_brace=text.find('{', index+1)
            stops.append({'pos':index,'char':text[index:index+1].encode('unicode_escape').decode('ascii'),'ord':ord(text[index]) if index < length else None,'error':repr(exc),'next_brace':next_brace,'window':safe_window(text,index)})
            if next_brace < 0:
                break
            index=next_brace
    out['first_20_decode']=positions
    out['decode_stop_samples']=stops[:10]
    out['legacy_decoder_first_20_count']=parsed
    sample_chars=[]
    for marker in ('}{','},{','\n{'):
        pos=text.find(marker)
        if pos >= 0:
            sample_chars.append({'marker':marker,'pos':pos,'window':safe_window(text,pos)})
    out['marker_samples']=sample_chars
    return out

payload={
  'schema_version':'source-stream-format-audit/v1',
  'generated_at':datetime.utcnow().isoformat(timespec='seconds')+'Z',
  'sources':{str(path):audit(path) for path in sources},
}
report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(f'SOURCE_STREAM_AUDIT_REPORT={report}')
for path, data in payload['sources'].items():
    counts=data.get('char_counts') or {}
    print(f'SOURCE_STREAM[{path}]=bytes:{data.get("bytes")},lines:{data.get("nonblank_lines")},brace_brace:{counts.get("object_join_brace_brace")},comma_brace:{counts.get("object_join_comma_brace")},newline_brace:{counts.get("newline_brace")},first20:{data.get("legacy_decoder_first_20_count")},sha:{data.get("sha256")}')
PY
AUDIT_RC=$?

bash scripts/git_publish_files_via_worktree.sh \
  "reports: publish source stream format audit" \
  "$REPORT" \
  > logs/source_stream_format_audit_publish.log 2>&1
PUBLISH_RC=$?
git fetch origin runtime-evidence >/dev/null 2>&1 || true

echo "AUDIT_RC=$AUDIT_RC"
echo "PUBLISH_RC=$PUBLISH_RC"
echo "RUNTIME_EVIDENCE_HEAD=$(git rev-parse --short origin/runtime-evidence 2>/dev/null)"
