from typing import Any

from cloud_fabric.providers.synthetic import SyntheticProvider
from cloud_fabric.tools.core import (
    get_billing_summary_response,
    get_metrics_response,
    list_resources_page,
)
from tests.constants import FROZEN_NOW, SMALL_COUNTS


def test_list_envelope_contract(provider: SyntheticProvider, settings: Any) -> None:
    env = list_resources_page(provider, settings, None, "network")
    assert set(env) == {"items", "next_cursor", "total_estimate", "freshness"}
    first = env["items"][0]
    assert {"resource_arn", "resource_type", "domain", "hourly_cost"} <= set(first)
    assert first["domain"] == "network"


def test_metrics_envelope(provider: SyntheticProvider, one_arn: str) -> None:
    out = get_metrics_response(provider, one_arn, window_days=99)
    assert out["window_days"] == 14
    for point in out["points"]:
        assert {"date", "avg_cpu", "avg_memory", "p99_latency_ms", "requests_per_sec"} <= set(point)


def test_billing_envelope_total(provider: SyntheticProvider) -> None:
    out = get_billing_summary_response(provider, period_days=30, default_days=30)
    assert out["monthly_total_usd"] > 0
    services = {i["service"] for i in out["items"]}
    assert {"ec2_instance", "ebs_snapshot", "k8s_pod"} <= services


def test_default_counts_full_scale() -> None:
    p = SyntheticProvider(seed=42, now=FROZEN_NOW)
    _, total = p.page(None, 0, 1)
    assert 10_000 <= total <= 14_000


def test_small_counts_fixture_size(provider: SyntheticProvider) -> None:
    _, total = provider.page(None, 0, 1)
    assert total == sum(SMALL_COUNTS.values())
