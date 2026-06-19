from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .browser_contract import DISABLED_CARD_CLASS, SOLD_OUT_TEXT


@dataclass(frozen=True, slots=True)
class SoldOutEvidence:
    sku: str
    tab: str
    item_url: str
    root_text: str


def evidence_from_failure(failure: dict[str, Any]) -> SoldOutEvidence | None:
    click = failure.get("click") or {}
    hit = click.get("hit") or {}
    matched = ((click.get("mark") or {}).get("matched") or {})
    root_text = str(matched.get("rootText") or "")
    sku = str(failure.get("sku") or click.get("sku") or "").strip()
    tab = str(failure.get("tab") or "").strip()
    if not sku or not tab:
        return None
    if DISABLED_CARD_CLASS not in str(hit.get("cls") or ""):
        return None
    if SOLD_OUT_TEXT not in root_text:
        return None
    return SoldOutEvidence(
        sku=sku,
        tab=tab,
        item_url=str(matched.get("itemUrl") or "").strip(),
        root_text=root_text,
    )


def collect_evidence(
    report: dict[str, Any],
) -> tuple[list[SoldOutEvidence], int]:
    indexed: dict[str, SoldOutEvidence] = {}
    duplicate_count = 0
    for failure in report.get("failures") or []:
        if not isinstance(failure, dict):
            continue
        evidence = evidence_from_failure(failure)
        if evidence is None:
            continue
        if evidence.sku in indexed:
            duplicate_count += 1
        indexed[evidence.sku] = evidence
    return [indexed[sku] for sku in sorted(indexed)], duplicate_count


def evidence_checks(
    evidence: list[SoldOutEvidence],
    queue: dict[str, dict[str, Any]],
    linked_skus: set[str],
    expected_count: int,
    duplicate_count: int,
) -> dict[str, bool]:
    queue_skus = set(queue)
    return {
        "evidence_nonempty": bool(evidence),
        "evidence_duplicate_zero": duplicate_count == 0,
        "evidence_count_matches": len(evidence) == expected_count,
        "all_evidence_in_queue": all(item.sku in queue_skus for item in evidence),
        "none_already_linked": all(item.sku not in linked_skus for item in evidence),
        "source_tabs_match_queue": all(
            item.tab in set(queue.get(item.sku, {}).get("source_tabs") or [])
            for item in evidence
        ),
    }
