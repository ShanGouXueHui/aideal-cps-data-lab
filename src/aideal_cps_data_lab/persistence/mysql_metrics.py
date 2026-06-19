from __future__ import annotations

from collections.abc import Callable
from typing import Any

ConnectionFactory = Callable[[], Any]

count_products_statement = "SELECT COUNT(*) AS value FROM commission_products"
count_duplicates_statement = (
    "SELECT COUNT(*) AS value FROM ("
    "SELECT jd_sku_id FROM commission_products "
    "GROUP BY jd_sku_id HAVING COUNT(*) > 1"
    ") AS duplicate_rows"
)


def scalar(connection_factory: ConnectionFactory, statement: str) -> int:
    connection = connection_factory()
    cursor = connection.cursor()
    try:
        cursor.execute(statement)
        row = cursor.fetchone() or {}
        return int(row.get("value") or 0)
    finally:
        cursor.close()
        connection.close()


def count_products(connection_factory: ConnectionFactory) -> int:
    return scalar(connection_factory, count_products_statement)


def count_duplicates(connection_factory: ConnectionFactory) -> int:
    return scalar(connection_factory, count_duplicates_statement)
