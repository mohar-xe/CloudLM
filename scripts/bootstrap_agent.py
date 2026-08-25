"""Register the CloudLM agent with a running TrueForge server via its HTTP API.

Usage:
    uv run python scripts/bootstrap_agent.py            # create/update agent
    uv run python scripts/bootstrap_agent.py --check    # connectivity probe only

Requires the connector named `cloud-fabric` to exist first
(TrueForge UI -> Settings -> Connectors -> Add MCP Server ->
http://127.0.0.1:9000/mcp). See README.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "agents" / "finops-agent.json"
DEFAULT_BASE_URL = "http://localhost:8790"
DEFAULT_MODEL = "openai/gpt-5.2"


def client(base_url: str) -> httpx.Client:
    headers = {}
    token = os.environ.get("TRUEFORGE_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=base_url, timeout=20.0, headers=headers)


def check(base_url: str) -> int:
    with client(base_url) as c:
        try:
            resp = c.get("/api/v1/agents")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[x] TrueForge unreachable at {base_url}: {exc}")
            return 1
    names = (
        [a.get("name") for a in resp.json().get("data", resp.json())]
        if isinstance(resp.json(), dict)
        else []
    )
    print(f"[ok] TrueForge reachable at {base_url}; {len(names)} agent(s): {names}")
    return 0


def bootstrap(base_url: str) -> int:
    raw = SPEC_PATH.read_text()
    model = os.environ.get("TRUEFORGE_MODEL", DEFAULT_MODEL)
    spec = json.loads(raw.replace("__MODEL__", model))
    with client(base_url) as c:
        try:
            resp = c.post("/api/v1/agents", json=spec)
        except httpx.ConnectError as exc:
            print(f"[x] cannot reach TrueForge at {base_url} ({exc}). Is it running?")
            return 1

    if resp.status_code == 409:
        print(f"[ok] agent '{spec['name']}' already exists - leaving it untouched.")
        return 0

    try:
        resp.raise_for_status()
    except httpx.HTTPError:
        body = resp.text[:500]
        if "connector" in body.lower() or "mcp" in body.lower():
            print("[x] server rejected the connector reference.")
            print("    Register it first: Settings -> Connectors -> Add MCP Server ->")
            print("    http://127.0.0.1:9000/mcp   (name it 'cloud-fabric')")
            print(f"    Server said: {body}")
            return 1
        print(f"[x] unexpected error {resp.status_code}: {body}")
        return 1

    data = resp.json().get("data", resp.json())
    agent_id = data.get("id", "?") if isinstance(data, dict) else "?"
    print(f"[ok] agent '{spec['name']}' registered (id={agent_id}) on {base_url}")
    print("     Open the chat UI, pick cloudlm-finops, and try:")
    print("     'Reduce spend by 20% while maintaining 99.9% availability and <200ms p99 latency.'")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("TRUEFORGE_BASE_URL", DEFAULT_BASE_URL)
    )
    parser.add_argument("--check", action="store_true", help="probe connectivity and exit")
    args = parser.parse_args()

    if not SPEC_PATH.exists():
        print(f"[x] spec not found: {SPEC_PATH}")
        return 1
    return check(args.base_url) if args.check else bootstrap(args.base_url)


if __name__ == "__main__":
    sys.exit(main())
