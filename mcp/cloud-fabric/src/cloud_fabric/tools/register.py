"""FastMCP tool registration — thin wrappers around tools/core.py."""

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from cloud_fabric.config import FabricSettings
from cloud_fabric.providers import FabricProvider
from cloud_fabric.tools.core import (
    get_billing_summary_response,
    get_metrics_response,
    list_resources_page,
)

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def register_tools(mcp: FastMCP, provider: FabricProvider, settings: FabricSettings) -> None:
    @mcp.tool(annotations=_READ_ONLY)
    def list_resources(cursor: str | None = None, domain: str | None = None) -> dict[str, Any]:
        """Page through normalized cloud resources.

        Args:
            cursor: Opaque cursor from a previous call's next_cursor. Omit for the first page.
            domain: Optional filter: compute | storage | k8s | network. Keep constant while walking.
        """
        return list_resources_page(provider, settings, cursor, domain)

    @mcp.tool(annotations=_READ_ONLY)
    def get_metrics(resource_arn: str, window_days: int = 14) -> dict[str, Any]:
        """Daily CPU/memory/p99-latency/request series for one resource (max 14 days).

        Args:
            resource_arn: Exact arn from list_resources items.
            window_days: How many days back to fetch, capped at 14.
        """
        return get_metrics_response(provider, resource_arn, window_days)

    @mcp.tool(annotations=_READ_ONLY)
    def get_billing_summary(period_days: int = 30) -> dict[str, Any]:
        """Monthly cost rollup grouped by domain and service, plus grand total.

        Args:
            period_days: Aggregation window in days, 1-90.
        """
        return get_billing_summary_response(provider, period_days, settings.billing_days)
