from cloud_fabric.providers.synthetic import SyntheticProvider
from tests.constants import FROZEN_NOW, SMALL_COUNTS


def _checksum(p: SyntheticProvider) -> str:
    import hashlib
    import json

    items, total = p.page(None, 0, 10_000)
    payload = json.dumps([i.model_dump(mode="json") for i in items], sort_keys=True)
    assert total == len(items)
    return hashlib.sha256(payload.encode()).hexdigest()


def test_same_seed_identical_dataset() -> None:
    a = SyntheticProvider(seed=7, counts=SMALL_COUNTS, now=FROZEN_NOW)
    b = SyntheticProvider(seed=7, counts=SMALL_COUNTS, now=FROZEN_NOW)
    assert _checksum(a) == _checksum(b)


def test_different_seed_different_dataset() -> None:
    a = SyntheticProvider(seed=7, counts=SMALL_COUNTS, now=FROZEN_NOW)
    b = SyntheticProvider(seed=8, counts=SMALL_COUNTS, now=FROZEN_NOW)
    assert _checksum(a) != _checksum(b)


def test_degraded_flag_propagates() -> None:
    from fabric_core.models import Domain

    p = SyntheticProvider(
        seed=1, counts=SMALL_COUNTS, now=FROZEN_NOW, degraded_domains=(Domain.K8S,)
    )
    fresh = p.freshness()
    assert fresh.degraded and fresh.degraded_domains == [Domain.K8S]
    pods, _ = p.page(Domain.K8S, 0, 5)
    assert all(r.status.value == "degraded" for r in pods)


def test_latency_correlates_with_cpu() -> None:
    p = SyntheticProvider(
        seed=3,
        counts={"compute": 300, "volumes": 0, "snapshots": 0, "pods": 0, "network": 0},
        now=FROZEN_NOW,
    )
    items, _ = p.page(None, 0, 300)
    idle = [
        r.p99_latency_ms
        for r in items
        if r.avg_cpu is not None and r.avg_cpu < 5 and r.p99_latency_ms is not None
    ]
    hot = [
        r.p99_latency_ms
        for r in items
        if r.avg_cpu is not None and r.avg_cpu > 80 and r.p99_latency_ms is not None
    ]
    assert idle and hot
    assert sum(hot) / len(hot) > 4 * (sum(idle) / len(idle))


def test_metrics_series_shape(provider: SyntheticProvider, one_arn: str) -> None:
    points = provider.metrics(one_arn, days=14)
    if not points:
        return
    assert len(points) == 14
    dates = [pt.date for pt in points]
    assert dates == sorted(dates)


def test_billing_totals_positive(provider: SyntheticProvider) -> None:
    items = provider.billing(30)
    assert items
    assert all(i.monthly_cost_usd > 0 for i in items)
