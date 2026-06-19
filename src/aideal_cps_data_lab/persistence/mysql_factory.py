from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from aideal_cps_data_lab.config import DataLabSettings


def build_connection_factory(settings: DataLabSettings) -> Callable[[], Any]:
    if settings.mysql_default_file:
        option_file = Path(settings.mysql_default_file)
        if not option_file.exists():
            raise RuntimeError("Data Lab MySQL option file does not exist")
        mode = "option_file"
        connection_args: dict[str, Any] = {
            "read_default_file": str(option_file),
            "read_default_group": "client",
            "database": settings.mysql_database,
        }
    elif settings.database_url:
        parsed = urlparse(settings.database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql"}:
            raise ValueError("DATA_LAB_DATABASE_URL must use mysql+pymysql")
        database = parsed.path.strip("/")
        if not parsed.hostname or not parsed.username or not database:
            raise ValueError("DATA_LAB_DATABASE_URL is incomplete")
        mode = "database_url"
        connection_args = {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "user": unquote(parsed.username),
            "passwd": unquote(parsed.password or ""),
            "database": database,
        }
    else:
        raise RuntimeError("no Data Lab MySQL connection source configured")

    def connect() -> Any:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("PyMySQL is required for MySQL execution") from exc

        return pymysql.connect(
            **connection_args,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

    connect.connection_mode = mode  # type: ignore[attr-defined]
    return connect


def build_secret_file_connection_factory(settings: DataLabSettings) -> Callable[[], Any]:
    if not settings.mysql_default_file:
        raise RuntimeError("DATA_LAB_MYSQL_DEFAULT_FILE is empty")
    return build_connection_factory(settings)
