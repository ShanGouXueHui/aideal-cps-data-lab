from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    category: str
    path: str
    line: int
    symbol: str
    detail: str


@dataclass(frozen=True, slots=True)
class FunctionFingerprint:
    name: str
    path: str
    line: int
    line_count: int
    digest: str
