from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .repository import successful_skus, unavailable_skus


@dataclass(frozen=True, slots=True)
class TerminalSkuState:
    linked: set[str]
    unavailable: set[str]

    @property
    def overlap(self) -> set[str]:
        return self.linked & self.unavailable

    def require_disjoint(self) -> None:
        overlap = sorted(self.overlap)
        if overlap:
            sample = ",".join(overlap[:10])
            raise ValueError(
                f"linked_unavailable_overlap:{len(overlap)}:{sample}"
            )


def load_terminal_state(
    linked_path: Path,
    unavailable_path: Path,
) -> TerminalSkuState:
    state = TerminalSkuState(
        linked=successful_skus(linked_path),
        unavailable=unavailable_skus(unavailable_path),
    )
    state.require_disjoint()
    return state
