from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class DataLabSettings:
    database_url: str = ""
    db_write_enabled: bool = False
    db_dual_write_enabled: bool = False
    publish_enabled: bool = False

    @classmethod
    def from_env(cls) -> "DataLabSettings":
        return cls(
            database_url=os.getenv("DATA_LAB_DATABASE_URL", "").strip(),
            db_write_enabled=_env_bool("DATA_LAB_DB_WRITE_ENABLED", False),
            db_dual_write_enabled=_env_bool("DATA_LAB_DB_DUAL_WRITE_ENABLED", False),
            publish_enabled=_env_bool("DATA_LAB_PUBLISH_ENABLED", False),
        )

    def assert_write_allowed(self) -> None:
        if not self.db_write_enabled:
            raise RuntimeError("DATA_LAB_DB_WRITE_ENABLED is false")
        if not self.database_url:
            raise RuntimeError("DATA_LAB_DATABASE_URL is empty")

    def assert_publish_allowed(self) -> None:
        if not self.publish_enabled:
            raise RuntimeError("DATA_LAB_PUBLISH_ENABLED is false")
