"""Pure tool logic — envelopes built here are exactly what MCP returns.

Kept free of FastMCP types so tests (and later layers' sandbox scripts) can
call these directly.
"""

from typing import Any

from cloud_fabric.config import FabricSettings
from cloud_fabric.providers import normalize_domain
from fabric_core.cursor import decode_cursor, encode_cursor
from fabric_core.models import BillingSummaryItem, ResourceSnapshot
from fabric_core.providers import FabricProvider, Freshness


def _envelope(
    items: list[ResourceSnapshot],
    next_cursor: str | None,
    total_estimate: int,
    freshness: Freshness,
) -> dict[str, Any]:
    return {
        "items": [json_item(i) for i in items],
        "next_cursor": next_cursor,
        "total_estimate": total_estimate,
        "freshness": {
            "collected_at": freshness.collected_at.isoformat(),
            "degraded_domains": [d.value for d in freshness.degraded_domains],
            "degraded": freshness.degraded,
        },
    }


def json_item(snapshot: ResourceSnapshot) -> dict[str, Any]:
    data = snapshot.model_dump(mode="json")
    return {k: v for k, v in data.items() if v is not None}


def list_resources_page(
    provider: FabricProvider,
    settings: FabricSettings,
    cursor: str | None,
    domain: str | None,
) -> dict[str, Any]:
    d = normalize_domain(domain)
    offset = decode_cursor(cursor, {"domain": domain})
    page_size = min(settings.page_size, settings.max_page_size)
    items, total = provider.page(d, offset, page_size)
    next_offset = offset + len(items)
    next_cursor = encode_cursor(next_offset, {"domain": domain}) if next_offset < total else None
    return _envelope(items, next_cursor, total, provider.freshness())


def get_metrics_response(
    provider: FabricProvider,
    resource_arn: str,
    window_days: int,
    max_window: int = 14,
) -> dict[str, Any]:
    days = max(1, min(window_days, max_window))
    points = provider.metrics(resource_arn, days)
    return {
        "resource_arn": resource_arn,
        "window_days": days,
        "points": [p.model_dump(mode="json") for p in points],
    }


def get_billing_summary_response(
    provider: FabricProvider,
    period_days: int,
    default_days: int,
) -> dict[str, Any]:
    days = max(1, min(period_days, 90))
    items: list[BillingSummaryItem] = provider.billing(days)
    return {
        "period_days": days,
        "items": [i.model_dump(mode="json") for i in items],
        "monthly_total_usd": round(sum(i.monthly_cost_usd for i in items), 2),
    }


__all__ = [
    "get_billing_summary_response",
    "get_metrics_response",
    "json_item",
    "list_resources_page",
]
