"""cloud-fabric MCP server entrypoint (D-005: streamable HTTP on localhost)."""

import contextlib
from collections.abc import Iterator

from mcp.server.fastmcp import FastMCP

from cloud_fabric.config import FabricSettings
from cloud_fabric.providers import get_provider
from cloud_fabric.tools.register import register_tools

SERVER_INSTRUCTIONS = (
    "Read-only multi-cloud data fabric for CloudLM. "
    "All listing tools are cursored: pass next_cursor back until it is null before summarizing. "
    "Respect freshness on every response; if a domain is degraded, say so in the report."
)


@contextlib.contextmanager
def build_server(settings: FabricSettings | None = None) -> Iterator[FastMCP]:
    settings = settings or FabricSettings()
    provider = get_provider(settings)
    mcp = FastMCP(
        "cloud-fabric",
        instructions=SERVER_INSTRUCTIONS,
        host=settings.host,
        port=settings.port,
    )
    register_tools(mcp, provider, settings)
    yield mcp


def main() -> None:
    settings = FabricSettings()
    with build_server(settings) as mcp:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
