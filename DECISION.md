# Decision Log

Human-first decision record for CloudLM. Every meaningful choice between two or
more viable options lands here, with the reasoning that produced it.

**Protocol**

- Entries are append-only. A superseded entry keeps its number and gains
  `Status: superseded by D-xxx`. Never delete history.
- Architecture-level decisions (schemas, contracts, new components, external
  behavior) are **paused and asked** before implementation.
- Implementation-level decisions are logged directly and surfaced in the session
  summary so they can be vetoed retroactively.
- One entry per decision, even if decided mid-conversation.

Entry fields: `Context` (what forced a choice) · `Decision` · `Why` (the actual
reasoning) · `Rejected` (alternatives + why) · `Consequence` (what we now accept).

---

## D-001 · Hybrid data fabric: synthetic default, real AWS opt-in

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** accepted

**Context:** Hackathon rules require judges to be able to run the repo, while also requiring connected tools to be real and accounts to be yours. A pure real-cloud demo is un-runnable by strangers; a pure mock weakens the "connected, not mocked" story.

**Decision:** The `cloud-fabric` MCP server ships two provider adapters behind one interface: a deterministic synthetic generator (default, seeded) and a read-only AWS adapter (opt-in via env flag with your own credentials).

**Why:** Judges clone → run → get identical data on any machine; we can still point at a real account for the demo video. One interface means Layer 2–5 code never knows which is active.

**Rejected:** Synthetic-only (loses realism); AWS-only (unjudgeable, secret-scrubbing risk).

**Consequence:** Synthetic data must be *plausible* (coherent cost/metric correlations) or later layers' regressions and simulations will look fake. AWS adapter is partial in L1 (EC2/EBS/S3-class resources; no EKS deep metrics yet).

---

## D-002 · LocalStack as the Terraform apply target

- **Date:** 2026-08-25 · **Layer:** 4 · **Status:** accepted

**Context:** Layer 4 must demonstrate a real plan → apply → backup → rollback loop. Options: emulator, throwaway cloud account, or plan-only.

**Decision:** Apply runs against LocalStack (docker compose profile `exec`). The synthetic provider emits matching `.tf` import blocks.

**Why:** Real Terraform lifecycle end-to-end, zero blast radius, fully judge-runnable without any credentials.

**Rejected:** Throwaway AWS account (strongest impression but unshippable in repo, guardrail burden, can't be in demo safely); plan-only (weakens "agent acts" — apply becomes theater).

**Consequence:** Resource types are limited to what LocalStack emulates well (EC2, EBS). Real-account mode stays a documented possibility but is not a goal.

---

## D-003 · Track emphasis: Best Use of TrueForge primary

- **Date:** 2026-08-25 · **Layer:** all · **Status:** accepted

**Context:** All submissions are auto-considered for three judged tracks; effort allocation across 7 days is zero-sum.

**Decision:** Optimize every layer to showcase more harness primitives (MCP, sandbox, approvals, subagents, sessions). Code Quality rides on CI + Qodo discipline; Best UI rides on Generative UI early + optional custom overlay in L5.

**Why:** The TrueForge track has the largest prize and explicitly rewards what our architecture already does; the other tracks are won as side effects rather than extra work streams.

**Rejected:** Split focus TrueForge+UI (custom frontend too early would starve the core loop); Code-Quality-primary (review trail alone doesn't differentiate the product).

**Consequence:** L5's custom React dashboard is the designated cut-line if time slips.

---

## D-004 · Monorepo layout and language split

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** superseded by [D-013](#d-013--python-everywhere-supersedes-typescript)

**Context:** Original plan assumed TypeScript services (TrueForge SDK is TS) plus Python sandbox packages.

**Decision:** pnpm monorepo; TypeScript for MCP servers/SDK bootstrap; Python only inside the sandbox.

~~**Why / Rejected / Consequence:** see D-013 — language choice reversed before implementation started.~~

---

## D-005 · cloud-fabric runs as a localhost streamable-HTTP MCP service

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** accepted

**Context:** TrueForge registers MCP connectors by URL under Settings → Connectors (catalog entries or arbitrary remote URLs). Our fabric is a local process, not a hosted SaaS.

**Decision:** Serve the fabric over streamable HTTP bound to `127.0.0.1:<port>` at `/mcp`; register it once in the TrueForge UI as a custom connector pointing at `http://127.0.0.1:9000/mcp`.

**Why:** Matches exactly how TrueForge ingests connectors; keeps auth surface local; one process, no tunneling needed for local judging.

**Rejected:** stdio transport (TrueForge's documented registration path is URL-based); public tunnel/ngrok (unnecessary exposure for a local hackathon build).

**Consequence:** Judge quickstart needs two processes (fabric + TrueForge). Documented as copy-paste commands; a compose file arrives in L4.

---

## D-006 · Cursored pagination contract on every fabric tool

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** accepted

**Context:** The flow requires handling 10k+ resources without OOM and without dumping huge payloads into model context.

**Decision:** Every listing tool accepts an opaque `cursor` string and returns `{items, next_cursor, total_estimate}`. Page size bounded (≤1000). Cursor encodes offset + a hash of the filter set.

**Why:** Offset cursors are trivially correct over a static snapshot; the filter-hash prevents inconsistent paging when filters change mid-walk. Bounded pages keep harness context lean (large payloads get offloaded to sandbox files anyway — belt and braces).

**Rejected:** Keyset cursors (needed for mutable stores; our synthetic dataset is immutable per process, AWS adapter may revisit); returning everything at once (context bomb).

**Consequence:** Walk-the-pages loops in later layers must pass identical filters per walk; enforced by cursor validation error otherwise.

---

## D-007 · Pydantic `ResourceSnapshot` is the single normalization boundary

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** accepted

**Context:** Multi-cloud raw payloads differ wildly; everything downstream (detectors, simulation, CVaR) must be cloud-agnostic (flow Step 3).

**Decision:** All providers normalize into one versioned pydantic schema — `resource_arn`, `resource_type`, `domain`, `region`, `instance_family`, `hourly_cost`, `avg_cpu`, `avg_memory`, `p99_latency_ms`, `created_at`, `collected_at`, `status`, plus lineage fields (`parent_arn`, `parent_state`) sized for L2 zombie detection.

**Why:** One boundary = detectors/simulators written once; `freshness` (`collected_at`, `status`) bakes degraded-mode reporting (flow Step 2.5) into the data instead of bolting it on.

**Rejected:** Per-domain schemas joined later (leaks joins into every consumer); untyped dicts (judges' code-quality criterion dies here).

**Consequence:** Schema evolution is a versioned event from day one; breaking changes require a migration note in FLOW.md's contracts section.

---

## D-008 · Generative UI first for manifests; custom overlay deferred to L5

- **Date:** 2026-08-25 · **Layer:** 1→5 · **Status:** accepted

**Context:** The Approval Manifest (Step 8) needs Approve/Reject affordances. TrueForge offers native Generative UI cards/forms; a bespoke React app is possible via the HTTP API/UI SDK.

**Decision:** Render manifests with built-in Generative UI through L1–L4. Custom dashboard only in L5, and only if time remains.

**Why:** Zero-code interactive UI that judges already recognize as harness capability; keeps the critical path on agent logic.

**Rejected:** Building the dashboard first (UI track bait; starves the qualifying core).

**Consequence:** If L5 slips, Best UI candidacy rests on Generative UI quality — acceptable per D-003.

---

## D-009 · Double safety envelope around destructive actions

- **Date:** 2026-08-25 · **Layer:** 3–4 · **Status:** accepted

**Context:** Flow Steps 9–10 require a human gate before irreversible infra changes. Tool annotations gate calls in the harness, but caps/expiry/hash checks are policy, not annotation.

**Decision:** Two independent enforcement layers: (1) MCP tool annotations (`@read-only` vs `@destructive`) driving TrueForge's native approval pause; (2) server-side policy checks inside terraform-executor — resource-type allowlist, $ cap per manifest, manifest expiry, manifest-hash match.

**Why:** Either layer failing leaves the other standing; judges can see both (harness pause in UI trace, policy rejection in tool output). This is the Control & Safety judging criterion made demonstrable twice.

**Rejected:** Annotations alone (policy bypassable by calling executor directly); policy alone (no visible human moment in the chat transcript).

**Consequence:** Executor must be stateful enough to know each manifest's cap/expiry — persisted alongside the manifest itself.

---

## D-010 · Qodo reviews every substantive PR from day one

- **Date:** 2026-08-25 · **Layer:** all · **Status:** accepted

**Context:** Hackathon rule: substantive changes merge only through Qodo-reviewed PRs; README must link evidence. Also feeds the Best Code Quality track.

**Decision:** Install Qodo before the first commit lands on GitHub; branch → PR → review → fix/dismiss-with-reason → follow-up review → human merge, for every layer.

**Why:** Requirement compliance is cheapest when habitual from commit #1; retrofitting a review trail is impossible.

**Rejected:** "Set it up later" (the trail would start thin precisely where judges look).

**Consequence:** Even docs/scaffold changes ride PRs; direct pushes to `main` never happen.

---

## D-011 · Tagged `layer-N` releases; every layer independently submittable

- **Date:** 2026-08-25 · **Layer:** all · **Status:** accepted

**Context:** Deadline is Aug 30 8PM London; a half-built L5 must never poison a working L4.

**Decision:** Each layer ends with: green CI, updated README + demo clip, git tag `layer-N`. Submission at any tag is legitimate.

**Why:** Converts schedule risk into scope risk (cut features, not integrity); gives judges a readable growth path through tags.

**Rejected:** Single big-bang submission (all-or-nothing on deadline day).

**Consequence:** Layer boundaries are hard: no cross-layer shortcuts even when tempting mid-week.

---

## D-012 · Living docs protocol: DECISION.md + FLOW.md

- **Date:** 2026-08-25 · **Layer:** all · **Status:** accepted

**Context:** Hackathon rules 12–13: participants must understand and be able to explain every technical decision; AI-generated-but-unverified projects may be rejected.

**Decision:** Maintain DECISION.md (this file, append-only) and FLOW.md (one evolving function-level execution trace + data contracts + layer changelog). Update cadence: decisions as they happen, flow at every `layer-N` tag.

**Why:** Human-first traceability — the team can narrate any code path and its rationale during judging; doubles as architecture documentation for strangers cloning the repo.

**Rejected:** Ad-hoc README-only documentation (decisions rot into folklore within days).

**Consequence:** Docs updates are part of each layer's definition-of-done, not optional polish.

---

## D-013 · Python everywhere (supersedes TypeScript)

- **Date:** 2026-08-25 · **Layer:** 1 · **Status:** accepted

**Context:** D-004 planned TS services because TrueForge ships a TS SDK. Before implementation began, the language call was revisited.

**Decision:** Entire codebase is Python: FastMCP servers, shared core package, bootstrap scripts, tests. TrueForge is driven via its HTTP API instead of the TS SDK.

**Why:** One language across MCP servers, future sandbox analysis (Python-native), detectors, and simulation removes dual-toolchain overhead for a 7-day hackathon. Everything the TS SDK does is available over the REST API (`POST /api/v1/agents`, SSE turns). Team fluency in Python makes the human-first explainability requirement (D-012) materially easier.

**Rejected:** Keeping TS for servers (two languages, two lint/test stacks, context-switching tax for zero functional gain — the SDK saves ~50 lines of httpx).

**Consequence:** Agent spec/bootstrap uses plain HTTP calls; SSE turn-streaming helpers live in our own small client module if later layers need programmatic drives. D-004 retained as history.
