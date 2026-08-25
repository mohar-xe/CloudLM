# CloudLM

**An approval-gated cloud FinOps agent built on [TrueForge](https://github.com/truefoundry/trueforge)** — The Agent Harness Hackathon, Aug 24–30 2026.

> Goal: *"Reduce spend by 20% while maintaining 99.9% availability and <200ms p99 latency."*

CloudLM parses that goal into immutable guardrails, reads your cloud through a
read-only MCP data fabric, detects waste by running analysis code in the
TrueForge sandbox, simulates right-sizing against your latency SLO, and — only
after a human approves an itemized manifest — applies Terraform changes with a
one-command rollback.

**Status:** `layer-1` — read-only FinOps analyst. Roadmap: [PLAN.md](PLAN.md).

---

## How it works (Layer 1)

```
you ──> TrueForge harness (finops agent spec)
          ├── ask_user_question      → "Prod or Dev?"        (Gate 1)
          ├── cloud-fabric MCP       → cursored, paginated reads of ~12k
          │                            normalized ResourceSnapshots
          └── Generative UI tables   → spend report w/ guardrail block
```

Every response repeats your guardrails verbatim and flags any degraded data
domain. Read-only: nothing is modified at this layer. Full execution flow:
[FLOW.md](FLOW.md). Every design decision and its reasoning:
[DECISION.md](DECISION.md).

## Quickstart

Prereqs: Python 3.11+ ([uv](https://docs.astral.sh/uv/)), Node 18+, any model API key.

```bash
# 1 · install workspace (fabric-core + cloud-fabric)
uv sync --all-packages --group dev

# 2 · run the data fabric MCP server (terminal A)
uv run cloud-fabric            # serves http://127.0.0.1:9000/mcp

# 3 · run TrueForge (terminal B)
npx @truefoundry/trueforge     # UI on http://localhost:8790

# 4 · register the fabric as a connector (one time)
#    TrueForge UI -> Settings -> Connectors -> Add MCP Server
#    URL:   http://127.0.0.1:9000/mcp
#    Name:  cloud-fabric

# 5 · create the agent via TrueForge's HTTP API
uv run python scripts/bootstrap_agent.py

# 6 · chat: pick the `cloudlm-finops` agent and paste the goal above
```

Switch providers / tune the dataset with env vars — see [.env.example](.env.example).
The default provider is a deterministic synthetic fabric (~12k resources across
compute/storage/k8s/network with coherent cost-metric correlations), so the repo
runs on any machine with zero cloud credentials. Point it at your own AWS
account read-only with `FABRIC_PROVIDER=aws` (`uv sync --all-packages --extra aws`).

### Simulate partial collection failure

```bash
FABRIC_DEGRADED_DOMAINS=k8s uv run cloud-fabric
```

The agent's reports must then disclose stale domains (flow Step 2.5).

## Development

```bash
uv run pytest -q        # tests
uv run ruff check .     # lint
uv run mypy packages/fabric-core/src mcp/cloud-fabric/src tests
```

Repo layout:

```
mcp/cloud-fabric/     FastMCP server: tools + synthetic/aws providers
packages/fabric-core/ shared contracts: models, cursors, provider protocol
agents/               finops-agent spec (registered via scripts/bootstrap_agent.py)
scripts/              bootstrap + ops helpers
docs/, PLAN.md, DECISION.md, FLOW.md
```

## Qodo Code Review Evidence

<!-- Filled in after the first reviewed PR lands. Required by hackathon rules:
     link to representative merged PR, what Qodo surfaced, decisions taken,
     follow-up review against final code. -->

## Security notes

- No credentials are required to run the default stack; `.env` is gitignored.
- The AWS adapter expects a **read-only** IAM identity you own; keys stay out of
  the repo and out of demo recordings.
- All fabric tools are annotated `readOnlyHint`; destructive capabilities arrive
  in later layers behind harness-enforced approval gates.

AI-assisted development is used in this project and disclosed per hackathon
rule 11; all code is reviewed and understood by the team.
