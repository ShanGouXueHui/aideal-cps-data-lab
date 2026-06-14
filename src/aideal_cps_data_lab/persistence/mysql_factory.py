from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from aideal_cps_data_lab.config import DataLabSettings


def build_secret_file_connection_factory(settings: DataLabSettings) -> Callable[[], Any]:
    if not settings.mysql_default_file:
        raise RuntimeError("DATA_LAB_MYSQL_DEFAULT_FILE is empty")
    option_file = Path(settings.mysql_default_file)
    if not option_file.exists():
        raise RuntimeError("Data Lab MySQL option file does not exist")

    def connect() -> Any:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("PyMySQL is required for MySQL execution") from exc

        return pymysql.connect(
            read_default_file=str(option_file),
            read_default_group="client",
            host="127.0.0.1",
            port=3306,
            database=settings.mysql_database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

    return connect
