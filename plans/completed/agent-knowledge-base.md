# Agent-oriented Zet knowledge base

Status: complete
Related specification: user-attached "Build and Maintain an Agent-Oriented Project Knowledge Base" (2026-10-11).

## Goal

Give a coding agent with no chat history selective, source-backed navigation, system contracts, development guidance, and a maintenance convention. Documentation only; preserve existing instructions and design notes.

## Current behavior

[AGENTS.md](../../AGENTS.md) defines scope, Python, and web/service boundaries. [README.md](../../README.md) introduces the application but links to moved documentation. `Docs/` exists and is empty; `Docs-Joe/` contains design/research notes and archived plans. [.github/CODEX_WORKFLOW.md](../../.github/CODEX_WORKFLOW.md) owns issue delivery. Code and tests establish local character generation, two independent scene systems, shared queues, and distinct authoritative and derived catalogs.

## Desired behavior

An agent can find the implementation and tests for each major capability, distinguish active and retired workflows, preserve documented contracts, and write a bounded implementation plan. All new local Markdown links and referenced implementation paths resolve. Commands distinguish verified results from instructions not executed here.

## Impact analysis

Add `Docs/INDEX.md`, architecture, code map, data model, invariants, development, focused component documents, and retrospective ADRs. Extend root `AGENTS.md` without removing existing rules. Update README documentation links. Add this plan convention. No application, test, dependency, or build changes.

## Invariants and constraints

Single agent; no external writes, dependency installation, application startup against the user's library, or destructive operations. Evidence comes from source and tests. Preserve casing of existing `Docs/` and all `Docs-Joe/` notes. Do not infer historical design motives.

## Implementation steps

### WP1 — Repository discovery
- Dependencies: none.
- Files/interfaces: configuration, composition root, routes, repositories, focused services, tests, launchers, CI, and existing design notes.
- Work: identify ownership, data flows, current contracts, and gaps.
- Acceptance: enough evidence for every material architecture statement; identify retired paths.
- Validation: inspect implementation and corresponding tests.
- Status: complete.

### WP2 — Entry points and core knowledge
- Dependencies: WP1.
- Files/interfaces: `AGENTS.md`, `README.md`, `Docs/INDEX.md`, core documents, `plans/README.md`.
- Work: selective navigation, planning rules, contracts, and development guidance.
- Acceptance: clear primary owner for each topic; existing instructions preserved.
- Validation: path/link check and manual consistency review.
- Status: complete.

### WP3 — Focused subsystem knowledge and decisions
- Dependencies: WP1, WP2 structure.
- Files/interfaces: `Docs/COMPONENTS/`, `Docs/DECISIONS/`.
- Work: document library/universes, local characters, prompts, Scene Builder, Narrative, queues; record useful choices with explicit evidence limits.
- Acceptance: meaningful interfaces, failure modes, extension points, and relevant tests.
- Validation: trace symbols and claims to code/tests.
- Status: complete.

### WP4 — Verify and archive
- Dependencies: WP2, WP3.
- Files/interfaces: new documentation and this plan.
- Work: check links and paths; run focused contract tests; review diff; record gaps and actual outcomes; archive plan.
- Acceptance: documentation-only diff, valid references, honest validation status.
- Validation: `git diff --check`, local reference checker, focused pytest command recorded in development docs.
- Status: complete.

## Validation

Python 3.14.6 verified with `python3 -c "import sys; assert sys.version_info.major == 3; print(sys.executable); print(sys.version)"`. Required imports for focused pytest tests are available. Exact test commands and results are recorded in [DEVELOPMENT.md](../../Docs/DEVELOPMENT.md): first selection 54 passed / 2 failed; second selection 131 passed / 12 subtests passed. No packages installed.

Final standard-library reference/scope checker: 20 Markdown files, 618 local links, 108 linked Python class/member references, 21 changed/new files. All links/paths resolve with repository-relative casing; Python symbols resolve by AST inspection; Markdown whitespace/final newlines pass; every original nonblank AGENTS instruction is preserved; changes are Markdown and an empty active-directory marker only. `git diff --check` passed. New files were included in the custom whitespace check because plain Git diff does not include untracked additions.

## Risks and alternatives

Older notes describe aspirations that may differ from implementation. Keep them linked as intent, not current contracts. Direct integrations and launchers are not verified by starting live services. Keep documentation compact; use subsystem documents instead of repeating the code map.

## Progress and decisions

Discovery complete. Key findings: authoritative entity SQLite differs from machine-local index; Narrative does not call Scene Builder; traditional character generation is guarded as retired while compilation functions remain reused. Current production local policy admits ComfyUI/Qwen Image 2.1, despite older Stable Matrix support files.

Documentation created and traced to code/tests. Source review corrected module labels that could imply nonexistent classes and clarified entity variant terminology. Existing AGENTS rules and `Docs-Joe/` were preserved; README's moved documentation links now resolve to historical notes. Observed cutover fixture failures were documented, not repaired. Final link/symbol/whitespace checks passed and plan archived.

New-agent review traced tasks for local-character selection/locking, scene prompt compilation, independent Narrative generation, data changes, and validation from INDEX to code/tests. Primary owners are explicit: architecture for system interactions, data model for formats, invariants for contracts, code map for navigation/impact, components for workflow detail, development for commands/results, ADRs for evidence-backed choices, and plans for execution history. No task requires reading the whole corpus.

## Final results

Added 16 knowledge-base Markdown files (six core documents, six components, ADR index and three retrospective records), planning convention and this completed plan, plus an active-directory marker. Updated AGENTS and README. Application code, tests, dependencies, build configuration, and existing design notes were not changed.

Documentation acceptance checks passed. Focused application tests total 185 passed, 2 failed, and 12 subtests passed across two disjoint selections; the failed run is explicitly not represented as successful. The documentation objective is complete with the observed pre-existing fixture/contract mismatch recorded for a separate investigation task. Full Python/browser suites, live AI/rendering, macOS, and CI Python 3.11 were not verified. No follow-up implementation is authorized by this plan.
