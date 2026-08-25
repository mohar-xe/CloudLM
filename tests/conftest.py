"""Shared fixtures: tiny dataset + fast settings so the suite stays under a few seconds."""

from collections.abc import Iterator

import pytest

from cloud_fabric.config import FabricSettings
from cloud_fabric.providers.synthetic import SyntheticProvider
from tests.constants import FROZEN_NOW, SMALL_COUNTS


@pytest.fixture()
def settings() -> FabricSettings:
    return FabricSettings(page_size=20)


@pytest.fixture()
def provider() -> SyntheticProvider:
    return SyntheticProvider(seed=42, counts=SMALL_COUNTS, now=FROZEN_NOW)


@pytest.fixture()
def one_arn(provider: SyntheticProvider) -> Iterator[str]:
    items, _ = provider.page(None, 0, 1)
    yield items[0].resource_arn
