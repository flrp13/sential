# Sential Research Synthesis

## One-Sentence Thesis

Sential should become the local-first context compiler for codebases: a cheap, inspectable system that turns repository facts into grounded, refreshable context packs for humans, agents, CI, and audits.

## What Sential Is Trying To Be

Sential's current direction is right: do not chat with the whole repo, and do not become a generic coding assistant. Its job is to economically map a codebase before expensive model calls happen.

The core product primitive is a trustworthy repo model:

- Scan Git-aware source structure, manifests, docs, tests, and high-signal files.
- Rank files and symbols under explicit token budgets.
- Ask an LLM for an onboarding syllabus only after deterministic evidence is available.
- Generate layered guides from focused file sets instead of raw repo dumps.
- Preserve enough provenance that users can see what was selected, what was excluded, and why.

The strongest positioning is not "AI-generated docs." It is "compile the right repository context for the next human or agent task."

## What It Could Become

Sential could become a production-grade repo intelligence layer that sits before agents, IDEs, CI, documentation workflows, and model gateways.

In the local-first version, Sential produces a portable context pack: Markdown for people, SQLite/JSONL for tools, and read-only MCP resources for agents. In a team or hosted version, the same pipeline can run behind queues, observability, budgets, tenant controls, and audit logs.

The strategic leap is from one-shot onboarding guide to living repository memory:

- A new hire gets a reading path, architecture map, and "first files to understand."
- A coding agent gets `AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions, and task-specific context.
- A PR gets an understanding diff: affected modules, stale guide sections, likely docs drift, architecture implications, and review prompts.
- A security or compliance reviewer gets proof of which source code was sent to which model, with redactions, token counts, prompts, and hashes.

The product should stay narrow at the surface but deep in the substrate: better context selection, better grounding, better refresh, better auditability.

## Core System Architecture

The architecture should keep Sential's economical pipeline as the backbone and add state, retrieval, verification, and agent interfaces around it.

1. Deterministic repo scan

Build a canonical file inventory from Git state, ignore rules, manifests, language filters, generated/vendor detection, token estimates, and file roles. This remains the cheap first pass that makes the rest of the system practical.

2. Local fact store

Add `.sential/` with SQLite as the durable index and JSONL as export. Store files, hashes, symbols, chunks, imports, manifests, tests, summaries, claims, chapter memberships, prompts, model calls, costs, and run manifests. Every derived fact should carry provenance, confidence, extractor version, and invalidation data.

3. Tiered structure extraction

Keep ctags as the broad fallback. Add Tree-sitter for high-value languages, starting with Python, then JS/TS, Go, Rust, and Java. Prioritize cheap graph edges first: imports, manifests, package boundaries, test-to-source hints, routes, config, and entrypoints. Treat SCIP/LSP, CodeQL, Semgrep, and deeper call graphs as optional precision tiers.

4. Hybrid retrieval and context packing

Move from one-shot file selection to chapter-aware retrieval. For each chapter or question, combine exact path and symbol lookup, file-role scoring, BM25/FTS, graph expansion, Git recency, optional embeddings, and lightweight reranking. Then pack context under a visible token budget with rationale for inclusion and exclusion.

5. Source-grounded generation

The planner should propose chapter hypotheses and evidence needs. The writer should generate only from evidence bundles. A reviewer should check citations, unsupported architecture claims, missing central files, wrong symbols, stale facts, and token waste. Repair only failed claims or chapters.

6. Run ledger and incremental refresh

Persist scanner inputs, config, commit SHA, token budgets, prompts, model IDs, costs, artifact hashes, selected files, excluded files, and reviewer critiques. Use hashes, Git diffs, graph neighborhoods, and chapter-source maps to regenerate only affected sections.

7. Interfaces for humans and agents

Export `Overview.md`, role-specific guides, context manifests, `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, Copilot instructions, and audit logs. Add a read-only MCP server with tools like `rank_files`, `expand_symbol`, `chapter_context`, `diff_impact`, `explain_manifest`, and `budgeted_retrieve`.

8. Production control plane, later

For teams, add FastAPI job APIs, Celery/Arq workers, Postgres, object storage, pgvector, LiteLLM Proxy, OpenTelemetry, Phoenix/LangSmith/Helicone adapters, and tenant budgets. Defer Temporal, Qdrant, Neo4j, and enterprise isolation until scale or customer requirements justify them.

## Product Wedges

- Local-first context compiler for private repos: a better alternative to pasting whole repositories into an LLM.
- Agent memory generator: concise, source-backed memory files for Cursor, Claude Code, Codex, Copilot, Continue, and future agents.
- Continuous repo memory: `sential refresh --since main` updates only stale chapters, maps, and memory facts.
- PR intelligence report: `sential ci --base origin/main` explains how a change affects the repo's mental model.
- Audit-ready context minimization: prove what code was sent to a model, why, with what redactions, prompts, costs, and hashes.
- Role and task onboarding: `sential guide --persona backend-new-hire` or `sential explain "how auth works"` using the same compiled repo map.
- Lightweight architecture intelligence: entrypoints, module boundaries, dependency hints, diagrams, and blast-radius summaries without requiring a full code intelligence platform.

## Research / Engineering Bets

- Evidence-backed syllabus: chapters should be hypotheses with required evidence, confidence, and known gaps, not just titles.
- SQLite repo intelligence graph: a local substrate for guides, retrieval, MCP, refresh, evals, and audit.
- Tree-sitter plus import graph: the best near-term quality upgrade beyond ctags.
- Chapter-aware hybrid retrieval: measure file and symbol recall before judging prose quality.
- Claim-level source maps: every important claim should trace to files, symbols, manifests, commands, or approved memory.
- Verifier and repair loop: bounded agentic review is more valuable than unconstrained multi-agent autonomy.
- Incremental regeneration: make guides and memory durable by detecting what changed and why it matters.
- Eval harness: pinned repos, gold file/symbol sets, onboarding questions, unsupported-claim scoring, token-weighted precision, cost, latency, and run stability.
- Context pack artifact: `manifest.json`, `repo.sqlite`, symbols, graph edges, chapter contexts, claim maps, guides, costs, and stale-section diagnostics.
- Prompt and model gateway discipline: stable prompt prefixes, cost budgets, local/no-network modes, provider adapters, and cached deterministic stages.

## First 90 Days

Days 1-15: sharpen the wedge and baseline quality.

- Position Sential as "local-first repo context compiler for agents and onboarding."
- Build a small eval suite across Python, TypeScript, Go, Rust, and mixed repos.
- Compare against Repomix, Gitingest, DeepWiki-style output, README-only onboarding, and whole-repo prompting.
- Instrument token count, file-role coverage, symbol coverage, hallucination rate, onboarding question success, and human usefulness.

Days 16-35: ship agent memory exports.

- Add `sential memory export --format agents-md|claude|cursor|copilot`.
- Generate purpose, structure, commands, tests, conventions, important files, security gotchas, and paths to avoid.
- Keep memory budget-aware: small root memory plus scoped rule files where useful.
- Add approval: generated facts start as suggestions, accepted facts become durable memory.

Days 36-55: add incremental repo memory.

- Introduce `.sential/index.sqlite` with file hashes, symbols, categories, token counts, chapter associations, and fact provenance.
- Implement `sential refresh --since <ref>` and `sential diff --base <ref>`.
- Output changed modules, stale chapters, affected memory files, and suggested updates.
- Make refresh deterministic and explainable before making it highly agentic.

Days 56-70: launch report-only CI.

- Create a GitHub Action for `sential ci --base main --format markdown`.
- Post compact PR comments: changed high-signal files, affected modules, stale memory, docs drift, architecture notes, and context audit summary.
- Add config for ignored paths, max tokens, model provider, local-only mode, and comment verbosity.
- Tune for low noise; do not block PRs initially.

Days 71-85: add privacy and audit controls.

- Add `sential inspect-payload`, audit logs, selected/excluded file manifests, token counts, provider/model records, and timestamps.
- Add secret scanning or preflight redaction before hosted model calls.
- Add a no-network dry run that emits deterministic artifacts without contacting an LLM.
- Document exactly what stays local and what may leave the machine.

Days 86-90: package demos and choose the next bet.

- Demo agent memory generation for a private repo.
- Demo "onboard to an unfamiliar repo in 10 minutes."
- Demo PR understanding diff and stale docs/memory detection.
- Decide based on pull: individual context compiler, team CI memory, or security audit layer.

## Decisions To Discuss

- Is the primary wedge agent memory, onboarding, CI drift, or audit-ready context minimization?
- Should `.sential/index.sqlite` become the central artifact now, or should JSONL stay primary until schemas settle?
- Which language gets the first Tree-sitter upgrade after Python, and what is the minimum supported language matrix?
- How strict should claim-level grounding be in the first public version?
- Should MCP ship early as a differentiator, or wait until the local fact store and retrieval APIs are stable?
- What should be local-only by default, and what requires explicit hosted-model opt-in?
- Which eval metrics are non-negotiable before adding more agentic behavior?
- Should Sential generate memory files directly, or propose patches that users accept into the repo?
- How opinionated should CI comments be before they become noisy?
- What is the smallest context pack that feels obviously better than Repomix/Gitingest without becoming a platform?
