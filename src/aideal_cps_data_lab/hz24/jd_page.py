from __future__ import annotations

from .settings import HZ24Settings


class JDPageAdapter:
    def __init__(self, settings: HZ24Settings) -> None:
        self.settings = settings
