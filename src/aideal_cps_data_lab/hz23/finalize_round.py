from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.hz24.repository import load_json, read_jsonl
from aideal_cps_data_lab.hz24.settings import HZ24Settings, load_settings

from .finalize_candidates import build_candidates, deduplicate_source
from .finalize_io import (
    FinalizePaths,
    atomic_text,
    choose_source,
    json_text,
    timestamp,
    update_catalog,
)
from .finalize_manifest import build_manifest, gate_state


def export_candidates(
    path: Path,
    rows: list[dict[str, Any]],
) -> str:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    atomic_text(path, text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_seen(path: Path) -> set[str]:
    return {
        str(row.get("sku"))
        for row in read_jsonl(path)
        if str(row.get("sku") or "").isdigit()
    }


def run_finalize(
    round_id: str,
    paths: FinalizePaths,
    settings: HZ24Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings()
    generated_at = timestamp()
    index = load_json(paths.index) or {"version": 1, "products": {}}
    seen = load_seen(paths.seen)
    products = update_catalog(index, seen, round_id, generated_at)
    atomic_text(paths.index, json_text(index))

    source = choose_source(paths.source_candidates)
    dedup, source_duplicates, unsafe_count, untrusted_count = deduplicate_source(
        read_jsonl(source) if source else [], settings
    )
    eligible, rejected = build_candidates(
        dedup,
        products,
        round_id,
        generated_at,
        settings,
        unsafe_count,
        untrusted_count,
    )
    export_sha = export_candidates(paths.export, eligible)
    summary = load_json(paths.summary)
    state = load_json(paths.observer_state)
    checks, values = gate_state(
        summary,
        state,
        source is not None,
        eligible,
        unsafe_count,
        untrusted_count,
        export_sha,
        generated_at,
    )
    manifest = build_manifest(
        round_id,
        generated_at,
        source,
        paths,
        eligible,
        dedup,
        source_duplicates,
        products,
        seen,
        rejected,
        summary,
        checks,
        values,
        export_sha,
    )
    atomic_text(paths.manifest, json_text(manifest))
    return manifest


def default_paths(round_id: str, summary: Path) -> FinalizePaths:
    return FinalizePaths(
        summary=summary,
        index=Path("data/state/hz23_catalog_index.json"),
        seen=Path(f"data/state/hz23_round_{round_id}_seen.jsonl"),
        observer_state=Path("run/hz23_observer_state.json"),
        source_candidates=(
            Path("data/import/hz_jd_union_all_product_full_links_latest.jsonl"),
            Path("data/import/hz_jd_union_product_all_full_links_latest.jsonl"),
        ),
        export=Path("data/export/aideal_cps_products_commercial_candidate_latest.jsonl"),
        manifest=Path("data/export/aideal_cps_products_commercial_candidate_manifest.json"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("round_id")
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    manifest = run_finalize(
        args.round_id,
        default_paths(args.round_id, args.summary),
    )
    print(
        json.dumps(
            {"event": "HZ23_FINALIZE_DONE", **manifest},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if manifest.get("candidate_integrity_ready") else 1
