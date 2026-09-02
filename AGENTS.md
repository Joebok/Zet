### Environment Fallback
- Always prioritize Python 3 over Python 2.
- Use `python3` explicitly for executing any python scripts.
- Do not assume system `python` points to a modern release.

### Architecture Boundary
- Keep reusable Zet behavior in backend code under `zet/services`, `zet/repositories`, `zet/models`, and pipeline scripts.
- Keep `zet/web` focused on FastAPI routes, page/API presentation, browser interaction, and calling backend service methods.
- Do not add file layout discovery, pipeline stage transitions, prompt review operations, render orchestration, or other reusable business logic directly to the web layer.
- When the dashboard needs a new workflow action, expose it through `ZetApp`, `AssetRef`, or a focused service first so other interfaces can reuse the same backend behavior.
- The old Streamlit dashboard and standalone Render Console are retired. Do not add new workflow functionality to them.
- If a package is not available, do not design a work-around. Stop and ask that the desired package be installed.

### Terse Responses
Cut out all conversational filler, preambles, and polite explanations. Return only the requested code block, minimal bullet points, or the direct structural diff.

### Token Economy

Minimize token usage.

- Read only the files required for the current task.
- Never summarize unrelated code.
- Avoid opening large files unless the task explicitly requires them.
- Prefer searching for symbols over reading entire files.
- Stop reading once sufficient context has been gathered.

### Minimal Changes

When modifying code:

- Produce the smallest correct change.
- Prefer editing existing functions over rewriting them.
- Do not reformat unrelated code.
- Preserve existing style.
- Do not rename variables, functions, or files unless required.

### Diff Preference

Unless explicitly requested otherwise:

- Apply minimal edits.
- Do not regenerate an entire file for localized changes.
- Do not duplicate unchanged code.

### Scope Discipline

Stay inside the requested scope.

Do not:

- perform opportunistic refactoring
- modernize unrelated code
- improve comments outside the requested area
- fix unrelated warnings
- reorganize project structure

unless explicitly instructed.

### Stop Conditions

When blocked:

- Ask one concise question.
- Do not speculate.
- Do not invent missing APIs.
- Do not implement placeholders without permission.

### Prompt Contract Template

Every task should be interpreted using this contract.

Goal:
<what should be true>

Context:
<only relevant files or functionality>

Constraints:
<what must not change>

Success:
<how success is verified>

Anything outside this contract is out of scope.

### Reasoning Budget

Choose the simplest solution that satisfies the request.

Do not compare multiple architectures unless asked.

Do not explore alternatives unless requested.

Avoid speculative analysis.

## Specialized deep-review exception

The restrictions against broad refactoring, dead-code analysis, duplication
analysis, and data-model consolidation apply to normal implementation work.

They do not prohibit analysis by the custom agent named
`architecture_reviewer` when the user explicitly requests a deep code review,
codebase cleanup assessment, architectural review, or refactoring plan.

The `architecture_reviewer` may:

- investigate code beyond the immediate task;
- identify unused or obsolete code;
- identify duplicate implementations;
- recommend shared abstractions;
- compare and regularize data models;
- propose multi-stage refactoring;
- recommend deletion or migration candidates.

Unless the user explicitly authorizes implementation, this exception permits
analysis and planning only. It does not authorize editing, deleting, or moving
code.

After the review, implementation must be separately approved and divided into
small, testable stages.

## Approved architectural refactoring

Normal development work must remain narrowly scoped and must not perform
broad cleanup, model consolidation, dead-code removal, or architectural
refactoring.

The custom agent `refactoring_implementer` may perform such work only when:

1. an architecture review or written refactoring plan exists;
2. the user has explicitly approved the phase being implemented;
3. the agent implements only that approved phase;
4. relevant tests are added or run;
5. unrelated cleanup is excluded.

Approval of one phase does not authorize later phases.
The agent must stop after completing the approved phase.
