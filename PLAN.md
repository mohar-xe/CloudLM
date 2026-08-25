# CloudLM — Implementation Plan

**Project:** Approval-gated cloud FinOps agent on TrueForge
**Hackathon:** [The Agent Harness Hackathon](https://www.wemakedevs.org/hackathons/trueforge) (WeMakeDevs × TrueFoundry × Qodo)
**Window:** Aug 24–30, 2026 · submissions close **Sun Aug 30, 8:00 PM London**
**Team:** 2–4 · **Primary track:** Best Use of TrueForge (auto-considered for all tracks)

---

## 1. Project definition

An agent you hand a FinOps goal to:

> *"Reduce spend by 20% while maintaining 99.9% availability and <200ms p99 latency."*

The agent:

1. Parses the goal into immutable **guardrails** (SLOs, savings target).
2. Collects multi-domain cloud data (billing, compute, storage, k8s, network) through a **custom MCP server** with cursored pagination.
3. Normalizes everything into a single `ResourceSnapshot` schema — the core engine never touches cloud-specific jargon.
4. Detects waste by **writing and executing Python in the TrueForge sandbox** (idle resources, zombie snapshots, over-provisioned K8s requests).
5. Simulates right-sizing with a **Monte Carlo + linear-regression latency model**, discards anything that would breach the latency SLO.
6. Ranks survivors with **CVaR risk scoring** (`savings / (effort × CVaR₅%)`) and picks the top-N that collectively hit the target.
7. Generates a Terraform plan, attaches the diff to an **Approval Manifest**, and **pauses for human approval** before touching anything.
8. On approval: applies against LocalStack, backs up pre-change state, opens an audit PR, and hands you a one-command rollback.
9. Optionally watches post-exec health for 1 hour and auto-rolls back within bounds you pre-authorized.

### Decisions locked

| Decision | Choice | Rationale |
|---|---|---|
| Data source | **Hybrid**: deterministic synthetic fabric (default) + real AWS read-only adapter (opt-in) | Judges can clone-and-run; realism available when you own the account |
| Terraform apply target | **LocalStack** AWS emulator | Real plan/apply lifecycle, zero blast radius, fully judge-runnable |
| Track emphasis | Best Use of TrueForge primary; Code Quality + UI ride along | Every layer showcases more harness primitives |
| UI strategy | Generative UI first (L1–4), custom React overlay only in L5 | Built-in capability wins early; overlay is the designated cut-line |

---

## 2. Flow → TrueForge primitive mapping

Every step of the 11-step execution flow lands on a harness feature. This table is the "TrueForge is doing the work" evidence map for judges.

| # | Flow step | TrueForge primitive |
|---|---|---|
| 0 | Intake & guardrail parsing | Agent instructions + `response_format: json_schema` |
| G1 | Clarifying question (prod/dev?) | Built-in `ask_user_questions` capability |
| 1 | Decomposition → JSON checklist | Planner turn constrained by json_schema output |
| 2 | Parallel data collection | **Dynamic subagents** (5 collectors, isolated contexts), deferred tool loading |
| 2.5 | Partial failure / degraded | Freshness + status metadata propagated in subagent results |
| 3 | Normalization → `ResourceSnapshot` | Provider adapters inside the custom MCP server (pydantic schema) |
| 4 | Sandboxed waste detection | **Sandbox-as-tool** + Code Mode + large-tool-response offloading + git-backed Skills |
| 5 | Monte Carlo simulation | Same sandbox; Python sim scripts over offloaded snapshot files |
| G2 | SLO discard gate | Guardrail check inside sim script + agent instructions |
| 6 | CVaR scoring & ranking | Sandbox script (CVaR α=0.05, knapsack top-N) |
| 7 | Terraform plan (read-only) | Second MCP server `terraform-executor`; plan tool annotated read-only |
| 8 | Approval manifest | Persisted artifact + **Generative UI** card/form rendered in chat |
| 9 | Human decision gate | `require_approval_for_tools` on `@destructive` tools → native Allow/Deny pause |
| 10 | Apply + pre-state backup | Apply tool + `terraform state pull` → `backups/{manifest_id}.tfstate` |
| 11 | Audit PR + post-exec watcher | GitHub PR via API/MCP; SDK-driven watcher loop → rollback within pre-authorized bounds |
| — | Session survives reconnects/restarts | Harness session persistence (demoed freebie, L5) |
| — | Any-model switchability | Provider-agnostic model config (demoed freebie, L5) |

---

## 3. The five layers

Each layer is a **complete, independently submittable state**: public repo, working agent, README a stranger can follow, demo clip, Qodo-reviewed PR trail. Later layers only add.

---

### Layer 1 — Read-Only FinOps Analyst *(Aug 25–26)*

> **If you stop here you can submit:** a repo where a judge runs one command, types the goal, and watches the agent hit real paginated MCP tools, ask a clarifying question, and answer with normalized multi-cloud data.

**Covers flow steps:** 0, G1, 2 (single-domain version), 3.

**Build:**

- uv workspace monorepo (Python, per D-013):
  ```
  CloudLM/
  ├── mcp/
  │   ├── cloud-fabric/        # custom MCP server (TS, streamable HTTP)
  │   └── terraform-executor/  # placeholder until L4
  ├── packages/
  │   └── fabric-core/         # shared contracts: pydantic models, cursors, provider protocol
  ├── agents/                  # finops-agent spec as code
  ├── skills/                  # SKILL.md packs (from L2)
  ├── docs/
  ├── .github/workflows/ci.yml
  └── README.md
  ```
- **`cloud-fabric` MCP server** (Python/FastMCP, streamable HTTP on localhost, registered under Settings → Connectors):
  - Tools: `list_resources(cursor, filters)`, `get_metrics(arn, window)`, `get_billing_summary(period)`
  - Cursored pagination everywhere (10k+ resources, no OOM)
  - Provider adapters behind one interface:
    - `synthetic` (default): deterministic seeded fixture generator (~12k resources across compute/storage/k8s/network/billing)
    - `aws` (opt-in flag): read-only Cost Explorer + Describe* APIs
- Normalizer → unified `ResourceSnapshot` pydantic schema: `resource_arn`, `resource_type`, `hourly_cost`, `avg_cpu`, `avg_memory`, `p99_latency`, `instance_family`, `freshness`
- Agent spec as code (`agents/finops-agent.json`) + TS SDK bootstrap script that registers the connector + agent
- Instructions encode **Step 0**: parse goal → restate guardrails as an immutable block in every report
- Gate 1 via built-in ask-user-questions ("Which environment? Prod or Dev?")
- **Qodo installed day one**; every substantive change goes branch → PR → review → merge
- README v1: judge quickstart (clone → compose up → seed → chat), architecture sketch, Qodo evidence section placeholder

**Demo clip #1:** prompt → clarifying question answered → paginated tool calls streaming in agent steps → normalized cost summary + heuristic top-waste list.

---

### Layer 2 — Sandboxed Waste Detective *(Aug 26–27)*

> **Adds:** sandbox code execution, skills, degraded-data handling, test/CI discipline.

**Covers flow steps:** 2.5, 4.

**Build:**

- Enable sandbox on the agent; skill `skills/finops-analysis/SKILL.md` — detector playbook loaded via progressive disclosure
- `packages/detectors/` — pure Python library, each detector unit-tested (pytest) with fixtures:
  - Idle resources: CPU < 5% for 14 days
  - Zombie snapshots: EBS/S3 snapshots > 30 days attached to terminated instances
  - Over-provisioned K8s: requests ≥ 5× actual usage
- Agent flow: pull snapshots → harness offloads large payload to sandbox file → **Code Mode** script imports detectors → emits versioned Findings JSON artifact
- Findings rendered as a **Generative UI table** in chat
- Degraded mode: every snapshot carries `collected_at` + `status: ok|degraded`; report template must surface staleness warnings verbatim
- CI: ruff + mypy + pytest (schema round-trips); branch protection on `main`

**Demo clip #2:** agent-steps panel showing sandbox execution + findings table + a degraded-data banner when the K8s feed is stale.

---

### Layer 3 — Simulation, CVaR Ranking & Approval Manifest *(Aug 27–28)* ⭐ qualifying heart

> **Adds:** the third pillar judges must see — the pause for human approval. All three pillars (MCP ✓ L1, sandbox ✓ L2, approval ✓ L3) are now demonstrable end-to-end.

**Covers flow steps:** 1, 5, G2, 6, 8, 9 (advisory-only approve).

**Build:**

- Planner turn: structured phases checklist via `response_format: json_schema`
- `packages/simulation/` (Python):
  - Latency regressor: fit historical cpu/mem vs p99 from fabric metrics
  - Monte Carlo (N=1000) downsizing sims per candidate: new cost from pricing tables, latency distribution
  - **Gate 2:** discard any candidate whose simulated p95 latency breaches the SLO
  - CVaR α=0.05 of the outcome distribution → risk score = `savings / (effort × CVaR)` → sort → knapsack top-N hitting the savings target
- `ApprovalManifest` schema: `{ manifest_id, recommendations[], total_savings, risk_rating, expires_at, rollback_ref }` persisted as a session artifact + file store
- Manifest rendered via **Generative UI card with Approve/Reject buttons** (OpenUI form)
- Reject loop: feedback captured → re-rank excluding rejected set → next-best combination
- Expiry (>24h): agent auto-suggests re-running analysis/simulation before any execution
- Approval at this layer = authorization to *generate* the execution plan (no infra change yet)

**Demo clip #3:** the full advisory loop with the visible *"Rollback is irreversible. Holding for your approval."* moment, then resume after Approve.

---

### Layer 4 — Closed-Loop Executor *(Aug 28–29)*

> **Adds:** acting, reversibly, on LocalStack.

**Covers flow steps:** 7, 9 (real gate), 10, 11 (PR part).

**Build:**

- **`terraform-executor` MCP server**:
  - `tf_plan(manifest_id)` — read-only annotation; returns red/green diff attached to the manifest
  - `tf_apply(manifest_id)` — **@destructive** annotation → harness-enforced Allow/Deny pause
  - `tf_rollback(manifest_id)` — @destructive; replays reverse plan from backup
  - Pre-apply backup: `terraform state pull` → `backups/{manifest_id}.tfstate` (versioned local dir; S3 adapter optional)
- Target environment: **LocalStack** via docker compose profile `exec`; synthetic provider emits matching `.tf` import blocks so plan/apply is real against the emulator
- **Double safety envelope:**
  1. MCP tool annotations → TrueForge pauses before write/destructive calls
  2. Server-side policy: resource-type allowlist, $ cap per manifest, expiry check, manifest-hash match
- GitOps audit trail: auto-open PR with generated `.tf` files (GitHub token via env, documented)
- Expiry revalidation before apply: if manifest > 24h old, force re-plan

**Demo clip #4:** approve → plan diff shown → apply → verify state → one-command rollback → state restored.

---

### Layer 5 — Resilient Fabric & Submission Package *(Aug 29–30)*

> **Adds:** subagent fan-out, auto-rollback watcher, custom UI, final submission.

**Covers flow steps:** 2 (full parallel version), 11 (watcher).

**Build:**

- **Parallel collector subagents:** root agent delegates billing/compute/storage/k8s/network to 5 subagents (isolated contexts); partial failure marks dataset degraded and propagates a banner to the final report
- **Post-exec watcher:** small TS service on the HTTP API polling health metrics for 60 min post-apply; breach beyond thresholds → auto-rollback — **only if the manifest contains pre-authorization bounds set by the human** ("auto-rollback authorized: yes/no, cpu_spike_threshold")
- Demoed freebies (zero extra code): session survives server restart/reconnect; model switched mid-session
- **Custom React overlay** (team has capacity): dashboard on the TrueForge HTTP API — sessions list, live agent-step stream, manifest cards, red/green diff viewer, approval timeline. *(Designated cut-line if time slips — Generative UI already covers Best UI basics.)*
- **Submission package:**
  - Final ~3-min demo video (script: problem → goal+guardrails → collection w/ subagents → sandbox detection → simulation+CVaR → **approval pause** → apply → rollback → watcher)
  - Short write-up (what the agent does, how it uses TrueForge)
  - Blog post draft (Field Report track) + per-layer social clips (swag track)
  - README final pass: Qodo evidence section, architecture diagram, judge quickstart, rule-compliance checklist

---

## 4. Timeline

| Date | Layer | Hard outputs |
|---|---|---|
| Tue Aug 25 | L1 start | Register ✅, Qodo installed ✅, repo scaffold, fabric server started |
| Wed Aug 26 | **L1 done** → L2 start | Tag `layer-1`, demo clip #1 |
| Thu Aug 27 | **L2 done** → L3 start | Tag `layer-2`, detectors tested, CI green |
| Fri Aug 28 | **L3 done** → L4 start | Tag `layer-3`, demo clip #3 |
| Sat Aug 29 | **L4 done** → L5 start | Tag `layer-4`, LocalStack loop works |
| Sun Aug 30 AM | L5 done | Video, blog, README final |
| Sun Aug 30 ≤ 8PM London | **Submit** | Repo + video + write-up |

## 5. Standing rules (every layer)

1. **Qodo on every substantive merge:** branch → PR → Qodo review → fix valid High findings / dismiss with recorded reason → follow-up review → human merges. Keep the README `## Qodo Code Review Evidence` section live from day one.
2. **Secrets hygiene:** `.env.example` committed, real keys never; no keys/personal data in repo or video.
3. **AI-assistance disclosure** noted in README (rule 11).
4. Tag `layer-N` releases at each completion — built-in audit trail of the build week.
5. Every substantive change through reviewed PRs — direct pushes to `main` don't count.
6. Only connect accounts/tools that are yours; synthetic provider keeps the repo stranger-runnable.

## 6. Judging criteria coverage

| Criterion (equal weight) | Covered by |
|---|---|
| Potential impact | Clear FinOps job: cut spend 20% without breaching SLOs |
| Creativity & originality | CVaR-ranked infra changes; regression-based latency prediction instead of load tests; pre-authorized auto-rollback |
| Technical excellence | Typed monorepo, tested detectors/sims, cursored pagination, double safety envelope, CI |
| Use of sponsor tools | TrueForge central: MCP ×2, sandbox, skills, subagents, approvals, Generative UI, sessions, SDK. Qodo reviews every PR |
| Control & safety | Harness-enforced pause on destructive tools + policy allowlist/spend-cap/expiry checks + backups + bounded auto-rollback |
| Presentation | Scripted 3-min demo with the approval pause front and center; per-layer clips |

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Custom MCP server needs remote URL registration | Run `cloud-fabric` as localhost streamable-HTTP service; document registration; fallback stdio proxy if needed |
| LocalStack drift from real AWS APIs | Pin LocalStack version; synthetic `.tf` targets only well-supported resources (EC2, EBS); plan verified in CI smoke test |
| Regression model garbage-in on synthetic data | Generator emits coherent cpu/mem↔latency correlation by construction; unit-test regressor on known curves |
| Time slip | Cut-line order: L5 custom UI → L5 watcher polish → real-AWS adapter. Layers 1–4 alone are fully submittable |
| Qodo noise/blocking | Set up day one (done), dismiss-with-reason workflow documented |

## 8. Submission checklist (final)

- [ ] Public repo, clone-and-run quickstart verified on a clean machine
- [ ] README: setup, architecture, `## Qodo Code Review Evidence` with merged PR links
- [ ] ~3-min demo video showing agent working incl. approval gate
- [ ] Write-up: what it does + how it uses TrueForge
- [ ] Blog post link (optional Field Report entry)
- [ ] Social posts tagged WeMakeDevs + TrueFoundry (+ Qodo)
- [ ] No secrets/personal data anywhere
- [ ] Submitted before Sun Aug 30, 8:00 PM London
