from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BatchState:
    processed: int = 0
    linked: int = 0
    unavailable: int = 0
    failed: int = 0
    consecutive_failures: int = 0
    stop_reason: str | None = None
    stop_risk: list[str] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def register_success(self) -> None:
        self.processed += 1
        self.linked += 1
        self.consecutive_failures = 0

    def register_unavailable(self) -> None:
        self.processed += 1
        self.unavailable += 1
        self.consecutive_failures = 0

    def register_failure(self, failure: dict[str, Any], fuse: int) -> None:
        self.processed += 1
        self.failed += 1
        self.consecutive_failures += 1
        self.failures.append(failure)
        reason = str(failure.get("reason") or "")
        if reason.startswith("risk_"):
            self.stop_reason = reason
            self.stop_risk = list(failure.get("risk") or [])
        elif self.consecutive_failures >= fuse:
            self.stop_reason = "item_fail_fuse"
