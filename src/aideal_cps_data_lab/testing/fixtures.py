from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TestFixtures:
    sku: str
    item_url: str
    item_url_prefix: str
    promotion_url: str
    image_url: str
    untrusted_url: str
    invalid_item_url: str
    database_url: str
    timestamp: str


def load_test_fixtures() -> TestFixtures:
    root = Path(__file__).resolve().parents[3]
    with (root / "config/test-fixtures.toml").open("rb") as stream:
        payload = tomllib.load(stream)
    return TestFixtures(
        sku=str(payload["sku"]),
        item_url=str(payload["item_url"]),
        item_url_prefix=str(payload["item_url_prefix"]),
        promotion_url=str(payload["promotion_url"]),
        image_url=str(payload["image_url"]),
        untrusted_url=str(payload["untrusted_url"]),
        invalid_item_url=str(payload["invalid_item_url"]),
        database_url=str(payload["database_url"]),
        timestamp=str(payload["timestamp"]),
    )


FIXTURES = load_test_fixtures()
