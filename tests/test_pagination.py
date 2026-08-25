from collections import Counter
from typing import Any

import pytest

from cloud_fabric.config import FabricSettings
from cloud_fabric.providers.synthetic import SyntheticProvider
from cloud_fabric.tools.core import list_resources_page
from fabric_core.cursor import CursorMismatchError


def test_walk_all_pages_no_duplicates_or_gaps(
    provider: SyntheticProvider, settings: FabricSettings
) -> None:
    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        envelope = list_resources_page(provider, settings, cursor, "compute")
        seen.extend(item["resource_arn"] for item in envelope["items"])
        pages += 1
        cursor = envelope["next_cursor"]
        if cursor is None:
            break
        assert pages < 50
    assert len(seen) == envelope["total_estimate"]
    counts = Counter(seen)
    assert all(c == 1 for c in counts.values())


def test_domain_filter_changes_walk(provider: SyntheticProvider, settings: FabricSettings) -> None:
    compute_env = list_resources_page(provider, settings, None, "compute")
    storage_env = list_resources_page(provider, settings, None, "storage")
    assert 0 < compute_env["total_estimate"] < 60
    assert storage_env["total_estimate"] > 0


def test_cursor_from_other_filter_set_is_rejected(
    provider: SyntheticProvider, settings: FabricSettings
) -> None:
    first = list_resources_page(provider, settings, None, None)
    bad_cursor = first["next_cursor"]
    if bad_cursor is None:
        pytest.skip("dataset smaller than one page")
    with pytest.raises(CursorMismatchError):
        list_resources_page(provider, settings, str(bad_cursor), "compute")


def test_freshness_block_shape(provider: SyntheticProvider, settings: FabricSettings) -> None:
    env: dict[str, Any] = list_resources_page(provider, settings, None, None)
    fresh: dict[str, Any] = env["freshness"]
    assert set(fresh) >= {"collected_at", "degraded_domains", "degraded"}
    assert fresh["degraded"] is False
